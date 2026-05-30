from __future__ import annotations

from app.legal_source.akn_validator import AKNValidationResult
from app.legal_source.source_index import LegalSourceIndex, SourceNode
from app.models import (
    CaseInput,
    CandidateFact,
    DetectedItem,
    EvidenceSupport,
    ExceptionResult,
    LegalSourceRef,
    PreliminaryAnalysis,
    ProhibitedPracticeMatch,
    SourceAnchor,
    TraceabilityItem,
)
from app.ontology.legal_ontology_store import LegalOntologyStore
from app.reasoning.fact_extractor import FactExtractor
from app.reasoning.legal_element_checker import LegalElementChecker


class Article5Reasoner:
    def __init__(self, legal_ontology: LegalOntologyStore, source_index: LegalSourceIndex | None, validation_result: AKNValidationResult):
        self.legal_ontology = legal_ontology
        self.source_index = source_index
        self.validation_result = validation_result
        self.fact_extractor = FactExtractor()
        self.element_checker = LegalElementChecker()

    @property
    def available(self) -> bool:
        return not self._unavailable_reasons()

    def analyze(self, case_input: CaseInput, suggested_facts: list[CandidateFact] | None = None) -> PreliminaryAnalysis:
        reasons = self._unavailable_reasons()
        if reasons:
            return self._analysis_unavailable(reasons)

        deterministic_facts = self.fact_extractor.extract(case_input.raw_text)
        facts = self.fact_extractor.merge(deterministic_facts, suggested_facts)
        matches: list[ProhibitedPracticeMatch] = []
        trace: list[TraceabilityItem] = []
        for practice in self.legal_ontology.get_prohibited_practices():
            elements = self.legal_ontology.get_required_elements(practice["id"])
            element_results = self.element_checker.check(facts, elements)
            supported = [item for item in element_results if item.status == "supported"]
            supported_system = [item for item in supported if "__usesSystem__" in item.id]
            if not supported_system or len(supported) < 2:
                continue
            anchors = self._source_anchors(practice["id"])
            match = ProhibitedPracticeMatch(
                id=practice["id"],
                label=practice["label"],
                article_point=self._article_point(anchors) or "5",
                affected_rights=[right["label"] for right in self.legal_ontology.get_affected_rights(practice["id"])],
                evidence=list(dict.fromkeys(support.evidence[0].snippet for support in supported if support.evidence)),
                legal_elements=element_results,
                exception_results=self._exception_results(practice["id"], facts),
                source_anchors=anchors,
                legal_basis_status=self._legal_basis_status(anchors),
                confidence=max((item.confidence for item in supported), default=0.0),
                status="ontology_element_review",
            )
            matches.append(match)
            trace.extend(self._trace_for_match(match))

        sources = self._article_5_sources()
        return PreliminaryAnalysis(
            case_summary="No Article 5 ontology-supported match was detected." if not matches else "Article 5 ontology review produced candidate matches.",
            candidate_facts=facts,
            matched_prohibited_practices=matches,
            detected_actors=self._detected_items(facts, "actor"),
            detected_contexts=self._detected_items(facts, "context"),
            detected_ai_functions=self._detected_items(facts, "system_or_function"),
            possible_risks=[
                DetectedItem(label=match.label, category="ontology_prohibited_practice_candidate", evidence=match.evidence, confidence=match.confidence, status=match.status)
                for match in matches
            ],
            possible_rights_or_interests=[
                DetectedItem(label=right, category="right_or_interest", confidence=0.6, status="mapped from legal ontology")
                for right in dict.fromkeys(right for match in matches for right in match.affected_rights)
            ],
            obligations_to_verify=[],
            missing_questions=self._missing_questions(matches, facts),
            relevant_ai_act_sources=sources,
            traceability=trace or self._trace_for_candidate_facts(facts),
            notes=[
                "Ontology-first path used. No JSON rule fallback was used.",
                "LLM-suggested candidate facts were used as evidence inputs; Article 5 legal validation remained RDF/AKN-gated."
                if any(fact.provenance == "llm_suggested" for fact in facts)
                else "No LLM-suggested candidate facts were used.",
                "Amended Article 5 prohibitions are integrated in this prototype.",
            ],
        )

    def _unavailable_reasons(self) -> list[str]:
        reasons: list[str] = []
        if not self.validation_result.attempted:
            reasons.append("AKN XML schema validation was not attempted: " + "; ".join(self.validation_result.warnings or ["schema files missing"]))
        elif not self.validation_result.is_valid:
            reasons.append("AKN XML schema validation failed: " + "; ".join(self.validation_result.errors or ["unknown validation error"]))
        if not self.source_index or not self.source_index.is_loaded:
            reasons.append("Legal source index is unavailable.")
        elif not self.source_index.get_article("5"):
            reasons.append("Article 5 source anchors are unavailable.")
        if not self.legal_ontology.status.loaded:
            reasons.append("Legal ontology is missing or not loaded.")
        elif not self.legal_ontology.status.is_valid:
            reasons.append("Legal ontology is invalid: " + "; ".join(self.legal_ontology.status.errors))
        return reasons

    def _analysis_unavailable(self, reasons: list[str]) -> PreliminaryAnalysis:
        return PreliminaryAnalysis(
            case_summary="Legal analysis unavailable",
            matched_prohibited_practices=[],
            detected_actors=[],
            detected_contexts=[],
            detected_ai_functions=[],
            possible_risks=[],
            possible_rights_or_interests=[],
            obligations_to_verify=[],
            missing_questions=[
                "Provide a valid Akoma Ntoso AI Act XML source and local XSD files.",
                "Provide the reviewed Article 5 RDF ontology in the configured legal ontology directory.",
            ],
            relevant_ai_act_sources=[],
            traceability=[],
            notes=["analysis_unavailable", *reasons, "No legal assessment was performed and no JSON rule fallback was used."],
        )

    def _article_5_sources(self) -> list[LegalSourceRef]:
        article = self.source_index.get_article("5") if self.source_index else None
        if not article:
            return []
        return [self._source_ref(article)]

    def _source_ref(self, node: SourceNode) -> LegalSourceRef:
        return LegalSourceRef(
            article_number=node.article,
            article_heading=node.heading,
            eId=node.eId,
            short_excerpt=node.text[:700],
            relevance_reason="Source anchor from validated Akoma Ntoso source-law layer.",
        )

    def _source_anchors(self, practice_id: str) -> list[SourceAnchor]:
        anchors = []
        for raw in self.legal_ontology.get_source_anchors(practice_id):
            label = raw.get("label") or raw.get("source_anchor") or "Article 5"
            article, paragraph, point = self._parse_anchor(label)
            node = self.source_index.get_article_point(article, paragraph or "1", point) if point and self.source_index else None
            anchors.append(
                SourceAnchor(
                    article=article,
                    paragraph=paragraph,
                    point=point,
                    eId=node.eId if node else None,
                    label=label,
                    frbr_uri=node.frbr_uri if node else None,
                    celex=node.celex if node else None,
                    legal_status=raw.get("legal_status") or "current_binding_law",
                )
            )
        return anchors

    def _exception_results(self, practice_id: str, facts) -> list[ExceptionResult]:
        results = []
        for item in self.legal_ontology.get_exceptions(practice_id):
            conditions = self.legal_ontology.get_required_conditions(item["id"])
            condition_results = self.element_checker.check(facts, conditions) if conditions else []
            status = "exception_possible"
            if condition_results and all(condition.status == "missing" for condition in condition_results):
                status = "missing"
            results.append(
                ExceptionResult(
                    id=item["id"],
                    label=item["label"],
                    source=item.get("source"),
                    status=status,
                    evidence=[EvidenceSupport(snippet="Defined in reviewed RDF ontology.", source=item.get("uri"), confidence=1.0)],
                    required_conditions=condition_results,
                )
            )
        return results

    def _legal_basis_status(self, anchors: list[SourceAnchor]) -> str:
        if not anchors:
            return "source_anchor_missing"
        statuses = {anchor.legal_status for anchor in anchors}
        if statuses == {"current_binding_law"}:
            return "current_binding_law"
        if statuses == {"amended_article5"}:
            return "amended_article5"
        if "current_binding_law" in statuses:
            return "mixed_current_and_amended_article5"
        return "amended_article5"

    def _parse_anchor(self, label: str) -> tuple[str, str | None, str | None]:
        import re

        match = re.search(r"Article\s*(\d+)(?:\(([^)]+)\))?(?:\(([^)]+)\))?", label, re.I)
        if match:
            return match.group(1), match.group(2), match.group(3)
        return "5", "1", None

    def _article_point(self, anchors: list[SourceAnchor]) -> str | None:
        if not anchors:
            return None
        anchor = anchors[0]
        if anchor.paragraph and anchor.point:
            return f"{anchor.article}({anchor.paragraph})({anchor.point})"
        return anchor.article

    def _detected_items(self, facts: list[CandidateFact], fact_type: str) -> list[DetectedItem]:
        items = []
        seen = set()
        for fact in facts:
            if fact.type != fact_type:
                continue
            label = fact.ontology_candidate or fact.label
            key = (label, fact.provenance)
            if key in seen:
                continue
            seen.add(key)
            items.append(
                DetectedItem(
                    label=label,
                    category=f"{fact.provenance}_{fact.type}",
                    evidence=[fact.evidence.snippet],
                    confidence=fact.confidence or fact.evidence.confidence,
                    status=fact.provenance,
                )
            )
        return items

    def _trace_for_match(self, match: ProhibitedPracticeMatch) -> list[TraceabilityItem]:
        traces = []
        for element in match.legal_elements:
            for evidence in element.evidence:
                traces.append(
                    TraceabilityItem(
                        input_snippet=evidence.snippet,
                        detected_concept=element.label,
                        mapped_risk=match.label,
                        mapped_right_or_interest=", ".join(match.affected_rights) or None,
                        relevant_source=match.article_point,
                        confidence=element.confidence,
                        note=f"Legal element status: {element.status}. Ontology-first path; no JSON rule fallback.",
                    )
                )
        return traces

    def _trace_for_candidate_facts(self, facts: list[CandidateFact]) -> list[TraceabilityItem]:
        if not any(fact.provenance == "llm_suggested" for fact in facts):
            return []
        return [
            TraceabilityItem(
                input_snippet=fact.evidence.snippet,
                detected_concept=fact.ontology_candidate or fact.label,
                relevant_source=None,
                confidence=fact.confidence or fact.evidence.confidence,
                note=f"Candidate fact provenance: {fact.provenance}. This is not an Article 5 legal conclusion.",
            )
            for fact in facts
            if fact.provenance == "llm_suggested"
        ]

    def _missing_questions(self, matches: list[ProhibitedPracticeMatch], facts: list[CandidateFact]) -> list[str]:
        questions = []
        for match in matches:
            for element in match.legal_elements:
                if element.missing_question:
                    questions.append(element.missing_question)
        if questions or matches:
            return questions
        contextual_ids = {fact.id for fact in facts}
        if {"camera_monitoring", "workplace_context"} & contextual_ids:
            return [
                "Are workers recorded by the AI-connected camera system?",
                "Is the AI used to evaluate worker behaviour or performance?",
                "Does the system infer emotions, identity, biometric traits, or sensitive characteristics of people?",
                "Are decisions taken about workers based on the system output?",
            ]
        return ["No reviewed Article 5 ontology element was supported by the extracted facts."]
