import re
from collections import defaultdict
from pathlib import Path

from models import MapSymbol


_ROW = re.compile(
    r"^\s*([0-9A-Fa-f]+)\s+([0-9A-Fa-f]+)\s+([0-9A-Fa-f]+)\s+([0-9A-Fa-f]+)\s+(.*\S)\s*$"
)


class MapIndex:
    def __init__(self) -> None:
        self.symbols: list[MapSymbol] = []
        self.by_name: dict[str, list[MapSymbol]] = defaultdict(list)
        self.by_vma: dict[int, list[MapSymbol]] = defaultdict(list)
        self.by_lma: dict[int, list[MapSymbol]] = defaultdict(list)

    def add(self, symbol: MapSymbol) -> None:
        self.symbols.append(symbol)
        self.by_name[symbol.name].append(symbol)
        self.by_vma[symbol.vma].append(symbol)
        self.by_lma[symbol.lma].append(symbol)


def parse_map(path: str | Path) -> MapIndex:
    index = MapIndex()
    section = ""
    source = str(path)
    with open(path, "r", encoding="utf-8", errors="replace") as handle:
        for line_number, line in enumerate(handle, 1):
            match = _ROW.match(line)
            if not match:
                if line.strip() and not line.startswith(" "):
                    section = line.strip()
                continue
            vma, lma, size, align, remainder = match.groups()
            parts = remainder.split()
            if not parts:
                continue
            name = parts[-1]
            index.add(
                MapSymbol(
                    name=name,
                    vma=int(vma, 16),
                    lma=int(lma, 16),
                    size=int(size, 16),
                    align=int(align, 16),
                    section=section,
                    source=source,
                    line=line_number,
                )
            )
    return index
