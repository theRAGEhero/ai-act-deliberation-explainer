from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import HTMLResponse, PlainTextResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi import Request

from app.analysis.input_processor import build_case_input
from app.analysis.llm_agent import OptionalLLMAgent
from app.analysis.report_builder import ReportBuilder
from app.config import settings
from app.legal_source.akn_validator import validate_akn_xml
from app.legal_source.legal_db import LegalKnowledgeDB
from app.legal_source.source_index import LegalSourceIndex
from app.ontology.case_graph import CaseGraphBuilder
from app.ontology.legal_ontology_store import LegalOntologyStore
from app.reasoning.article5_reasoner import Article5Reasoner
from app.models import MAX_TEXT_LENGTH, AnalysisResponse, CaseInputRequest
from rdflib import RDFS, URIRef


MAX_UPLOAD_BYTES = MAX_TEXT_LENGTH * 4

app = FastAPI(title="AI Act Prohibitions Checker")
app.mount("/static", StaticFiles(directory=settings.project_root / "app/static"), name="static")
templates = Jinja2Templates(directory=settings.project_root / "app/templates")

legal_db = LegalKnowledgeDB(settings.resolve_path(settings.seed_concepts_path))
akn_path = settings.resolve_path(settings.ai_act_akn_path)
corpus = legal_db.load_from_akn(akn_path)
akn_validation = validate_akn_xml(
    akn_path,
    settings.resolve_path(settings.akomantoso_xsd_path),
    settings.resolve_path(settings.xml_xsd_path),
)
source_index = LegalSourceIndex(akn_path) if akn_validation.attempted and akn_validation.is_valid else None
legal_ontology_store = LegalOntologyStore(settings.resolve_path(settings.legal_ontology_dir))
article5_reasoner = Article5Reasoner(legal_ontology_store, source_index, akn_validation)
report_builder = ReportBuilder()
case_graph_builder = CaseGraphBuilder()
llm_agent = OptionalLLMAgent()


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    return templates.TemplateResponse(request, "index.html")


@app.api_route("/favicon.ico", methods=["GET", "HEAD"], include_in_schema=False)
def favicon():
    return RedirectResponse(url="/static/favicon.svg", status_code=308)


@app.post("/api/analyze", response_model=AnalysisResponse)
def analyze(payload: CaseInputRequest):
    payload.text = payload.text.strip()
    if not payload.text:
        raise HTTPException(status_code=400, detail="Text is required")
    case_input = build_case_input(payload.text, payload.title, payload.persona)
    suggested_facts = llm_agent.extract_candidate_facts(payload.text) if payload.use_llm and article5_reasoner.available else []
    preliminary = article5_reasoner.analyze(case_input, suggested_facts)
    llm_output = None
    if payload.use_llm and "analysis_unavailable" not in preliminary.notes:
        llm_output = llm_agent.refine(
            payload.text,
            preliminary.model_dump(),
            [src.model_dump() for src in preliminary.relevant_ai_act_sources],
            list(case_input.keywords),
        )
    rdf_preview = "\n".join(case_graph_builder.serialize_turtle(preliminary).splitlines()[:80])
    return report_builder.build(preliminary, rdf_preview, llm_output)


@app.post("/api/upload", response_model=AnalysisResponse)
async def upload(file: UploadFile = File(...), use_llm: bool = False):
    if not file.filename.lower().endswith(".txt"):
        raise HTTPException(status_code=400, detail="Only .txt files are supported")
    raw = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(raw) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail=f"Uploaded text must be at most {MAX_TEXT_LENGTH} characters")
    content = raw.decode("utf-8", errors="replace")
    return analyze(CaseInputRequest(title=file.filename, text=content, use_llm=use_llm))


@app.get("/api/articles")
def articles():
    return [{"number": a.number, "heading": a.heading, "eId": a.eId, "source_type": a.source_type} for a in legal_db.articles_by_number.values()]


@app.get("/api/articles/{number}")
def article(number: str):
    found = legal_db.get_article_by_number(number)
    if not found:
        raise HTTPException(status_code=404, detail="Article not found")
    return found


