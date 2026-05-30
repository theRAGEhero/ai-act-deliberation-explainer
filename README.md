# AI Act Prohibitions Checker

AI Act Prohibitions Checker is a FastAPI application that turns a short AI-use scenario, meeting note, or transcript into a preliminary legal-design map under the EU AI Act.

A traceable, ontology-assisted approach to evaluate whether an AI system is prohibited under the AI Act.

The app is designed to support discussion, teaching, workshops, and early issue spotting. It connects four layers:

- citizen-readable explanations
- deterministic ontology-first legal-design signals
- AI Act source references
- machine-readable ontology output

It does not provide legal advice, certify compliance, or decide whether an AI system is legal, illegal, compliant, or non-compliant.

## What The App Does

Given a text input, the app:

1. Normalizes the text and splits it into claims.
2. Extracts candidate factual signals without making a legal conclusion.
3. Validates and indexes the Akoma Ntoso AI Act source-law file.
4. Loads the reviewed Article 5 RDF ontology from `data/ontology/`.
5. Checks only the legal elements, rights, exceptions, conditions, and source anchors defined in that RDF.
6. Separates current binding AI Act material from Omnibus/proposed/amending material.
7. Builds a traceability table from input snippets to ontology elements and Article 5 source anchors.
8. Produces a citizen-facing explanation.
9. Exposes the result as JSON.
10. Exposes RDF ontology exports as Turtle and JSON-LD.
11. Shows visual maps in the browser, including network, trace-flow, actor, risk, source, obligation, lifecycle, and question views.

The app is intentionally cautious. Its output is a structured discussion aid, not a legal conclusion.

## Current Public Deployment

The app is deployed at:

```text
https://ai-act.democracyroutes.com
```

The production service runs behind Nginx and HTTPS. The FastAPI app itself listens locally on the server and is proxied by Nginx.

## Example Input

```text
Municipality X wants to use an AI system to rank social housing applications.
The model uses historical welfare data. A human officer can approve the final
decision, but applicants will not see the score.
```

Expected result:

- the app attempts to run the ontology-first Article 5 pipeline
- if the reviewed legal ontology is missing, the response explicitly says `Legal analysis unavailable`
- the app does not fall back to JSON keyword rules

Example Article 5 input:

```text
A public authority uses an AI system for social scoring based on social
behaviour and personality characteristics. The score can cause detrimental
treatment in access to services.
```

Expected behavior before the reviewed Article 5 ontology is added:

- no legal conclusion is produced
- `raw_rule_output.status` is `analysis_unavailable`
- the response explains which source-law or ontology configuration is missing

All signals still require human legal review.

## Main Features

### Browser Interface

`GET /` serves the HTML interface in `app/templates/index.html`.

The page lets a user:

- paste a scenario or transcript
- upload a `.txt` file
- optionally request LLM refinement if configured
- view ontology-derived legal elements, exceptions/conditions, source anchors, rights/interests, missing questions, traceability, visual maps, and raw JSON

### Ontology-First Analysis Path

`POST /api/analyze` now uses an ontology-first Article 5 pipeline. The active path is:

```text
Akoma Ntoso AI Act XML
  -> XSD validation
  -> source anchors for Article 3 and Article 5
  -> reviewed Article 5 RDF ontology
  -> legal element checker
  -> structured JSON output
```

There is no runtime switch back to the old JSON-rule path. `data/seed_prohibitions.json` remains in the repository only as historical material and is not used by `/api/analyze`.

If the source XML, XSD validation, source index, or reviewed legal ontology is missing or invalid, the API returns HTTP 200 with a valid `AnalysisResponse` whose `case_summary` is `Legal analysis unavailable`. This is intentional fail-closed behavior, not an application crash.

### Legal Source Layer

The active source-law file is the hackathon-provided Akoma Ntoso XML:

```text
reference/akoma-ntoso/aiAct-2024-1689.xml
```

It is validated against:

```text
reference/akoma-ntoso/akomantoso30.xsd
reference/akoma-ntoso/xml.xsd
```

`app/legal_source/source_index.py` preserves source anchors for:

- Article 3 definitions
- Article 5
- Article 5(1)(a)-(h)
- nested Article 5(1)(c)(i)-(ii)
- nested Article 5(1)(h)(i)-(iii)

The repository now uses `reference/akoma-ntoso/aiAct-2024-1689.xml` as the single AI Act Akoma Ntoso source file.

### Reviewed Legal Ontology

The reviewed Article 5 RDF ontology is stored as Turtle at:

```text
data/ontology/article5_reviewed.ttl
```

`app/ontology/legal_ontology_store.py` merges `.ttl` files from `data/ontology/` and validates the vocabulary expected by the reasoner. The ontology includes current AI Act Article 5 material and separately marked Omnibus/amending material. The active current-law reasoner skips Omnibus practices by default.

