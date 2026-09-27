import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))

from a2l_parser import parse_a2l
from map_parser import parse_map
from matcher import match_indexes


ROOT = Path(__file__).parents[2]
MAP = ROOT / "CMP_TZCU_0.0.0_9110100VC20000_A.map"
A2L = ROOT / "full_CMP_0.0.0_CANApe_0923.a2l"


def test_sample_target_matches():
    records = match_indexes(parse_a2l(A2L), parse_map(MAP))
    target = next(record for record in records if record.name == "CIL_3rModFlapMotCtr")
    assert target.a2l_address == 0xB0056364
    assert target.map_vma == 0xB0056364
    assert target.status == "A"


def test_sample_address_coverage():
    a2l = parse_a2l(A2L)
    map_index = parse_map(MAP)
    measurement_addresses = {
        obj.address
        for obj in a2l.objects
        if obj.object_type == "MEASUREMENT" and obj.address is not None
    }
    assert len(measurement_addresses) == 890
    assert sum(
        address in map_index.by_vma or address in map_index.by_lma
        for address in measurement_addresses
    ) == 890


def test_empty_a2l_is_diagnosed():
    index = parse_a2l(ROOT / "CEA2_TZCU" / "full_CMP_0.0.0_CANApe_0923.a2l")
    assert not index.objects
    assert index.diagnostics
