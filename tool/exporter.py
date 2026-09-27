import csv
import json
from pathlib import Path

from models import MatchRecord


def _address(value: int | None) -> str:
    return "" if value is None else f"0x{value:X}"


def record_dict(record: MatchRecord) -> dict:
    return {
        "name": record.name,
        "object_type": record.object_type,
        "a2l_address": _address(record.a2l_address),
        "map_vma": _address(record.map_vma),
        "map_lma": _address(record.map_lma),
        "size": record.size,
        "status": record.status,
        "diagnostics": "; ".join(record.diagnostics),
    }


def export_json(records: list[MatchRecord], path: str | Path) -> None:
    Path(path).write_text(json.dumps([record_dict(r) for r in records], indent=2), encoding="utf-8")


def export_csv(records: list[MatchRecord], path: str | Path) -> None:
    rows = [record_dict(r) for r in records]
    with Path(path).open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]) if rows else ["name"])
        writer.writeheader()
        writer.writerows(rows)
