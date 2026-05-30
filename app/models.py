from pydantic import BaseModel, Field
from typing import Any


MAX_TEXT_LENGTH = 20000
MAX_TITLE_LENGTH = 160
MAX_PERSONA_LENGTH = 80


class LegalParagraph(BaseModel):
    eId: str | None = None
    number: str | None = None
    text: str


class LegalDefinition(BaseModel):
    term: str
    text: str
    article_number: str = "3"
    eId: str | None = None


class LegalArticle(BaseModel):
    eId: str | None = None
    number: str
    heading: str | None = None
    text: str
    paragraphs: list[LegalParagraph] = Field(default_factory=list)
    source_path: str | None = None
    source_type: str = "AKN"


class LegalCorpus(BaseModel):
    articles: list[LegalArticle] = Field(default_factory=list)
    definitions: list[LegalDefinition] = Field(default_factory=list)
    source_path: str | None = None
    warnings: list[str] = Field(default_factory=list)


class CaseInput(BaseModel):
    raw_text: str
    title: str = "Untitled scenario"
    persona: str = "citizen"
    claims: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)


class CaseInputRequest(BaseModel):
    title: str | None = Field(default=None, max_length=MAX_TITLE_LENGTH)
    text: str = Field(min_length=1, max_length=MAX_TEXT_LENGTH)
    persona: str | None = Field(default="citizen", max_length=MAX_PERSONA_LENGTH)
    use_llm: bool = False


class LegalSourceRef(BaseModel):
    article_number: str
    article_heading: str | None = None
    eId: str | None = None
    short_excerpt: str | None = None
    relevance_reason: str


class TraceabilityItem(BaseModel):
    input_snippet: str
    detected_concept: str
    mapped_risk: str | None = None
    mapped_right_or_interest: str | None = None
    relevant_source: str | None = None
    confidence: float = 0.6
    note: str


class DetectedItem(BaseModel):
    label: str
    category: str | None = None
    evidence: list[str] = Field(default_factory=list)
    confidence: float = 0.6
    status: str = "possible"


class EvidenceSupport(BaseModel):
    snippet: str
    source: str | None = None
    confidence: float = 0.0


class CandidateFact(BaseModel):
    id: str
    label: str
    type: str = "signal"
    ontology_candidate: str | None = None
    evidence: EvidenceSupport
    confidence: float = 0.0
    provenance: str = "deterministic"
    accepted: bool = True
    note: str | None = None


class LegalElementResult(BaseModel):
    id: str
    label: str
    source: str | None = None
    element_type: str | None = None
    requirement_type: str = "required"
    status: str
    evidence: list[EvidenceSupport] = Field(default_factory=list)
    missing_question: str | None = None
    confidence: float = 0.0


class ExceptionResult(BaseModel):
    id: str
    label: str
    source: str | None = None
    status: str
    evidence: list[EvidenceSupport] = Field(default_factory=list)
    required_conditions: list[LegalElementResult] = Field(default_factory=list)


class SourceAnchor(BaseModel):
    article: str
    paragraph: str | None = None
    point: str | None = None
    eId: str | None = None
    label: str
    frbr_uri: str | None = None
    celex: str | None = None
    legal_status: str = "current_binding_law"


class ProhibitedPracticeMatch(BaseModel):
    id: str
    label: str
    article_point: str
    targets: list[str] = Field(default_factory=list)
    contexts: list[str] = Field(default_factory=list)
    exceptions: list[str] = Field(default_factory=list)
    affected_rights: list[str] = Field(default_factory=list)
    safeguards: list[str] = Field(default_factory=list)
    trigger_conditions: list[str] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)
    legal_elements: list[LegalElementResult] = Field(default_factory=list)
    exception_results: list[ExceptionResult] = Field(default_factory=list)
    source_anchors: list[SourceAnchor] = Field(default_factory=list)
    legal_basis_status: str = "current_binding_law"
    confidence: float = 0.6
    status: str = "possible"


class PreliminaryAnalysis(BaseModel):
    case_summary: str
    candidate_facts: list[CandidateFact] = Field(default_factory=list)
    matched_prohibited_practices: list[ProhibitedPracticeMatch] = Field(default_factory=list)
    detected_actors: list[DetectedItem] = Field(default_factory=list)
    detected_contexts: list[DetectedItem] = Field(default_factory=list)
    detected_ai_functions: list[DetectedItem] = Field(default_factory=list)
    possible_risks: list[DetectedItem] = Field(default_factory=list)
    possible_rights_or_interests: list[DetectedItem] = Field(default_factory=list)
    obligations_to_verify: list[DetectedItem] = Field(default_factory=list)
    missing_questions: list[str] = Field(default_factory=list)
    relevant_ai_act_sources: list[LegalSourceRef] = Field(default_factory=list)
    traceability: list[TraceabilityItem] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class GraphView(BaseModel):
    nodes: list[dict[str, Any]] = Field(default_factory=list)
    edges: list[dict[str, Any]] = Field(default_factory=list)


class AnalysisResponse(BaseModel):
    case_summary: str
    candidate_facts: list[CandidateFact] = Field(default_factory=list)
    matched_prohibited_practices: list[ProhibitedPracticeMatch] = Field(default_factory=list)
    detected_actors: list[DetectedItem]
    detected_contexts: list[DetectedItem]
    detected_ai_functions: list[DetectedItem]
    possible_risks: list[DetectedItem]
    possible_rights_or_interests: list[DetectedItem]
    obligations_to_verify: list[DetectedItem]
    missing_questions: list[str]
    relevant_ai_act_sources: list[LegalSourceRef]
    traceability: list[TraceabilityItem]
    notes: list[str] = Field(default_factory=list)
    citizen_explanation: str
    disclaimer: str
    raw_rule_output: dict[str, Any]
    rdf_triples_preview: str
    markdown_summary: str
    graph: GraphView
