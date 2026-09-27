import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))

from models import MatchRecord


def test_grade_explanations_are_explicit():
    expected = {"A", "B", "C", "D", "E"}
    explanations = {
        MatchRecord(name="sample", status=grade).grade_explanation
        for grade in expected
    }
    assert len(explanations) == len(expected)
    assert all("：" in explanation for explanation in explanations)
