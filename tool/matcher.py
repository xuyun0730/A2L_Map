from a2l_parser import A2LIndex
from map_parser import MapIndex
from models import MatchRecord


def normalize_address(value: int | str) -> int:
    if isinstance(value, int):
        return value
    return int(value.strip().lower().removeprefix("0x"), 16)


def match_indexes(a2l: A2LIndex, map_index: MapIndex) -> list[MatchRecord]:
    records: list[MatchRecord] = []
    for obj in a2l.objects:
        symbols = list(map_index.by_name.get(obj.name, ()))
        if obj.address is not None:
            symbols_by_address = map_index.by_vma.get(obj.address, [])
            if not symbols:
                symbols = list(symbols_by_address)
        record = MatchRecord(
            name=obj.name,
            object_type=obj.object_type,
            a2l_address=obj.address,
            map_symbols=symbols,
            a2l=obj,
        )
        if len(a2l.by_name.get(obj.name, ())) > 1 or len(symbols) > 1:
            record.status = "E"
            record.diagnostics.append("同名或同地址存在多个候选")
        elif obj.address is not None and symbols:
            if any(s.vma == obj.address or s.lma == obj.address for s in symbols):
                record.status = "A" if any(s.name == obj.name for s in symbols) else "B"
            else:
                record.status = "C"
                record.diagnostics.append("A2L 地址与 MAP 地址不一致")
        elif symbols:
            record.status = "C"
            record.diagnostics.append("A2L 地址缺失")
        elif obj.address is not None:
            record.status = "B"
            record.diagnostics.append("A2L 地址未按 MAP 符号名称命中")
        else:
            record.status = "D"
            record.diagnostics.append("A2L 对象无地址且未命中 MAP 符号")
        records.append(record)
    return records