### Ontology Layer

`app/ontology/ontology_builder.py` builds an RDF graph from:

- `data/seed_concepts.json`
- `data/seed_annexes.json`
- parsed AI Act article metadata

The ontology models:

- AI Act articles
- actors
- concepts
- risks
- rights/interests
- obligations
- scenarios
- evidence snippets
- missing questions
- Annex III areas

The active legal-analysis workflow is:

```text
input text -> fact extraction -> reviewed Article 5 RDF ontology elements
           -> source anchors from validated AKN -> structured JSON response
```

The graph can be exported as:

- Turtle: `GET /api/ontology.ttl`
- JSON-LD: `GET /api/ontology.jsonld`

Generated copies are stored in:

```text
generated/ontology.ttl
generated/ontology.jsonld
```

### Optional OpenRouter Refinement

`app/analysis/llm_agent.py` can call OpenRouter when `OPENROUTER_API_KEY` is configured.

OpenRouter exposes an OpenAI-compatible API, so the app uses the Python `openai` SDK as the transport client while sending requests to:

```text
https://openrouter.ai/api/v1
```

When enabled, OpenRouter receives:

- the user's input text
- the deterministic rule output
- selected legal source snippets
- ontology concepts

The model is instructed to stay within the provided sources and to preserve the non-legal-advice boundary. If no OpenRouter API key is configured, the app runs fully in deterministic mode.

The OpenRouter prompt is also scoped to Article 5. It is instructed not to invent prohibited-practice matches and not to add rights, trigger conditions, safeguards, contexts, targets, exceptions, or legal elements beyond the reviewed RDF/source-law material supplied by the backend.

For public deployments, OpenRouter refinement should be treated carefully because user text may contain personal, sensitive, or confidential information.

## API

### `GET /`

Returns the browser interface.

### `POST /api/analyze`

Analyzes JSON input.

The `text` field is limited to 20,000 characters.

Request:

```json
{
  "title": "Optional title",
  "text": "Scenario or transcript text",
  "persona": "citizen",
  "use_llm": false
}
```

Response:

Returns an `AnalysisResponse` with:

- `case_summary`
- `matched_prohibited_practices`
- `detected_actors`
- `detected_contexts`
- `detected_ai_functions`
- `possible_risks`
- `possible_rights_or_interests`
- `obligations_to_verify`
- `missing_questions`
- `relevant_ai_act_sources`
- `traceability`
- `citizen_explanation`
- `disclaimer`
- `raw_rule_output`
- `rdf_triples_preview`
- `markdown_summary`
- `graph`

### `POST /api/upload`

Analyzes an uploaded `.txt` file.

Uploaded text is capped to the same analysis limit. The app reads at most 80,000 bytes and rejects larger uploads.

Query parameter:

```text
use_llm=false
```

### `GET /api/articles`

Returns parsed or seeded AI Act article metadata.

### `GET /api/articles/{number}`

Returns one article by number.

Example:

```text
GET /api/articles/13
```

### `GET /api/ontology.ttl`

Returns the ontology as Turtle.

### `GET /api/ontology.jsonld`

Returns the ontology as JSON-LD.

### `GET /api/health`

Returns runtime health information:

- app status
- whether the AKN file loaded
- number of parsed AI Act articles
- parser warnings
- RDF triple count
- whether OpenRouter refinement is available

## Project Structure

```text
app/
  main.py                       FastAPI routes and app wiring
  config.py                     Environment-based settings
  models.py                     Pydantic request/response models
  analysis/
    input_processor.py          Text normalization, claims, keywords
    rule_engine.py              Legacy/deprecated JSON-rule engine, not wired to /api/analyze
    report_builder.py           Final response, markdown, graph data
    llm_agent.py                Optional OpenRouter refinement
    prompt_templates.py         LLM prompts
  legal_source/
    akn_parser.py               Akoma Ntoso XML parser
    akn_validator.py            Local XSD validation for AKN source law
    source_index.py             Article 3 / Article 5 source anchors
    legal_db.py                 In-memory legal article store
    article_selector.py         Legacy concept-to-article mapping
  ontology/
    legal_ontology_store.py     Reviewed legal ontology loader/validator
    case_graph.py               Per-analysis RDF debug graph
    ontology_builder.py         RDF graph construction
    ontology_store.py           Ontology access and serialization
    export.py                   File export helper
  static/style.css              Browser UI styles
  static/icons/rights/          Optimized right/interests icons used in results
  templates/index.html          Browser UI and client-side visual maps

  reasoning/
    fact_extractor.py           Non-legal fact/evidence extraction
    legal_element_checker.py    Legal element status objects
    article5_reasoner.py        Ontology-first Article 5 reasoner

data/
  ontology/                     Reviewed Article 5 RDF ontology files
  seed_concepts.json            Seed actors, concepts, risks, rights, obligations
  seed_annexes.json             Seed Annex III areas and questions
  seed_prohibitions.json        Historical JSON mapping, not active legal source
  sample_transcripts/           Example text inputs

generated/
  ontology.ttl                  Generated Turtle ontology
  ontology.jsonld               Generated JSON-LD ontology

reference/
  akoma-ntoso/                  Hackathon-provided AKN XML and schemas
  icons/                        Original extracted icon artwork for reference

scripts/
  parse_ai_act.py               Parser check script
  build_ontology.py             Rebuild generated ontology files

tests/
  test_akn_parser.py
  test_api.py
  test_ontology_builder.py
  test_rule_engine.py
  test_ontology_first_architecture.py
```

