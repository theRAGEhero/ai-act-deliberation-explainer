from pathlib import Path

from app.analysis.input_processor import build_case_input
from app.analysis.rule_engine import RuleEngine
from app.legal_source.legal_db import LegalKnowledgeDB


def test_rule_engine_employment_ranking():
    db = LegalKnowledgeDB(Path("data/seed_concepts.json"))
    db.load_from_akn(Path("reference/akoma-ntoso/aiAct-2024-1689.xml"))
    engine = RuleEngine(Path("data/seed_annexes.json"), Path("data/seed_concepts.json"), Path("data/seed_prohibitions.json"))
    case = build_case_input("We use AI to rank candidates for jobs using historical data. A human makes the final decision.")
    result = engine.analyze(case, db)
    assert any("employment" in c.label.lower() for c in result.detected_contexts)
    assert any(f.label == "ranking" for f in result.detected_ai_functions)
    assert any(a.label == "affected person" for a in result.detected_actors)
    assert result.matched_prohibited_practices == []
    assert result.possible_risks == []
    source_numbers = {s.article_number for s in result.relevant_ai_act_sources}
    assert source_numbers == {"5"}
    assert any("Article 5" in q for q in result.missing_questions)


def test_rule_engine_social_scoring_uses_article_5_mapping():
    db = LegalKnowledgeDB(Path("data/seed_concepts.json"))
    db.load_from_akn(Path("reference/akoma-ntoso/aiAct-2024-1689.xml"))
    engine = RuleEngine(Path("data/seed_annexes.json"), Path("data/seed_concepts.json"), Path("data/seed_prohibitions.json"))
    text = (
        "The authority uses an AI system for social scoring over time based on social behaviour "
        "and personality characteristics. The score can cause detrimental treatment in public services."
    )
    result = engine.analyze(build_case_input(text), db)
    assert [match.id for match in result.matched_prohibited_practices] == ["social_scoring"]
    match = result.matched_prohibited_practices[0]
    assert match.article_point == "5(1)(c)"
    assert match.affected_rights == ["non-discrimination", "human dignity", "privacy", "fair treatment"]
    assert match.contexts == ["evaluation or classification over a period of time"]
    assert {s.article_number for s in result.relevant_ai_act_sources} == {"5"}
    assert all(t.relevant_source in {"Article 5", "Article 5(1)(c)"} for t in result.traceability)


def test_rule_engine_workplace_emotion_includes_defined_exception():
    db = LegalKnowledgeDB(Path("data/seed_concepts.json"))
    db.load_from_akn(Path("reference/akoma-ntoso/aiAct-2024-1689.xml"))
    engine = RuleEngine(Path("data/seed_annexes.json"), Path("data/seed_concepts.json"), Path("data/seed_prohibitions.json"))
    result = engine.analyze(build_case_input("An AI emotion recognition system will infer emotions of employees in the workplace."), db)
    assert [match.id for match in result.matched_prohibited_practices] == ["emotion_recognition_workplace_education"]
    assert result.matched_prohibited_practices[0].exceptions == ["medical reasons", "safety reasons"]


def test_rule_engine_no_signal():
    db = LegalKnowledgeDB(Path("data/seed_concepts.json"))
    db.load_from_akn(Path("reference/akoma-ntoso/aiAct-2024-1689.xml"))
    engine = RuleEngine(Path("data/seed_annexes.json"), Path("data/seed_concepts.json"), Path("data/seed_prohibitions.json"))
    result = engine.analyze(build_case_input("test"), db)
    assert result.relevant_ai_act_sources == []
    assert result.matched_prohibited_practices == []
    assert result.possible_rights_or_interests == []
    assert result.obligations_to_verify == []
    assert result.traceability == []
