from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import HTMLResponse, PlainTextResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi import Request

from app.analysis.input_processor import build_case_input
from app.analysis.llm_agent import OptionalLLMAgent
from app.analysis.report_builder import ReportBuilder
from app.analysis.rule_engine import RuleEngine
from app.config import settings
from app.legal_source.legal_db import LegalKnowledgeDB
from app.ontology.ontology_store import OntologyStore
from app.models import AnalysisResponse, CaseInputRequest

app = FastAPI(title="AI Act Deliberation Explainer")
app.mount("/static", StaticFiles(directory=settings.project_root / "app/static"), name="static")
templates = Jinja2Templates(directory=settings.project_root / "app/templates")

legal_db = LegalKnowledgeDB(settings.resolve_path(settings.seed_concepts_path))
akn_path = settings.resolve_path(settings.ai_act_akn_path)
corpus = legal_db.load_from_akn(akn_path)
ontology_store = OntologyStore(settings.resolve_path(settings.seed_concepts_path), settings.resolve_path(settings.seed_annexes_path), legal_db)
rule_engine = RuleEngine(settings.resolve_path(settings.seed_annexes_path), settings.resolve_path(settings.seed_concepts_path))
report_builder = ReportBuilder()
llm_agent = OptionalLLMAgent()


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    return templates.TemplateResponse(request, "index.html")


@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    return Response(status_code=204)


@app.post("/api/analyze", response_model=AnalysisResponse)
def analyze(payload: CaseInputRequest):
    if not payload.text.strip():
        raise HTTPException(status_code=400, detail="Text is required")
    case_input = build_case_input(payload.text, payload.title, payload.persona)
    preliminary = rule_engine.analyze(case_input, legal_db, ontology_store)
    llm_output = None
    if payload.use_llm:
        llm_output = llm_agent.refine(
            payload.text,
            preliminary.model_dump(),
            [src.model_dump() for src in preliminary.relevant_ai_act_sources],
            list(case_input.keywords),
        )
    rdf_preview = "\n".join(ontology_store.serialize_turtle().splitlines()[:80])
    return report_builder.build(preliminary, rdf_preview, llm_output)


@app.post("/api/upload", response_model=AnalysisResponse)
async def upload(file: UploadFile = File(...), use_llm: bool = False):
    if not file.filename.lower().endswith(".txt"):
        raise HTTPException(status_code=400, detail="Only .txt files are supported")
    content = (await file.read()).decode("utf-8", errors="replace")
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


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "akn_file_loaded": Path(akn_path).exists() and len(corpus.articles) > 0,
        "articles_parsed": len([a for a in corpus.articles if a.source_type == "AKN"]),
        "legal_source_warnings": corpus.warnings,
        "ontology_triples_count": len(ontology_store.get_graph()),
        "llm_available": llm_agent.available(),
    }
