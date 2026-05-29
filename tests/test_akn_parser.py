from pathlib import Path

from app.legal_source.akn_parser import AKNParser


def test_missing_file_no_crash(tmp_path):
    corpus = AKNParser().parse_file(tmp_path / "missing.xml")
    assert corpus.articles == []
    assert corpus.warnings


def test_parser_loads_ai_act_if_present():
    path = Path("data/aiACT.xml")
    corpus = AKNParser().parse_file(path)
    if path.exists():
        assert len(corpus.articles) > 0
        numbers = {a.number for a in corpus.articles}
        for number in ["3", "13", "14", "27", "50", "86"]:
            assert number in numbers