@app.get("/api/legal-ontology.ttl", response_class=PlainTextResponse)
def legal_ontology_ttl():
    return legal_ontology_store.serialize_turtle()


@app.get("/api/legal-ontology.jsonld")
def legal_ontology_jsonld():
    return Response(content=legal_ontology_store.serialize_jsonld(), media_type="application/ld+json")


@app.get("/api/article5/explorer")
def article5_explorer():
    practices = []
    rights: dict[str, dict] = {}
    graph = legal_ontology_store.get_graph()
    for practice in legal_ontology_store.get_prohibited_practices():
        practice_id = practice["id"]
        affected_rights = legal_ontology_store.get_affected_rights(practice_id)
        exceptions = legal_ontology_store.get_exceptions(practice_id)
        conditions = [item for item in legal_ontology_store.get_required_elements(practice_id) if item["label"].startswith("requires Condition:")]
        elements = [item for item in legal_ontology_store.get_required_elements(practice_id) if not item["label"].startswith("requires Condition:")]
        anchors = legal_ontology_store.get_source_anchors(practice_id)
        for right in affected_rights:
            rights.setdefault(
                right["id"],
                {"id": right["id"], "label": right["label"], "uri": right["uri"], "linked_practices": []},
            )
            rights[right["id"]]["linked_practices"].append({"id": practice_id, "label": practice["label"]})
        practices.append(
            {
                **practice,
                "group": "amended" if practice.get("legal_status") == "amended_article5" else "original",
                "article_ref": _article_ref(anchors),
                "elements": elements,
                "exceptions": exceptions,
                "conditions": conditions,
                "derogations": legal_ontology_store.get_derogations(practice_id),
                "rights": affected_rights,
                "source_anchors": anchors,
                "rdf_triples": _resource_triples(graph, practice["uri"]),
            }
        )
    return {"practices": practices, "rights": sorted(rights.values(), key=lambda item: item["label"])}


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "analysis_available": article5_reasoner.available,
        "active_analysis_path": "ontology_first_article5",
        "akn_file_loaded": Path(akn_path).exists() and len(corpus.articles) > 0,
        "akn_xml_path": str(akn_path),
        "akomantoso_xsd_path": str(settings.resolve_path(settings.akomantoso_xsd_path)),
        "xml_xsd_path": str(settings.resolve_path(settings.xml_xsd_path)),
        "akn_validation": akn_validation.model_dump(),
        "source_index_loaded": bool(source_index and source_index.is_loaded),
        "source_index_errors": source_index.errors if source_index else ["Source index unavailable because AKN validation did not pass."],
        "legal_ontology_directory": str(settings.resolve_path(settings.legal_ontology_dir)),
        "legal_ontology_loaded": legal_ontology_store.status.loaded,
        "legal_ontology_valid": legal_ontology_store.status.is_valid,
        "legal_ontology_status": legal_ontology_store.status.model_dump(),
        "legacy_json_rule_path_removed": True,
        "articles_parsed": len([a for a in corpus.articles if a.source_type == "AKN"]),
        "legal_source_warnings": corpus.warnings,
        "llm_available": llm_agent.available(),
    }


def _article_ref(anchors: list[dict]) -> str:
    if not anchors:
        return "Article 5"
    labels = [anchor.get("label") or anchor.get("source_anchor") for anchor in anchors]
    return ", ".join(label.replace("Omnibus", "Amended") for label in labels if label) or "Article 5"


def _resource_triples(graph, uri: str) -> list[dict[str, str]]:
    subject = URIRef(uri)
    triples = []
    for predicate, obj in graph.predicate_objects(subject):
        triples.append({"predicate": _compact_uri(predicate), "object": _compact_uri(obj)})
    return triples


def _compact_uri(value) -> str:
    if isinstance(value, URIRef):
        label = next(legal_ontology_store.get_graph().objects(value, RDFS.label), None)
        if label:
            return str(label)
        text = str(value)
        return text.rstrip("/#").split("#")[-1].split("/")[-1]
    return str(value)