## Local Setup

Create a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Start the app:

```bash
uvicorn app.main:app --reload
```

Open:

```text
http://localhost:8000
```

## Environment Variables

Copy `.env.example` to `.env` if needed:

```bash
cp .env.example .env
```

Supported variables:

```text
OPENROUTER_API_KEY=
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
OPENROUTER_MODEL=moonshotai/kimi-k2.6:free
OPENROUTER_SITE_URL=https://ai-act.democracyroutes.com
OPENROUTER_APP_TITLE=AI Act Prohibitions Checker
AI_ACT_AKN_PATH=reference/akoma-ntoso/aiAct-2024-1689.xml
AKOMANTOSO_XSD_PATH=reference/akoma-ntoso/akomantoso30.xsd
XML_XSD_PATH=reference/akoma-ntoso/xml.xsd
AKOMANTOSO_REFERENCE_PATH=reference/akoma-ntoso/akomantoso30.xml
LEGAL_ONTOLOGY_DIR=data/ontology
```

If `OPENROUTER_API_KEY` is empty, OpenRouter refinement is unavailable. It is never used as a legal fallback.

## Legal Source Data

The preferred legal source is the AI Act Akoma Ntoso XML file:

```text
reference/akoma-ntoso/aiAct-2024-1689.xml
```

The runtime default points to `reference/akoma-ntoso/aiAct-2024-1689.xml`.

The original right/interests icon artwork is kept under `reference/icons/`. The UI uses smaller cleaned PNG copies in `app/static/icons/rights/` so result pages do not load the large reference images directly.

To check parsing:

```bash
python scripts/parse_ai_act.py
```

To rebuild ontology exports:

```bash
python scripts/build_ontology.py
```

## Tests

Run tests with the project root on `PYTHONPATH`:

```bash
PYTHONPATH=. pytest
```

The test suite covers parsing, ontology generation, Article 5 rule-engine behavior, API route functions, input limits, and the no-sufficient-signal path.

## Production Deployment Notes

The current public deployment uses:

- systemd service: `ai-act-deliberation-explainer.service`
- app bind address: `127.0.0.1:8097`
- reverse proxy: Nginx
- public domain: `https://ai-act.democracyroutes.com`
- TLS: Let's Encrypt / Certbot
- Nginx body limit: `256k`
- Nginx API rate limit: `12r/m` per IP with small bursts for `/api/analyze` and `/api/upload`
- security headers: CSP, HSTS, `X-Frame-Options`, `X-Content-Type-Options`, `Referrer-Policy`, and `Permissions-Policy`
- systemd hardening: restart limits, `NoNewPrivileges`, private temp/devices, read-only system/home protection, kernel/control-group protections, task limits, and memory cap

Recommended hardening before relying on this as a public service:

- keep dependency versions pinned
- keep app-level input length limits enabled
- keep Nginx or application rate limiting enabled
- move the deployment out of `/root` and run the service under a dedicated non-root user
- keep systemd sandboxing options enabled
- keep CSP, HSTS, and Permissions-Policy headers enabled
- keep OpenRouter refinement disabled unless privacy and data-sharing notices are in place

## Known Limitations

- The rule engine is keyword-based and can miss relevant Article 5 issues or over-detect weak signals.
- The deterministic legal-source selection is intentionally limited to Article 5.
- The app does not perform a complete AI Act classification.
- The app does not decide whether a use case is high-risk, prohibited, compliant, or unlawful.
- The ontology is intentionally small and should be expanded for deeper legal reasoning.
- Uploaded text is processed in memory and is not persisted by the application.
- Public deployments still need monitoring in addition to rate limiting and input-size controls.

## Design Boundary

The application is an explainer and mapping tool. It should help people understand possible AI Act relevance by linking text, concepts, legal sources, visual maps, and machine-readable output.

It should not be presented as:

- a legal advice system
- a compliance certification tool
- a substitute for expert legal review
- a complete AI Act risk-classification engine

## License

See `LICENSE`.
