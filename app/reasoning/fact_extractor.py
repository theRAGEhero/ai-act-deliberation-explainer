from __future__ import annotations

import re

from app.models import CandidateFact, EvidenceSupport


class FactExtractor:
    """Extract factual text signals without legal classification."""

    PATTERNS = {
        "ai_system": r"\b(ai system|artificial intelligence|algorithm|automated|machine learning|model)\b",
        "biometric": r"\b(biometric|facial recognition|face recognition|remote identification)\b",
        "social_scoring_text": r"\b(social score|social scoring|social behaviour|social behavior|classif(?:y|ies|ication)|evaluat(?:e|es|ion))\b",
        "emotion_recognition_text": r"\b(emotion recognition|infer(?:s|ring)? (?:my |their |a person's |people's )?emotions?|detect(?:s|ing)? (?:my |their |a person's |people's )?emotions?)\b",
        "manipulation_text": r"\b(subliminal|manipulative|deceptive|distort behaviour|distort behavior|informed decision|harm)\b",
        "vulnerability_text": r"\b(vulnerab(?:le|ility)|age|disability|socio-economic|social or economic|exploit)\b",
        "profiling_text": r"\b(profiling|personality traits|criminal risk|risk assessment)\b",
        "facial_scraping_text": r"\b(scraping|scrape|facial images|facial recognition database|cctv)\b",
        "biometric_categorisation_text": r"\b(biometric categorisation|biometric categorization|infer race|political opinions|religious beliefs|sexual orientation)\b",
        "real_time_remote_biometric_text": r"\b(real-time remote biometric|remote biometric identification|publicly accessible space|live facial recognition)\b",
        "law_enforcement_context": r"\b(police|law enforcement|criminal offence|criminal offense)\b",
        "strict_necessity_text": r"\b(strictly necessary|strict necessity)\b",
        "temporal_limitation_text": r"\b(limited by time|time limit|temporal limitation)\b",
        "geographic_limitation_text": r"\b(limited by geography|geographic limitation|geographical limitation)\b",
        "personal_limitation_text": r"\b(limited by persons|personal limitation)\b",
        "authorisation_text": r"\b(judicial authority authorises|judicial authority authorizes|prior authorisation|prior authorization|national law authorisation|national law authorization)\b",
        "workplace_context": r"\b(workplace|employee|worker|job|employment)\b",
        "education_context": r"\b(school|student|studying|study at|education|university|professor|teacher|classroom|course|unibo)\b",
    }

    def extract(self, text: str) -> list[CandidateFact]:
        facts: list[CandidateFact] = []
        for fact_id, pattern in self.PATTERNS.items():
            match = re.search(pattern, text, flags=re.I)
            if match:
                facts.append(
                    CandidateFact(
                        id=fact_id,
                        label=fact_id.replace("_", " "),
                        type=self._type_for(fact_id),
                        ontology_candidate=self._ontology_candidate_for(fact_id),
                        evidence=EvidenceSupport(snippet=self._snippet(text, match.start(), match.end()), source="input", confidence=0.55),
                        confidence=0.55,
                        provenance="deterministic",
                    )
                )
        return facts

    def merge(self, deterministic: list[CandidateFact], suggested: list[CandidateFact] | None = None) -> list[CandidateFact]:
        merged: list[CandidateFact] = []
        seen: set[tuple[str, str, str]] = set()
        for fact in [*deterministic, *(suggested or [])]:
            key = (fact.id, re.sub(r"\s+", " ", fact.evidence.snippet).casefold(), fact.provenance)
            if key not in seen:
                seen.add(key)
                merged.append(fact)
        return merged

    def _snippet(self, text: str, start: int, end: int) -> str:
        left = max(0, start - 100)
        right = min(len(text), end + 100)
        return re.sub(r"\s+", " ", text[left:right]).strip()

    def _type_for(self, fact_id: str) -> str:
        if "context" in fact_id:
            return "context"
        if "target" in fact_id:
            return "target"
        if "condition" in fact_id or "limitation" in fact_id or "authorisation" in fact_id:
            return "condition"
        if "system" in fact_id or "text" in fact_id or fact_id == "biometric":
            return "system_or_function"
        return "signal"

    def _ontology_candidate_for(self, fact_id: str) -> str | None:
        candidates = {
            "ai_system": "AISystem",
            "biometric": "BiometricData",
            "social_scoring_text": "SocialScoringSystem",
            "emotion_recognition_text": "EmotionRecognitionSystem",
            "facial_scraping_text": "FacialRecognitionDatabaseScraper",
            "biometric_categorisation_text": "BiometricCategorisationSystem",
            "real_time_remote_biometric_text": "RealTimeRemoteBiometricIdentificationSystem",
            "law_enforcement_context": "LawEnforcementContext",
            "workplace_context": "Workplace",
            "education_context": "EducationInstitution",
        }
        return candidates.get(fact_id)
