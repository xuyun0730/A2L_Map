from dataclasses import dataclass, field
from typing import Optional


@dataclass
class MapSymbol:
    name: str
    vma: int
    lma: int
    size: int
    align: int
    section: str = ""
    source: str = ""
    line: int = 0


@dataclass
class A2LObject:
    name: str
    object_type: str
    address: Optional[int] = None
    data_type: str = ""
    conversion: str = ""
    unit: str = ""
    lower_limit: str = ""
    upper_limit: str = ""
    dimensions: tuple[int, ...] = ()
    source: str = ""
    line: int = 0
    fields: dict[str, str] = field(default_factory=dict)


@dataclass
class MatchRecord:
    name: str
    object_type: str = ""
    a2l_address: Optional[int] = None
    map_symbols: list[MapSymbol] = field(default_factory=list)
    status: str = "D"
    diagnostics: list[str] = field(default_factory=list)
    a2l: Optional[A2LObject] = None

    @property
    def map_vma(self) -> Optional[int]:
        return self.map_symbols[0].vma if self.map_symbols else None

    @property
    def map_lma(self) -> Optional[int]:
        return self.map_symbols[0].lma if self.map_symbols else None

    @property
    def size(self) -> Optional[int]:
        return self.map_symbols[0].size if self.map_symbols else None

    @property
    def grade_explanation(self) -> str:
        return {
            "A": "完全一致：A2L 名称和地址均与 MAP 符号/VMA/LMA 一致",
            "B": "地址匹配：A2L 地址命中 MAP，但符号名称未精确匹配",
            "C": "名称匹配：MAP 符号名称命中，但 A2L 地址缺失或不一致",
            "D": "未匹配：A2L 对象未按名称或地址命中 MAP",
            "E": "存在歧义：同名或同地址有多个候选，需人工确认",
        }.get(self.status, "未知等级")
