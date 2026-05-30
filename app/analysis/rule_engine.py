from __future__ import annotations

import json
from pathlib import Path

from app.models import CaseInput, DetectedItem, LegalSourceRef, PreliminaryAnalysis, ProhibitedPracticeMatch, TraceabilityItem


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8")) if path and path.exists() and path.is_file() else {}


class RuleEngine:
    def __init__(self, seed_annexes_path: Path, seed_concepts_path: Path, seed_prohibitions_path: Path | None = None):
        self.annex = _load_json(seed_annexes_path).get("annex_iii", [])
        self.seed = _load_json(seed_concepts_path)
        self.prohibitions = _load_json(seed_prohibitions_path or Path()).get("article_5_prohibited_practices", [])

    def analyze(self, case_input: CaseInput, legal_db, ontology_store=None) -> PreliminaryAnalysis:
        text = case_input.raw_text.lower()
        claims = case_input.claims or [case_input.raw_text]
        contexts = self._detect_contexts(text)
        functions = self._detect_functions(text)
        actors = self._detect_actors(text)
        prohibition_matches = self._detect_prohibited_practices(text)
        risks = self._detect_risks(text, prohibition_matches)
        if not self._has_ai_act_signal(text, contexts, functions, risks, prohibition_matches):
            return PreliminaryAnalysis(
                case_summary="No sufficient AI Act signal was detected in the submitted text.",
                matched_prohibited_practices=[],
                detected_actors=actors,
                detected_contexts=[],
                detected_ai_functions=[],
                possible_risks=[],
                possible_rights_or_interests=[],
                obligations_to_verify=[],
                missing_questions=[
                    "Does the text describe an AI system or an automated system?",
                    "What output does the system produce, such as a prediction, recommendation, ranking, score, decision or generated content?",
                    "Who uses the system, and who may be affected by its output?",
                ],
                relevant_ai_act_sources=[],
                traceability=[],
                notes=["The input did not contain enough evidence for the rule engine to map AI Act concepts."],
            )
        rights = self._rights_from_matches(prohibition_matches)
        obligations = self._obligations_from_matches(prohibition_matches)
        questions = self._article_5_missing_questions(prohibition_matches)
        sources = self._article_5_sources(legal_db)
        trace = self._trace(claims, contexts + functions + risks + rights + obligations, sources, prohibition_matches)
        return PreliminaryAnalysis(
            case_summary=self._summary(case_input.raw_text, contexts, functions, prohibition_matches),
            matched_prohibited_practices=prohibition_matches,
            detected_actors=actors,
            detected_contexts=contexts,
            detected_ai_functions=functions,
            possible_risks=risks,
            possible_rights_or_interests=rights,
            obligations_to_verify=obligations,
            missing_questions=questions,
            relevant_ai_act_sources=sources,
            traceability=trace,
            notes=["The deterministic scope is limited to Article 5 prohibited AI practices and requires human legal review."],
        )

    def _has_ai_act_signal(
        self,
        text: str,
        contexts: list[DetectedItem],
        functions: list[DetectedItem],
        risks: list[DetectedItem],
        matches: list[ProhibitedPracticeMatch],
    ) -> bool:
        ai_terms = ["ai", "artificial intelligence", "algorithm", "model", "automated", "machine learning", "llm", "chatbot"]
        return bool(matches or functions or (contexts and any(term in text for term in ai_terms)) or (risks and any(term in text for term in ai_terms)))

    def _detect_contexts(self, text: str) -> list[DetectedItem]:
        context_terms = {
            "employment": ["recruitment", "candidate", "hiring", "cv", "worker", "employee", "job", "promotion", "internship"],
            "education and vocational training": ["student", "school", "university", "exam", "admission", "assessment"],
            "essential public services / public benefits": ["welfare", "housing", "benefits", "social services", "municipality", "public administration", "public service"],
            "healthcare": ["patient", "diagnosis", "triage", "medical", "hospital"],
            "law enforcement": ["police", "crime", "risk assessment", "investigation"],
            "migration, asylum and border control": ["asylum", "border", "visa", "migration"],
            "administration of justice and democratic processes": ["court", "judge", "election", "voting", "democratic process"],
            "chatbot/content AI": ["chatbot", "assistant", "generated image", "generated video", "deepfake", "synthetic content"],
        }
        found = self._match_items(text, context_terms, "context")
        for area in self.annex:
            if any(term.lower() in text for term in area.get("keywords", [])):
                equivalent_public_services = area["id"] == "public_services" and any("public services" in item.label for item in found)
                if not equivalent_public_services and not any(item.label == area["label"] for item in found):
                    found.append(DetectedItem(label=area["label"], category="Annex III area", evidence=area.get("keywords", [])[:3], confidence=0.75))
        return found

    def _detect_functions(self, text: str) -> list[DetectedItem]:
        terms = {
            "scoring": ["score", "scoring", "suitability score"],
            "ranking": ["rank", "ranking", "prioritise", "prioritize"],
            "filtering": ["filter", "screen", "exclude", "shortlist"],
            "recommendation": ["recommend", "recommendation"],
            "automated decision": ["automated decision", "final decision", "approve", "deny"],
            "biometric identification": ["biometric", "face recognition", "fingerprint"],
            "prediction": ["predict", "prediction", "forecast"],
            "content generation": ["generate", "generated", "synthetic content", "deepfake"],
            "chatbot interaction": ["chatbot", "virtual assistant", "conversational"],
        }
        return self._match_items(text, terms, "AI function")

    def _detect_actors(self, text: str) -> list[DetectedItem]:
        terms = {
            "provider": ["vendor", "developer", "supplier", "platform provider", "provider"],
            "deployer": ["municipality", "company uses", "public body uses", "school uses", "agency uses", "uses an ai", "wants to use"],
            "human operator": ["officer", "human", "caseworker", "operator", "reviewer"],
            "affected person": ["candidate", "citizen", "student", "applicant", "worker", "patient", "beneficiary", "tenant"],
        }
        actors = self._match_items(text, terms, "actor")
        if actors and not any(actor.label == "provider" for actor in actors):
            actors.append(DetectedItem(label="provider", category="actor", evidence=[], confidence=0.25, status="unknown / to verify"))
        return actors

    def _detect_prohibited_practices(self, text: str) -> list[ProhibitedPracticeMatch]:
        matches = []
        for rule in self.prohibitions:
            keywords = rule.get("keywords", [])
            evidence = [term for term in keywords if term.lower() in text]
            if len(evidence) < int(rule.get("minimum_matches", 2)):
                continue
            matches.append(
                ProhibitedPracticeMatch(
                    id=rule["id"],
                    label=rule["label"],
                    article_point=rule["article_point"],
                    targets=list(rule.get("targets", [])),
                    contexts=list(rule.get("contexts", [])),
                    exceptions=list(rule.get("exceptions", [])),
                    affected_rights=list(rule.get("affected_rights", [])),
                    safeguards=list(rule.get("safeguards", [])),
                    trigger_conditions=list(rule.get("trigger_conditions", [])),
                    evidence=evidence[:8],
                    confidence=min(0.95, 0.55 + len(evidence) * 0.08),
                    status="Article 5 match to verify",
                )
            )
        return matches

    def _detect_risks(self, text: str, matches: list[ProhibitedPracticeMatch]) -> list[DetectedItem]:
        return [
            DetectedItem(
                label=match.label,
                category="Article 5 prohibited-practice risk",
                evidence=match.evidence,
                confidence=match.confidence,
                status="to verify",
            )
            for match in matches
        ]

    def _rights_from_matches(self, matches: list[ProhibitedPracticeMatch]) -> list[DetectedItem]:
        labels = []
        for match in matches:
            for right in match.affected_rights:
                if right not in labels:
                    labels.append(right)
        return [DetectedItem(label=label, category="right_or_interest", confidence=0.7, status="mapped from Article 5 rule") for label in labels]

    def _obligations_from_matches(self, matches: list[ProhibitedPracticeMatch]) -> list[DetectedItem]:
        if not matches:
            return []
        labels = ["verify Article 5 prohibition criteria", "check whether any Article 5 exception applies"]
        if any(match.safeguards for match in matches):
            labels.append("verify safeguards defined in the matched Article 5 rule")
        return [DetectedItem(label=label, category="obligation_to_verify", confidence=0.65, status="to verify") for label in labels]

    def _article_5_missing_questions(self, matches: list[ProhibitedPracticeMatch]) -> list[str]:
        questions = {
            "Which Article 5 prohibited-practice point, if any, is being assessed?",
            "What evidence shows that each trigger condition of the suspected Article 5 rule is met?",
            "Are any Article 5 exceptions or safeguards explicitly applicable?",
            "Who is the provider, deployer and affected natural person or group?",
        }
        if not matches:
            questions.add("Does the scenario involve any Article 5 practice such as social scoring, prohibited biometric use, manipulative techniques or exploitation of vulnerabilities?")
        return sorted(questions)

    def _summary(self, text, contexts, functions, matches) -> str:
        if matches:
            points = ", ".join(f"Article {match.article_point}" for match in matches[:3])
            return f"The scenario contains signals for Article 5 prohibited AI practice review under {points}."
        ctx = contexts[0].label if contexts else "an unspecified context"
        fn = functions[0].label if functions else "AI-supported processing"
        return f"The scenario describes possible {fn} in {ctx}, but no Article 5 prohibited-practice match was detected by the deterministic rules."

    def _article_5_sources(self, legal_db) -> list[LegalSourceRef]:
        article = legal_db.get_article_by_number("5")
        if not article:
            return [
                LegalSourceRef(
                    article_number="5",
                    article_heading="Prohibited AI practices",
                    eId=None,
                    short_excerpt="Article 5 source was not available in the loaded legal corpus.",
                    relevance_reason="The checker is scoped to Article 5 prohibited AI practices.",
                )
            ]
        return [
            LegalSourceRef(
                article_number=article.number,
                article_heading=article.heading,
                eId=article.eId,
                short_excerpt=article.text[:700],
                relevance_reason="The checker is scoped to Article 5 prohibited AI practices.",
            )
        ]

    def _trace(self, claims, items, sources, matches: list[ProhibitedPracticeMatch]) -> list[TraceabilityItem]:
        traces = []
        for match in matches:
            snippet = next((claim for claim in claims if any(ev.lower() in claim.lower() for ev in match.evidence)), claims[0] if claims else "")
            traces.append(
                TraceabilityItem(
                    input_snippet=snippet[:240],
                    detected_concept=match.label,
                    mapped_risk=match.label,
                    mapped_right_or_interest=", ".join(match.affected_rights) or None,
                    relevant_source=f"Article {match.article_point}",
                    confidence=match.confidence,
                    note="Matched fields use only the explicit Article 5 prohibition mapping; legal review is required.",
                )
            )
        for item in items[:20]:
            snippet = next((claim for claim in claims if any(ev.lower() in claim.lower() for ev in item.evidence)), claims[0] if claims else "")
            source_label = self._sources_for_item(item, sources)
            traces.append(
                TraceabilityItem(
                    input_snippet=snippet[:240],
                    detected_concept=item.label,
                    mapped_risk=item.label if item.category == "risk" else None,
                    mapped_right_or_interest=item.label if item.category == "right_or_interest" else None,
                    relevant_source=source_label,
                    confidence=item.confidence,
                    note=f"{item.status.capitalize()} signal detected by deterministic keyword rules; information may be incomplete.",
                )
            )
        return traces

    def _sources_for_item(self, item: DetectedItem, sources) -> str:
        return "Article 5" if sources else "Article 5 source to verify"

    def _match_items(self, text: str, mapping: dict[str, list[str]], category: str) -> list[DetectedItem]:
        found = []
        for label, terms in mapping.items():
            evidence = [term for term in terms if term.lower() in text]
            if evidence:
                found.append(DetectedItem(label=label, category=category, evidence=evidence[:5], confidence=min(0.9, 0.45 + len(evidence) * 0.15)))
        return found
