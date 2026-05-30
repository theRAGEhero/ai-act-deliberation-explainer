from __future__ import annotations

import json
import re
from typing import Any

from app.config import settings
from app.analysis.prompt_templates import FACT_EXTRACTION_SYSTEM_PROMPT, FACT_EXTRACTION_USER_PROMPT, SYSTEM_PROMPT, USER_PROMPT
from app.models import CandidateFact, EvidenceSupport


class OptionalLLMAgent:
    FACT_CANDIDATES = {
        "AISystem": {
            "id": "ai_system",
            "label": "AI system",
            "type": "system_or_function",
            "terms": ["ai", "ai system", "artificial intelligence", "algorithm", "automated", "model", "machine learning"],
        },
        "CameraMonitoring": {
            "id": "camera_monitoring",
            "label": "camera-based monitoring",
            "type": "context",
            "terms": ["camera", "cameras", "cctv", "video", "monitor", "surveillance"],
        },
        "AnimalPlantTarget": {
            "id": "animal_plant_target",
            "label": "animals or plants as stated target",
            "type": "target",
            "terms": ["animal", "animals", "plant", "plants", "crop", "crops", "livestock"],
        },
        "Workplace": {
            "id": "workplace_context",
            "label": "workplace context",
            "type": "context",
            "terms": ["workplace", "worker", "workers", "employee", "employees", "boss", "manager", "farm", "orchard", "stable", "cooperative", "field manager"],
        },
        "Worker": {
            "id": "worker_target",
            "label": "worker",
            "type": "target",
            "terms": ["worker", "workers", "employee", "employees", "staff", "farmhand", "farmhands"],
        },
        "EmotionRecognitionSystem": {
            "id": "emotion_recognition_text",
            "label": "emotion recognition text",
            "type": "system_or_function",
            "terms": ["emotion", "emotions", "emotional", "infer emotions", "detect emotions"],
        },
        "BiometricData": {
            "id": "biometric",
            "label": "biometric data",
            "type": "system_or_function",
            "terms": ["biometric", "face recognition", "facial recognition"],
        },
        "BiometricCategorisationSystem": {
            "id": "biometric_categorisation_text",
            "label": "biometric categorisation text",
            "type": "system_or_function",
            "terms": ["biometric categorisation", "biometric categorization", "infer race", "sexual orientation", "political opinions"],
        },
        "SocialScoringSystem": {
            "id": "social_scoring_text",
            "label": "social scoring text",
            "type": "system_or_function",
            "terms": ["social score", "social scoring", "social behaviour", "social behavior"],
        },
    }

    def available(self) -> bool:
        return bool(settings.openrouter_api_key)

    def extract_candidate_facts(self, input_text: str) -> list[CandidateFact]:
        if not self.available():
            return []
        try:
            payload = self._complete_json(
                FACT_EXTRACTION_SYSTEM_PROMPT,
                FACT_EXTRACTION_USER_PROMPT.format(
                    input_text=input_text,
                    allowed_candidates=json.dumps(sorted(self.FACT_CANDIDATES), ensure_ascii=False),
                ),
            )
        except Exception:
            return []
        return self._validated_candidate_facts(input_text, payload)

    def refine(self, input_text: str, preliminary: dict[str, Any], legal_sources: list[dict[str, Any]], ontology_concepts: list[str]) -> dict[str, Any] | None:
        if not self.available():
            return None
        try:
            prompt = USER_PROMPT.format(
                input_text=input_text,
                preliminary_json=json.dumps(preliminary, ensure_ascii=False),
                legal_sources=json.dumps(legal_sources, ensure_ascii=False),
                ontology_concepts=json.dumps(ontology_concepts, ensure_ascii=False),
            )
            return self._complete_json(SYSTEM_PROMPT, prompt)
        except Exception:
            return None

    def _complete_json(self, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        from openai import OpenAI

        client = OpenAI(
            api_key=settings.openrouter_api_key,
            base_url=settings.openrouter_base_url,
            default_headers={
                "HTTP-Referer": settings.openrouter_site_url,
                "X-OpenRouter-Title": settings.openrouter_app_title,
            },
        )
        response = client.chat.completions.create(
            model=settings.openrouter_model,
            response_format={"type": "json_object"},
            messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
            temperature=0.1,
        )
        return json.loads(response.choices[0].message.content or "{}")

    def _validated_candidate_facts(self, input_text: str, payload: dict[str, Any]) -> list[CandidateFact]:
        facts = []
        for item in payload.get("candidate_facts", []):
            candidate = str(item.get("ontology_candidate") or "").strip()
            config = self.FACT_CANDIDATES.get(candidate)
            evidence = re.sub(r"\s+", " ", str(item.get("evidence") or item.get("snippet") or "")).strip()
            if not config or not evidence or evidence.casefold() not in re.sub(r"\s+", " ", input_text).casefold():
                continue
            if not any(term in evidence.casefold() for term in config["terms"]):
                continue
            confidence = item.get("confidence", 0.45)
            try:
                confidence = max(0.0, min(float(confidence), 0.75))
            except (TypeError, ValueError):
                confidence = 0.45
            facts.append(
                CandidateFact(
                    id=config["id"],
                    label=config["label"],
                    type=config["type"],
                    ontology_candidate=candidate,
                    evidence=EvidenceSupport(snippet=evidence, source="llm", confidence=confidence),
                    confidence=confidence,
                    provenance="llm_suggested",
                    note="LLM-suggested candidate fact accepted only as evidence input; legal validation remains ontology-gated.",
                )
            )
        return facts
