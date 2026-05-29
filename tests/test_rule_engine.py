from pathlib import Path

from app.analysis.input_processor import build_case_input
from app.analysis.rule_engine import RuleEngine
from app.legal_source.legal_db import LegalKnowledgeDB


def test_rule_engine_employment_ranking():
    db = LegalKnowledgeDB(Path("data/seed_concepts.json"))
    db.load_from_akn(Path("data/aiACT.xml"))
    engine = RuleEngine(Path("data/seed_annexes.json"), Path("data/seed_concepts.json"))
    case = build_case_input("We use AI to rank candidates for jobs using historical data. A human makes the final decision.")
    result = engine.analyze(case, db)
    assert any("employment" in c.label.lower() for c in result.detected_contexts)
    assert any(f.label == "ranking" for f in result.detected_ai_functions)
    assert any(a.label == "affected person" for a in result.detected_actors)
    assert any(r.label == "bias" for r in result.possible_risks)
    assert any(r.label == "automation bias" for r in result.possible_risks)
    source_numbers = {s.article_number for s in result.relevant_ai_act_sources}
    assert {"13", "14"}.issubset(source_numbers)
    assert any("contest" in q.lower() for q in result.missing_questions)
