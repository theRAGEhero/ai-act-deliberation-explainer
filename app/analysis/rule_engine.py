from __future__ import annotations

import json
from pathlib import Path

from app.legal_source.article_selector import source_refs_for_concepts
from app.models import CaseInput, DetectedItem, LegalSourceRef, PreliminaryAnalysis, TraceabilityItem


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


class RuleEngine:
    def __init__(self, seed_annexes_path: Path, seed_concepts_path: Path):
        self.annex = _load_json(seed_annexes_path).get("annex_iii", [])
        self.seed = _load_json(seed_concepts_path)

    def analyze(self, case_input: CaseInput, legal_db, ontology_store=None) -> PreliminaryAnalysis:
        text = case_input.raw_text.lower()
        claims = case_input.claims or [case_input.raw_text]
        contexts = self._detect_contexts(text)
        functions = self._detect_functions(text)
        actors = self._detect_actors(text)
        risks = self._detect_risks(text, contexts, functions)
        rights = self._detect_rights(text, contexts, risks)
        obligations = self._detect_obligations(contexts, functions, risks, actors)
        questions = self._missing_questions(contexts, functions, risks)
        concepts = [item.label for group in [contexts, functions, risks, rights, obligations] for item in group]
        sources = source_refs_for_concepts(concepts + ["definitions"], legal_db)
        sources = self._add_annex_source_if_needed(contexts, sources)
        trace = self._trace(claims, contexts + functions + risks + rights + obligations, sources)
        return PreliminaryAnalysis(
            case_summary=self._summary(case_input.raw_text, contexts, functions),
            detected_actors=actors,
            detected_contexts=contexts,
            detected_ai_functions=functions,
            possible_risks=risks,
            possible_rights_or_interests=rights,
            obligations_to_verify=obligations,
            missing_questions=questions,
            relevant_ai_act_sources=sources,
            traceability=trace,
            notes=["All findings are preliminary risk signals and require human legal review."],
        )

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
        if not any(actor.label == "provider" for actor in actors):
            actors.append(DetectedItem(label="provider", category="actor", evidence=[], confidence=0.25, status="unknown / to verify"))
        return actors

    def _detect_risks(self, text: str, contexts: list[DetectedItem], functions: list[DetectedItem]) -> list[DetectedItem]:
        terms = {
            "bias": ["historical data", "training data", "demographic", "minority", "gender", "race", "discrimination", "welfare data"],
            "opacity": ["black box", "not explainable", "no explanation", "hidden score", "will not see", "not see the score"],
            "automation bias": ["human always follows", "final decision human", "human officer", "score used", "recommendation strongly influences"],
            "weak contestability": ["no appeal", "no challenge", "no review", "cannot contest", "will not see the score"],
            "lack of disclosure": ["not told ai", "not informed", "without disclosure"],
            "vulnerable group impact": ["minors", "migrants", "disabled", "low-income", "minorities", "women", "welfare", "housing"],
        }
        risks = self._match_items(text, terms, "risk")
        labels = {risk.label for risk in risks}
        if any(fn.label in {"ranking", "scoring", "automated decision"} for fn in functions) and "automation bias" not in labels:
            risks.append(DetectedItem(label="automation bias", category="risk", evidence=["ranking/scoring used in decision workflow"], confidence=0.55))
        if contexts and any("Annex III" == item.category for item in contexts) and "fundamental rights impact" not in labels:
            risks.append(DetectedItem(label="fundamental rights impact to verify", category="risk", evidence=["Annex III area signal"], confidence=0.55))
        return risks

    def _detect_rights(self, text: str, contexts: list[DetectedItem], risks: list[DetectedItem]) -> list[DetectedItem]:
        labels = {"transparency", "non-discrimination", "human oversight", "contestability", "human explanation"}
        if any("housing" in c.label or "public" in c.label for c in contexts):
            labels.add("access to essential public services")
        if any("employment" in c.label.lower() for c in contexts):
            labels.add("access to employment opportunity")
        if "privacy" in text or "data" in text:
            labels.add("privacy/data protection")
        return [DetectedItem(label=label, category="right_or_interest", confidence=0.6) for label in sorted(labels)]

    def _detect_obligations(self, contexts, functions, risks, actors) -> list[DetectedItem]:
        labels = {"inform deployer", "ensure human oversight", "allow meaningful human review"}
        if any(r.label in {"opacity", "lack of disclosure"} for r in risks):
            labels.add("inform affected person")
        if any(fn.label in {"ranking", "scoring", "automated decision"} for fn in functions):
            labels.update({"keep logs", "maintain technical documentation", "provide instructions for use"})
        if any("Annex III" == c.category or "public services" in c.label for c in contexts):
            labels.add("assess fundamental rights impact")
        if any(fn.label == "chatbot interaction" for fn in functions):
            labels.add("disclose chatbot interaction")
        if any(fn.label == "content generation" for fn in functions):
            labels.add("disclose AI-generated content")
        return [DetectedItem(label=label, category="obligation_to_verify", confidence=0.55, status="to verify") for label in sorted(labels)]

    def _missing_questions(self, contexts, functions, risks) -> list[str]:
        questions = {
            "What data is used, and what is its provenance?",
            "Can the affected person understand and contest the result?",
            "Can the human operator meaningfully override the AI output?",
            "Who is the provider and who is the deployer?",
            "Is the AI system used to rank, filter, score or otherwise influence access to an opportunity or service?",
        }
        for area in self.annex:
            if any(area["label"] == c.label or area["id"] in c.label.lower() for c in contexts):
                questions.update(area.get("missing_questions", []))
        if any("vulnerable" in risk.label for risk in risks):
            questions.add("Are vulnerable groups affected, and how is that assessed?")
        if any("public services" in c.label for c in contexts):
            questions.add("Is a fundamental rights impact assessment required for the public-sector deployer?")
        return sorted(questions)

    def _summary(self, text, contexts, functions) -> str:
        ctx = contexts[0].label if contexts else "an unspecified context"
        fn = functions[0].label if functions else "AI-supported processing"
        if "municipality" in text.lower() and "housing" in text.lower():
            return "A public body is discussing an AI ranking system for access to social housing."
        return f"The scenario describes possible {fn} in {ctx}; AI Act relevance should be verified."

    def _trace(self, claims, items, sources) -> list[TraceabilityItem]:
        traces = []
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

    def _add_annex_source_if_needed(self, contexts: list[DetectedItem], sources) -> list[LegalSourceRef]:
        has_annex_signal = any(context.category == "Annex III area" or "public services" in context.label for context in contexts)
        if not has_annex_signal:
            return sources
        return sources + [
            LegalSourceRef(
                article_number="Annex III",
                article_heading="High-risk areas signalled by seeded Annex III taxonomy",
                eId=None,
                short_excerpt="Seeded Annex III area signal used for preliminary high-risk classification discussion.",
                relevance_reason="The scenario contains keywords associated with an Annex III high-risk area; classification remains to verify.",
            )
        ]

    def _sources_for_item(self, item: DetectedItem, sources) -> str:
        label = item.label.lower()
        wanted = ["3"]
        if item.category in {"context", "Annex III area"}:
            wanted += ["6", "Annex III", "27"]
        if item.category == "AI function":
            wanted += ["6", "13", "14", "86"]
        if item.category == "risk":
            if "bias" in label or "vulnerable" in label:
                wanted += ["10", "27"]
            if "opacity" in label or "contestability" in label:
                wanted += ["13", "86"]
            if "automation" in label:
                wanted += ["14", "26"]
        if item.category == "right_or_interest":
            if "transparency" in label:
                wanted += ["13"]
            if "oversight" in label:
                wanted += ["14"]
            if "explanation" in label or "contestability" in label:
                wanted += ["86"]
            if "non-discrimination" in label or "essential" in label:
                wanted += ["6", "27", "Annex III"]
        if item.category == "obligation_to_verify":
            if "impact" in label:
                wanted += ["27"]
            if "oversight" in label or "review" in label:
                wanted += ["14", "26"]
            if "logs" in label:
                wanted += ["12"]
            if "documentation" in label:
                wanted += ["11"]
            if "instructions" in label or "inform" in label:
                wanted += ["13", "26"]
        available = {source.article_number for source in sources}
        labels = []
        for number in wanted:
            if number in available:
                labels.append(number if number == "Annex III" else f"Article {number}")
        return ", ".join(dict.fromkeys(labels)) or "AI Act source to verify"

    def _match_items(self, text: str, mapping: dict[str, list[str]], category: str) -> list[DetectedItem]:
        found = []
        for label, terms in mapping.items():
            evidence = [term for term in terms if term.lower() in text]
            if evidence:
                found.append(DetectedItem(label=label, category=category, evidence=evidence[:5], confidence=min(0.9, 0.45 + len(evidence) * 0.15)))
        return found
