import re
from pathlib import Path

from models import A2LObject


_BEGIN = re.compile(r"^\s*/begin\s+(MEASUREMENT|CHARACTERISTIC)(?:\s+(\S+))?")
_FIELD = re.compile(r"^\s*(ECU_ADDRESS|MATRIX_DIM|PHYS_UNIT|COMPU_METHOD|RECORD_LAYOUT|BYTE_ORDER)\s+(.+?)\s*$")


class A2LIndex:
    def __init__(self) -> None:
        self.objects: list[A2LObject] = []
        self.by_name: dict[str, list[A2LObject]] = {}
        self.byte_order = ""
        self.project = ""
        self.module = ""
        self.diagnostics: list[str] = []

    def add(self, obj: A2LObject) -> None:
        self.objects.append(obj)
        self.by_name.setdefault(obj.name, []).append(obj)


def _parse_int(value: str) -> int | None:
    token = value.split()[0]
    try:
        return int(token, 0)
    except ValueError:
        return None


def parse_a2l(path: str | Path) -> A2LIndex:
    index = A2LIndex()
    current: A2LObject | None = None
    depth = 0
    with open(path, "r", encoding="utf-8", errors="replace") as handle:
        for line_number, line in enumerate(handle, 1):
            if line.startswith("  /begin PROJECT "):
                parts = line.split()
                index.project = parts[2] if len(parts) > 2 else ""
            elif line.startswith("    /begin MODULE "):
                parts = line.split()
                index.module = parts[2] if len(parts) > 2 else ""
            begin = _BEGIN.match(line)
            if begin and current is None:
                current = A2LObject(
                    name=begin.group(2) or "",
                    object_type=begin.group(1),
                    source=str(path),
                    line=line_number,
                )
                depth = 1
                continue
            if current is not None:
                labeled = re.match(r'^\s*/\*\s*Name\s*\*/\s*(.*?)\s*$', line, re.IGNORECASE)
                if labeled and not current.name:
                    current.name = labeled.group(1).strip().strip('"')
                    continue
                typed = re.match(r'^\s*/\*\s*Data type\s*\*/\s*(.*?)\s*$', line, re.IGNORECASE)
                if typed:
                    current.data_type = typed.group(1).strip()
                converted = re.match(r'^\s*/\*\s*Conversion method\s*\*/\s*(.*?)\s*$', line, re.IGNORECASE)
                if converted:
                    current.conversion = converted.group(1).strip()
                if re.match(r"^\s*/begin\b", line):
                    depth += 1
                elif re.match(r"^\s*/end\b", line):
                    depth -= 1
                    if depth == 0:
                        if current.name:
                            index.add(current)
                        else:
                            index.diagnostics.append(
                                f"{path}:{current.line}: object has no name"
                            )
                        current = None
                        continue
                field = _FIELD.match(line)
                if field:
                    key, value = field.groups()
                    current.fields[key] = value
                    if key == "ECU_ADDRESS":
                        current.address = _parse_int(value)
                    elif key == "MATRIX_DIM":
                        current.dimensions = tuple(
                            int(item) for item in value.split() if item.isdigit()
                        )
                    elif key == "PHYS_UNIT":
                        current.unit = value.strip('"')
                    elif key in {"COMPU_METHOD", "RECORD_LAYOUT"}:
                        current.conversion = value.split()[0]
                elif line.strip() and not current.fields.get("_header"):
                    header = line.strip()
                    current.fields["_header"] = header
                    parts = header.split()
                    if current.object_type == "MEASUREMENT" and parts:
                        current.data_type = parts[0]
                    elif current.object_type == "CHARACTERISTIC" and len(parts) >= 2:
                        current.data_type = parts[1]
                        if parts[0] in {"VALUE", "CURVE", "MAP", "CUBOID", "CUBE_4", "CUBE_5"}:
                            current.address = _parse_int(parts[1])
                            current.fields["RECORD_LAYOUT"] = parts[2] if len(parts) > 2 else ""
                if "DATA_TYPE" in current.fields:
                    current.data_type = current.fields["DATA_TYPE"].strip()
                continue
            field = _FIELD.match(line)
            if field and field.group(1) == "BYTE_ORDER":
                index.byte_order = field.group(2)
    if current is not None:
        index.diagnostics.append(f"{path}:{current.line}: unterminated {current.object_type}")
    if not index.objects:
        text = Path(path).read_text(encoding="utf-8", errors="replace")
        block_re = re.compile(
            r"(?ms)^\s*/begin\s+(MEASUREMENT|CHARACTERISTIC)\s*$"
            r"(.*?)^\s*/end\s+(MEASUREMENT|CHARACTERISTIC)\s*$"
        )
        for match in block_re.finditer(text):
            body = match.group(2)
            name_match = re.search(r"/\*\s*Name\s*\*/\s*(\S+)", body, re.IGNORECASE)
            name = name_match.group(1).strip('"') if name_match else ""
            if not name:
                continue
            address = None
            address_match = re.search(r"\bECU_ADDRESS\s+(0x[0-9A-Fa-f]+)", body)
            if address_match:
                address = int(address_match.group(1), 16)
            elif match.group(1) == "CHARACTERISTIC":
                value_match = re.search(r"^\s*VALUE\s+(0x[0-9A-Fa-f]+)", body, re.MULTILINE)
                if value_match:
                    address = int(value_match.group(1), 16)
            index.add(
                A2LObject(
                    name=name,
                    object_type=match.group(1),
                    address=address,
                    source=str(path),
                    line=text[:match.start()].count("\n") + 1,
                )
            )
        if index.objects:
            index.diagnostics.clear()
    if not index.objects:
        index.diagnostics.append(f"{path}: no MEASUREMENT or CHARACTERISTIC objects")
    return index
