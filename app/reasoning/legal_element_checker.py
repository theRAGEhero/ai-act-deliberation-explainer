from __future__ import annotations

from app.models import LegalElementResult
from app.reasoning.fact_extractor import CandidateFact


class LegalElementChecker:
    VALID_STATUSES = {"supported", "missing", "uncertain", "contradicted", "exception_possible", "not_applicable"}
    STOP_TOKENS = {
        "system",
        "person",
        "persons",
        "natural",
        "group",
        "groups",
        "targets",
        "uses",
        "true",
        "false",
        "required",
        "context",
        "condition",
    }

    def check(self, candidate_facts: list[CandidateFact], ontology_elements: list[dict]) -> list[LegalElementResult]:
        fact_text = " ".join(f"{fact.id} {fact.label}" for fact in candidate_facts).casefold()
        results: list[LegalElementResult] = []
        for element in ontology_elements:
            label = str(element.get("label") or element.get("id") or "")
            element_id = str(element.get("id") or label)
            evidence = []
            seen_snippets = set()
            for fact in candidate_facts:
                if self._supports(label, element_id, fact_text, fact) and fact.evidence.snippet not in seen_snippets:
                    seen_snippets.add(fact.evidence.snippet)
                    evidence.append(fact.evidence)
            status = "supported" if evidence else "missing"
            results.append(
                LegalElementResult(
                    id=element_id,
                    label=label,
                    source=element.get("source"),
                    element_type=element.get("element_type"),
                    requirement_type=element.get("requirement_type") or "required",
                    status=status,
                    evidence=evidence,
                    missing_question=None if evidence else f"What evidence supports this legal element: {label}?",
                    confidence=max((item.confidence for item in evidence), default=0.0),
                )
            )
        return results

    def _supports(self, label: str, element_id: str, fact_text: str, fact: CandidateFact) -> bool:
        haystack = f"{label} {element_id}".casefold()
        synonyms = {
            "social scoring": ["social scoring", "social score", "social behaviour", "social behavior"],
            "emotion recognition": ["emotion recognition", "infer emotions", "detect emotions"],
            "biometric": ["biometric", "facial recognition", "remote biometric"],
            "profiling": ["profiling", "criminal risk", "risk assessment"],
            "manipulative": ["manipulative", "deceptive", "subliminal", "informed decision"],
            "vulnerability": ["vulnerable", "vulnerability", "disability", "socio-economic"],
            "workplace": ["workplace", "employee", "worker"],
            "education": ["education", "school", "student", "university"],
            "law enforcement": ["law enforcement", "police"],
        }
        snippet = fact.evidence.snippet.casefold()
        if any(key in haystack and any(term in snippet for term in terms) for key, terms in synonyms.items()):
            return True
        tokens = [token for token in haystack.replace("-", " ").split() if len(token) > 4 and token not in self.STOP_TOKENS]
        return any(token in fact_text or token in fact.evidence.snippet.casefold() for token in tokens)
