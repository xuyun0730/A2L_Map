from __future__ import annotations

import csv
import difflib
import hashlib
import json
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


A2L_OBJECT_TYPES = {"MEASUREMENT", "CHARACTERISTIC", "AXIS_PTS", "INSTANCE", "BLOB"}


def file_fingerprint(path: Path) -> dict[str, Any]:
    stat = path.stat()
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return {
        "path": str(path.resolve()),
        "size": stat.st_size,
        "modified": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(),
        "sha256": digest.hexdigest(),
    }


def _read_text(path: Path) -> str:
    for encoding in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    return path.read_text(encoding="utf-8", errors="replace")


def _clean_line(line: str) -> str:
    return re.sub(r"/\*.*?\*/", "", line).strip()


def _quoted_values(text: str) -> list[str]:
    return re.findall(r'"((?:[^"\\]|\\.)*)"', text)


def _atom_tokens(text: str) -> list[str]:
    return re.findall(r'"(?:[^"\\]|\\.)*"|\S+', text)


@dataclass
class A2LObject:
    name: str
    object_type: str
    address: int | None = None
    data_type: str | None = None
    conversion: str | None = None
    unit: str | None = None
    lower_limit: str | None = None
    upper_limit: str | None = None
    record_layout: str | None = None
    dimensions: list[int] = field(default_factory=list)
    source_line: int = 0
    raw_fields: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["address_hex"] = format_address(self.address) if self.address is not None else None
        return result


@dataclass
class MapSymbol:
    name: str
    vma: int
    lma: int
    size: int
    align: int
    section: str = ""
    object_file: str = ""
    source_line: int = 0

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result.update(vma_hex=format_address(self.vma), lma_hex=format_address(self.lma))
        return result


def format_address(value: int | None) -> str | None:
    return None if value is None else f"0x{value:X}"


def parse_a2l(path: Path) -> tuple[list[A2LObject], dict[str, Any]]:
    text = _read_text(path)
    lines = text.splitlines()
    module = None
    project = None
    asap2 = None
    byte_order = None
    objects: list[A2LObject] = []
    block_pattern = re.compile(r"^\s*/begin\s+(\w+)(?:\s+(.*))?$", re.IGNORECASE)
    for idx, line in enumerate(lines):
        clean = _clean_line(line)
        version_match = re.match(r"ASAP2_VERSION\s+(\d+)\s+(\d+)", clean)
        if version_match:
            asap2 = f"{version_match.group(1)}.{version_match.group(2)}"
        if clean.startswith("BYTE_ORDER "):
            byte_order = clean.split(None, 1)[1]
        if clean.startswith("/begin PROJECT "):
            quoted = _quoted_values(clean)
            project = quoted[0] if quoted else None
        if clean.startswith("/begin MODULE "):
            toks = _atom_tokens(clean)
            if len(toks) > 2:
                module = toks[2].strip('"')
        match = block_pattern.match(line)
        if not match or match.group(1).upper() not in A2L_OBJECT_TYPES:
            continue
        kind = match.group(1).upper()
        header_tokens = _atom_tokens(match.group(2) or "")
        name = header_tokens[0].strip('"') if header_tokens else ""
        depth = 1
        block_lines: list[str] = []
        end_idx = idx
        for end_idx in range(idx + 1, len(lines)):
            current = _clean_line(lines[end_idx])
            if re.match(r"/begin\b", current, re.IGNORECASE):
                depth += 1
            if re.match(r"/end\b", current, re.IGNORECASE):
                depth -= 1
                if depth == 0:
                    break
            block_lines.append(current)
        fields: dict[str, str] = {}
        for field_line in block_lines:
            if not field_line:
                continue
            labeled = re.match(r"/\*\s*([^*]+?)\s*\*/\s*(.*?)\s*$", lines[idx + 1 + block_lines.index(field_line)])
            if labeled:
                label, value = labeled.groups()
                fields.setdefault(label.strip().upper().replace(" ", "_"), value.strip())
            field_match = re.match(r"([A-Z][A-Z0-9_]*)\s*(.*)$", field_line)
            if field_match:
                fields.setdefault(field_match.group(1), field_match.group(2).strip())
        if not name:
            name = fields.get("NAME", "").strip().strip('"')
        if not name:
            continue
        address_text = fields.get("ECU_ADDRESS")
        if not address_text and kind == "CHARACTERISTIC" and fields.get("VALUE"):
            # The first VALUE argument is the ECU address in CHARACTERISTIC syntax.
            address_text = fields["VALUE"].split()[0]
        if not address_text and kind == "CHARACTERISTIC" and fields.get("VAL_BLK"):
            address_text = fields["VAL_BLK"].split()[0]
        try:
            address = int(address_text, 0) if address_text else None
        except ValueError:
            address = None
        tokens = [x.strip('"') for x in _atom_tokens(" ".join(block_lines))]
        data_type = None
        conversion = None
        unit = None
        lower = upper = None
        record_layout = None
        if kind == "MEASUREMENT":
            # Name, long identifier, datatype, conversion, resolution, accuracy, lower, upper.
            if len(header_tokens) >= 1:
                data_type = fields.get("DATA_TYPE")
                conversion = fields.get("CONVERSION_METHOD")
                lower = fields.get("LOWER_LIMIT")
                upper = fields.get("UPPER_LIMIT")
        elif kind == "CHARACTERISTIC":
            value = (fields.get("VALUE") or fields.get("VAL_BLK", "")).split()
            if len(value) >= 4:
                record_layout = value[1]
                conversion = value[3]
                lower = value[4] if len(value) > 4 else None
                upper = value[5] if len(value) > 5 else None
        unit_match = re.search(r"\bPHYS_UNIT\s+\"([^\"]*)\"", "\n".join(block_lines))
        if unit_match:
            unit = unit_match.group(1)
        dimensions = [int(x) for x in re.findall(r"\bMATRIX_DIM\s+(\d+)", "\n".join(block_lines))]
        objects.append(A2LObject(name, kind, address, data_type, conversion, unit, lower, upper,
                                 record_layout, dimensions, idx + 1, fields))
    meta = {"project": project, "module": module, "asap2_version": asap2, "byte_order": byte_order}
    return objects, meta


