from pathlib import Path

import pytest
from pydantic import ValidationError

from app.main import analyze, health
from app.models import MAX_TEXT_LENGTH, CaseInputRequest


def test_health():
    assert health()["status"] == "ok"


def test_index():
    assert "AI Act Prohibitions Checker" in Path("app/templates/index.html").read_text(encoding="utf-8")


def test_analyze():
    response = analyze(CaseInputRequest(text="A public authority uses an AI system for social scoring based on social behaviour and personality characteristics, causing detrimental treatment in access to services."))
    data = response.model_dump()
    assert "preliminary legal-design analysis" in data["disclaimer"]
    assert data["matched_prohibited_practices"][0]["id"] == "social_scoring"
    assert {source["article_number"] for source in data["relevant_ai_act_sources"]} == {"5"}


def test_weak_input_does_not_create_legal_map():
    response = analyze(CaseInputRequest(text="test"))
    assert response.relevant_ai_act_sources == []
    assert response.matched_prohibited_practices == []
    assert response.possible_rights_or_interests == []
    assert response.obligations_to_verify == []
    assert response.traceability == []


def test_input_length_is_limited():
    with pytest.raises(ValidationError):
        CaseInputRequest(text="x" * (MAX_TEXT_LENGTH + 1))
