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
        "requires",
        "biometric",
        "database",
        "identification",
        "recognition",
        "remote",
        "public",
        "spaces",
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
        snippet = fact.evidence.snippet.casefold()
        if "biometric categorisation" in haystack or "biometric categorization" in haystack:
            return any(term in snippet for term in ["biometric categorisation", "biometric categorization", "categorise", "categorize", "categorisation", "categorization"])
        if "infers characteristic" in haystack:
            return any(term in snippet for term in ["infer race", "political opinions", "trade union", "religious beliefs", "philosophical beliefs", "sex life", "sexual orientation"])
        if "requires condition" in haystack:
            return self._supports_condition(haystack, snippet)
        synonyms = {
            "social scoring": ["social scoring", "social score", "social behaviour", "social behavior"],
            "emotion recognition": ["emotion recognition", "infer emotions", "infers my emotions", "infers emotions", "detect emotions", "detects emotions"],
            "real-time remote biometric": ["real-time remote biometric", "remote biometric identification", "live facial recognition"],
            "facial recognition database": ["facial recognition database", "facial images", "scraping", "scrape"],
            "profiling": ["profiling", "criminal risk", "risk assessment"],
            "manipulative": ["manipulative", "deceptive", "subliminal", "informed decision"],
            "vulnerability": ["vulnerable", "vulnerability", "disability", "socio-economic"],
            "workplace": ["workplace", "employee", "worker"],
            "student": ["student", "studying", "study at", "university", "unibo"],
            "education": ["education", "school", "student", "studying", "study at", "university", "professor", "teacher", "classroom", "course", "unibo"],
            "law enforcement": ["law enforcement", "police"],
        }
        if any(key in haystack and any(term in snippet for term in terms) for key, terms in synonyms.items()):
            return True
        tokens = [token for token in haystack.replace("-", " ").split() if len(token) > 4 and token not in self.STOP_TOKENS]
        return any(token in fact_text or token in fact.evidence.snippet.casefold() for token in tokens)

    def _supports_condition(self, haystack: str, snippet: str) -> bool:
        condition_terms = {
            "strict necessity": ["strictly necessary", "strict necessity"],
            "harm seriousness": ["seriousness", "probability", "scale of harm", "harm scale"],
            "right based proportionality": ["proportionate", "proportionality", "fundamental rights"],
            "contextual proportionality": ["contextual proportionality", "context of use"],
            "national law authorisation": ["judicial authority authorises", "judicial authority authorizes", "prior authorisation", "prior authorization", "national law authorisation", "national law authorization"],
            "fundamental rights impact assessment": ["fundamental rights impact assessment", "fria"],
            "eu database registration": ["eu database", "database registration"],
            "temporal limitation": ["limited by time", "time limit", "temporal limitation"],
            "geographic limitation": ["limited by geography", "geography and persons", "time, geography", "geographic limitation", "geographical limitation"],
            "personal limitation": ["limited by persons", "geography and persons", "personal limitation"],
            "no solely automated adverse decision": ["not solely automated", "human decision", "human review"],
            "notification to authorities": ["notification to authorities", "notify authorities", "notified authorities"],
            "annual reporting": ["annual reporting", "reporting to commission"],
            "report publication": ["report publication", "published report", "public report"],
        }
        for key, terms in condition_terms.items():
            if key in haystack:
                return any(term in snippet for term in terms)
        return False