def parse_map(path: Path) -> list[MapSymbol]:
    symbols: list[MapSymbol] = []
    header_seen = False
    for line_number, line in enumerate(_read_text(path).splitlines(), 1):
        if not header_seen:
            if re.search(r"\bVMA\s+LMA\s+Size\s+Align\b", line):
                header_seen = True
            continue
        # GNU-style map row; address columns are hexadecimal, Size/Align decimal.
        match = re.match(r"^\s*([0-9a-fA-F]+)\s+([0-9a-fA-F]+)\s+([0-9a-fA-F]+)\s+(\d+)\s+(.*?)\s*$", line)
        if not match:
            continue
        vma, lma, size = (int(match.group(i), 16) for i in range(1, 4))
        align = int(match.group(4), 10)
        tail = match.group(5).split()
        if not tail:
            continue
        name = tail[-1]
        section = tail[0] if len(tail) > 1 else ""
        obj = tail[-2] if len(tail) > 2 else ""
        symbols.append(MapSymbol(name, vma, lma, size, align, section, obj, line_number))
    return symbols


def _matches_for_object(obj: A2LObject, maps_by_name: dict[str, list[MapSymbol]],
                        maps_by_addr: dict[int, list[MapSymbol]]) -> dict[str, Any]:
    named = maps_by_name.get(obj.name, [])
    addressed = maps_by_addr.get(obj.address, []) if obj.address is not None else []
    paired = [s for s in named if obj.address in (s.vma, s.lma)] if obj.address is not None else []
    if len(named) > 1 or (obj.address is not None and len(addressed) > 1):
        grade, status = "E", "ambiguous"
        diagnostic = "同名符号或同地址存在多个 MAP 候选，需人工确认"
    elif paired:
        grade, status, diagnostic = "A", "exact", "A2L 名称、地址与 MAP 符号/地址一致"
    elif obj.address is not None and addressed:
        grade, status, diagnostic = "B", "address_only", "A2L 地址在 MAP 中存在，但符号名未精确匹配"
    elif named:
        grade, status, diagnostic = "C", "name_only", "MAP 符号名匹配，但地址缺失或不一致"
    else:
        grade, status, diagnostic = "D", "a2l_only", "A2L 对象未在 MAP 中按名称或地址匹配"
    return {"grade": grade, "match_status": status, "diagnostic": diagnostic,
            "map_name_matches": [s.to_dict() for s in named],
            "map_address_matches": [s.to_dict() for s in addressed]}


def build_index(a2l_path: Path, map_path: Path, *, use_cache: bool = True) -> dict[str, Any]:
    fingerprints = {"a2l": file_fingerprint(a2l_path), "map": file_fingerprint(map_path)}
    cache_path = a2l_path.parent / ".map_a2l_cache.json"
    if use_cache and cache_path.exists():
        try:
            cached = json.loads(cache_path.read_text(encoding="utf-8"))
            if cached.get("schema_version") == 2 and cached.get("fingerprints") == fingerprints:
                return cached
        except (OSError, json.JSONDecodeError):
            pass
    objects, a2l_meta = parse_a2l(a2l_path)
    symbols = parse_map(map_path)
    by_name: dict[str, list[MapSymbol]] = {}
    by_addr: dict[int, list[MapSymbol]] = {}
    for symbol in symbols:
        by_name.setdefault(symbol.name, []).append(symbol)
        by_addr.setdefault(symbol.vma, []).append(symbol)
        if symbol.lma != symbol.vma:
            by_addr.setdefault(symbol.lma, []).append(symbol)
    rows = []
    for obj in objects:
        row = obj.to_dict()
        row.update(_matches_for_object(obj, by_name, by_addr))
        rows.append(row)
    version_verified = False
    result = {
        "schema_version": 2,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "version_status": "未验证：未发现可确认的 MAP/A2L 构建标识",
        "version_verified": version_verified,
        "fingerprints": fingerprints,
        "a2l": {**a2l_meta, "path": str(a2l_path.resolve()), "object_count": len(objects)},
        "map": {"path": str(map_path.resolve()), "symbol_count": len(symbols)},
        "objects": rows,
        "symbols": [s.to_dict() for s in symbols],
        "summary": summarize(rows, symbols),
    }
    if use_cache:
        try:
            cache_path.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
        except OSError:
            pass
    return result


