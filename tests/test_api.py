from pathlib import Path

import pytest
from pydantic import ValidationError

from app.main import analyze, health
from app.models import MAX_TEXT_LENGTH, CaseInputRequest


def test_health():
    data = health()
    assert data["status"] == "ok"
    assert data["analysis_available"] is True
    assert data["active_analysis_path"] == "ontology_first_article5"
    assert "akn_validation" in data
    assert "legal_ontology_status" in data
    assert data["legacy_json_rule_path_removed"] is True


def test_index():
    assert "AI Act Prohibitions Checker" in Path("app/templates/index.html").read_text(encoding="utf-8")


def test_analyze():
    response = analyze(CaseInputRequest(text="A public authority uses an AI system for social scoring based on social behaviour and personality characteristics, causing detrimental treatment in access to services."))
    data = response.model_dump()
    assert data["case_summary"] == "Article 5 ontology review produced candidate matches."
    assert [match["id"] for match in data["matched_prohibited_practices"]] == ["DetrimentalSocialScoring"]
    assert data["matched_prohibited_practices"][0]["article_point"] == "5(1)(c)"
    assert data["matched_prohibited_practices"][0]["source_anchors"][0]["eId"] == "chp_II__art_5__para_1__list_1__point_c"
    assert "analysis_unavailable" not in data["raw_rule_output"]
    assert "Ontology-first path used. No JSON rule fallback was used." in data["notes"]


def test_remote_biometric_input_does_not_trigger_sensitive_categorisation_without_sensitive_inference():
    response = analyze(
        CaseInputRequest(
            text=(
                "Police use a real-time remote biometric identification system in a publicly accessible space to find a missing child. "
                "The deployment is strictly necessary and limited by time, geography and persons. "
                "A judicial authority authorises it before use."
            )
        )
    )
    ids = [match.id for match in response.matched_prohibited_practices]
    assert "RealTimeRemoteBiometricIdentificationInPublicSpacesForLawEnforcement" in ids
    assert "SensitiveBiometricCategorisation" not in ids
    real_time = next(match for match in response.matched_prohibited_practices if match.id == "RealTimeRemoteBiometricIdentificationInPublicSpacesForLawEnforcement")
    condition_statuses = {element.label: element.status for element in real_time.legal_elements if element.label.startswith("requires Condition:")}
    assert condition_statuses["requires Condition: Strict necessity"] == "supported"
    assert condition_statuses["requires Condition: Temporal limitation"] == "supported"
    assert condition_statuses["requires Condition: Geographic limitation"] == "supported"
    assert condition_statuses["requires Condition: Personal limitation"] == "supported"
    assert condition_statuses["requires Condition: Annual reporting to Commission"] == "missing"


def test_university_emotion_inference_maps_to_education_not_workplace():
    response = analyze(CaseInputRequest(text="I am studying at UNIBO and my professor has access to an AI system that infers my emotions"))
    ids = [match.id for match in response.matched_prohibited_practices]
    assert ids == ["EmotionRecognitionInEducation"]
    match = response.matched_prohibited_practices[0]
    statuses = {element.label: element.status for element in match.legal_elements}
    assert statuses["uses System: Emotion recognition AI system"] == "supported"
    assert statuses["targets: Student"] == "supported"
    assert statuses["occurs In Context: Education institution"] == "supported"
    assert response.missing_questions == []


def test_weak_input_does_not_create_legal_map():
    response = analyze(CaseInputRequest(text="test"))
    assert response.matched_prohibited_practices == []
    assert response.case_summary == "No Article 5 ontology-supported match was detected."
    assert response.possible_rights_or_interests == []
    assert response.obligations_to_verify == []
    assert response.traceability == []


def test_input_length_is_limited():
    with pytest.raises(ValidationError):
        CaseInputRequest(text="x" * (MAX_TEXT_LENGTH + 1))
