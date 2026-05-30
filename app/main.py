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
from app.ontology.ontology_store import OntologyStore
from app.reasoning.article5_reasoner import Article5Reasoner
from app.models import MAX_TEXT_LENGTH, AnalysisResponse, CaseInputRequest


MAX_UPLOAD_BYTES = MAX_TEXT_LENGTH * 4

app = FastAPI(title="AI Act Prohibitions Checker")
app.mount("/static", StaticFiles(directory=settings.project_root / "app/static"), name="static")
templates = Jinja2Templates(directory=settings.project_root / "app/templates")

legal_db = LegalKnowledgeDB(settings.resolve_path(settings.seed_concepts_path))
akn_path = settings.resolve_path(settings.ai_act_akn_path)
corpus = legal_db.load_from_akn(akn_path)
ontology_store = OntologyStore(settings.resolve_path(settings.seed_concepts_path), settings.resolve_path(settings.seed_annexes_path), legal_db)
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
    preliminary = article5_reasoner.analyze(case_input)
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


@app.get("/api/ontology.ttl", response_class=PlainTextResponse)
def ontology_ttl():
    return ontology_store.serialize_turtle()


@app.get("/api/ontology.jsonld")
def ontology_jsonld():
    return Response(content=ontology_store.serialize_jsonld(), media_type="application/ld+json")


@app.get("/api/legal-ontology.ttl", response_class=PlainTextResponse)
def legal_ontology_ttl():
    return legal_ontology_store.serialize_turtle()


@app.get("/api/legal-ontology.jsonld")
def legal_ontology_jsonld():
    return Response(content=legal_ontology_store.serialize_jsonld(), media_type="application/ld+json")


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
        "seed_prohibitions_unused_by_active_analysis_path": True,
        "articles_parsed": len([a for a in corpus.articles if a.source_type == "AKN"]),
        "legal_source_warnings": corpus.warnings,
        "ontology_triples_count": len(ontology_store.get_graph()),
        "llm_available": llm_agent.available(),
        "openrouter_available": llm_agent.available(),
    }