def summarize(objects: list[dict[str, Any]], symbols: list[MapSymbol]) -> dict[str, Any]:
    types: dict[str, int] = {}
    grades: dict[str, int] = {}
    for row in objects:
        types[row["object_type"]] = types.get(row["object_type"], 0) + 1
        grades[row["grade"]] = grades.get(row["grade"], 0) + 1
    addressable = [x for x in objects if x["address"] is not None]
    primary = [x for x in objects if x["object_type"] in {"MEASUREMENT", "CHARACTERISTIC"}]
    unique_primary_names = {x["name"] for x in primary}
    map_names = {x.name for x in symbols}
    measurements = [x for x in objects if x["object_type"] == "MEASUREMENT"]
    unique_measurement_addresses = {x["address"] for x in measurements if x["address"] is not None}
    map_addresses = {address for symbol in symbols for address in (symbol.vma, symbol.lma)}
    return {"a2l_objects": len(objects), "object_types": types, "map_symbols": len(symbols),
            "a2l_objects_with_address": len(addressable),
            "unique_a2l_addresses": len({x["address"] for x in addressable}),
            "address_hits": sum(1 for x in addressable if x["map_address_matches"]),
            "exact_name_hits": sum(1 for x in objects if x["map_name_matches"]),
            "measurement_characteristic_objects": len(primary),
            "measurement_characteristic_unique_names": len(unique_primary_names),
            "measurement_characteristic_unique_name_hits": len(unique_primary_names & map_names),
            "measurement_characteristic_unique_name_misses": sorted(unique_primary_names - map_names),
            "measurement_ecu_address_fields": sum(1 for x in measurements if x["address"] is not None),
            "measurement_unique_addresses": len(unique_measurement_addresses),
            "measurement_unique_address_hits": len(unique_measurement_addresses & map_addresses),
            "grades": grades}


def query_name(
    index: dict[str, Any],
    name: str,
    *,
    fuzzy: bool = False,
    limit: int = 50,
) -> list[dict[str, Any]]:
    query = name.strip().casefold()
    if not query:
        return []
    if not fuzzy:
        return [row for row in index["objects"] if row["name"] == name]
    candidates = []
    for row in index["objects"]:
        candidate = row["name"].casefold()
        if query in candidate:
            score = 1.0 if query == candidate else len(query) / len(candidate)
        else:
            score = difflib.SequenceMatcher(None, query, candidate).ratio()
        if query in candidate or score >= 0.45:
            result = dict(row)
            result["query_score"] = round(score, 4)
            candidates.append(result)
    candidates.sort(key=lambda row: (-row["query_score"], row["name"]))
    return candidates[:limit]


def query_address(index: dict[str, Any], address: int) -> list[dict[str, Any]]:
    found = []
    for row in index["objects"]:
        if row["address"] == address:
            found.append({"source": "A2L", "object": row})
    for symbol in index["symbols"]:
        if address in (int(symbol["vma_hex"], 16), int(symbol["lma_hex"], 16)):
            found.append({"source": "MAP", "symbol": symbol,
                          "address_kind": "VMA+LMA" if symbol["vma"] == symbol["lma"] else
                          "VMA" if address == symbol["vma"] else "LMA"})
    return found


def export_rows(index: dict[str, Any], output: Path, fmt: str, names: Iterable[str] | None = None) -> int:
    selected = set(names) if names is not None else None
    rows = [r for r in index["objects"] if selected is None or r["name"] in selected]
    if fmt == "json":
        payload = {k: v for k, v in index.items() if k != "symbols"}
        payload["objects"] = rows
        output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    else:
        fields = ["name", "object_type", "address_hex", "data_type", "conversion", "unit",
                  "lower_limit", "upper_limit", "record_layout", "dimensions", "grade", "match_status", "diagnostic"]
        with output.open("w", newline="", encoding="utf-8-sig") as stream:
            writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)
    return len(rows)
