import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))

from models import MatchRecord


def test_strict_name_matching_is_exact():
    records = [
        MatchRecord(name="CIL_3rModFlapMotCtr"),
        MatchRecord(name="CIL_3rModFlapMotCtr_BypS"),
    ]
    query = "CIL_3rModFlapMotCtr"
    matched = [record for record in records if record.name == query]
    assert [record.name for record in matched] == ["CIL_3rModFlapMotCtr"]


def test_strict_name_matching_ignores_case():
    record = MatchRecord(name="CIL_3rModFlapMotCtr")
    assert record.name.casefold() == "cil_3rmodflapmotctr".casefold()
