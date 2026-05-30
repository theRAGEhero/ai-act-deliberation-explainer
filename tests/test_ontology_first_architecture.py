from pathlib import Path

from app.analysis.input_processor import build_case_input
from app.legal_source.akn_validator import validate_akn_xml
from app.legal_source.source_index import LegalSourceIndex
from app.ontology.legal_ontology_store import LegalOntologyStore
from app.reasoning.article5_reasoner import Article5Reasoner


ROOT = Path(__file__).resolve().parent.parent
AKN = ROOT / "reference/akoma-ntoso/aiAct-2024-1689.xml"
XSD = ROOT / "reference/akoma-ntoso/akomantoso30.xsd"
XML_XSD = ROOT / "reference/akoma-ntoso/xml.xsd"
FIXTURE_ONTOLOGY = ROOT / "tests/fixtures/ontology"


def test_akn_validator_reports_valid_or_controlled_problem():
    result = validate_akn_xml(AKN, XSD, XML_XSD)
    assert result.xml_path.endswith("aiAct-2024-1689.xml")
    assert result.xsd_path.endswith("akomantoso30.xsd")
    assert result.attempted or result.warnings
    if result.attempted:
        assert result.is_valid or result.errors


def test_akn_validator_malformed_xml_fails_cleanly(tmp_path):
    malformed = tmp_path / "bad.xml"
    malformed.write_text("<akomaNtoso><broken></akomaNtoso>", encoding="utf-8")
    result = validate_akn_xml(malformed, XSD, XML_XSD)
    assert result.attempted
    assert not result.is_valid
    assert result.errors


def test_source_index_finds_article_5_and_point_c():
    index = LegalSourceIndex(AKN)
    article = index.get_article("5")
    assert article is not None
    assert article.eId == "chp_II__art_5"
    point_c = index.get_article_point("5", "1", "c")
    assert point_c is not None
    assert point_c.eId == "chp_II__art_5__para_1__list_1__point_c"


def test_source_index_finds_article_5_nested_h_points():
    index = LegalSourceIndex(AKN)
    nested = [point for point in index.get_article_5_points() if point.point in {"h.i", "h.ii", "h.iii"}]
    assert {point.point for point in nested} == {"h.i", "h.ii", "h.iii"}
    assert all(point.eId and "point_h__list_1__point_" in point.eId for point in nested)


def test_source_index_extracts_article_3_definitions():
    index = LegalSourceIndex(AKN)
    definitions = index.get_article_3_definitions()
    assert definitions
    assert index.get_definition_by_number("1") is not None
    assert index.get_definition_by_term("AI system") is not None


def test_legal_ontology_store_loads_minimal_fixture():
    store = LegalOntologyStore(FIXTURE_ONTOLOGY)
    assert store.status.loaded
    assert store.status.is_valid
    assert store.get_prohibited_practices()
    assert store.get_required_elements("FixtureSocialScoringPractice")


def test_legal_ontology_store_loads_reviewed_cirsfid_ontology():
    store = LegalOntologyStore(ROOT / "data/ontology")
    assert store.status.loaded
    assert store.status.is_valid
    assert store.status.warnings
    assert any(item["id"] == "DetrimentalSocialScoring" for item in store.get_prohibited_practices())
    assert store.get_required_elements("DetrimentalSocialScoring")
    assert store.get_source_anchors("DetrimentalSocialScoring")[0]["label"] == "Article 5(1)(c)"
    assert store.get_source_anchors("DetrimentalSocialScoring")[0]["legal_status"] == "current_binding_law"
    assert store.is_current_law_practice("DetrimentalSocialScoring")
    assert not store.is_current_law_practice("IntendedScalableNonConsensualIntimateDeepfakeGenerator")


def test_legal_ontology_store_fails_without_required_vocabulary(tmp_path):
    (tmp_path / "bad.ttl").write_text("@prefix aid: <http://example.org/ai-act-deliberation#> .\naid:Thing aid:label \"bad\" .\n", encoding="utf-8")
    store = LegalOntologyStore(tmp_path)
    assert not store.status.is_valid
    assert store.status.errors


def test_article5_reasoner_fails_closed_when_ontology_missing(tmp_path):
    validation = validate_akn_xml(AKN, XSD, XML_XSD)
    index = LegalSourceIndex(AKN) if validation.is_valid else None
    store = LegalOntologyStore(tmp_path / "missing")
    result = Article5Reasoner(store, index, validation).analyze(build_case_input("AI social scoring system"))
    assert result.case_summary == "Legal analysis unavailable"
    assert "analysis_unavailable" in result.notes
    assert result.matched_prohibited_practices == []


def test_article5_reasoner_does_not_depend_on_legacy_json_rules(tmp_path):
    validation = validate_akn_xml(AKN, XSD, XML_XSD)
    if not validation.is_valid:
        return
    index = LegalSourceIndex(AKN)
    store = LegalOntologyStore(FIXTURE_ONTOLOGY)
    result = Article5Reasoner(store, index, validation).analyze(build_case_input("An AI social scoring system is used."))
    assert all("seed_prohibitions" not in note for note in result.notes)
    assert "Ontology-first path used. No JSON rule fallback was used." in result.notes


def test_article5_reasoner_uses_reviewed_ontology_source_anchor():
    validation = validate_akn_xml(AKN, XSD, XML_XSD)
    if not validation.is_valid:
        return
    index = LegalSourceIndex(AKN)
    store = LegalOntologyStore(ROOT / "data/ontology")
    result = Article5Reasoner(store, index, validation).analyze(
        build_case_input("A public authority uses an AI system for social scoring based on social behaviour and detrimental treatment.")
    )
    assert [match.id for match in result.matched_prohibited_practices] == ["DetrimentalSocialScoring"]
    match = result.matched_prohibited_practices[0]
    assert match.article_point == "5(1)(c)"
    assert match.source_anchors[0].eId == "chp_II__art_5__para_1__list_1__point_c"
    assert match.legal_basis_status == "current_binding_law"
    assert match.source_anchors[0].legal_status == "current_binding_law"
    assert match.legal_elements


def test_article5_reasoner_exposes_exception_conditions_from_reviewed_ontology():
    validation = validate_akn_xml(AKN, XSD, XML_XSD)
    if not validation.is_valid:
        return
    index = LegalSourceIndex(AKN)
    store = LegalOntologyStore(ROOT / "data/ontology")
    result = Article5Reasoner(store, index, validation).analyze(
        build_case_input("Police use a real-time remote biometric identification system in a publicly accessible space.")
    )
    matches = {match.id: match for match in result.matched_prohibited_practices}
    assert "RealTimeRemoteBiometricIdentificationInPublicSpacesForLawEnforcement" in matches
    match = matches["RealTimeRemoteBiometricIdentificationInPublicSpacesForLawEnforcement"]
    assert match.exception_results
    assert any(condition.label.startswith("requires Condition:") for condition in match.legal_elements)
    assert all(anchor.legal_status == "current_binding_law" for anchor in match.source_anchors)
