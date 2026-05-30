# AI Act Prohibitions Checker

AI Act Prohibitions Checker is a FastAPI web application for mapping a short AI-use scenario to possible EU AI Act Article 5 prohibited-practice signals.

It is built as an ontology-first legal-design explainer:

- the Akoma Ntoso XML file is the source-law layer;
- the reviewed RDF/OWL Turtle file is the legal model;
- deterministic Python code extracts factual signals and checks ontology-defined legal elements;
- JSON, markdown, graph data, and UI cards are output formats, not sources of law;
- optional LLM assistance can suggest contextual facts and improve explanation text, but cannot create legal findings or replace the ontology-gated path.

The app is a discussion, teaching, and issue-spotting tool. It is not legal advice, compliance certification, or a final AI Act risk classification.

## System Overview

```text
                          Repository / Runtime Boundaries

  reference/akoma-ntoso/                 data/ontology/
  ----------------------                 --------------
  AI Act XML source law                  reviewed Article 5 RDF/OWL model
  AKN schema files                       original + amended Article 5 practices
           |                                      |
           v                                      v
  app/legal_source/                     app/ontology/
  -----------------                     -------------
  XSD validation                        Turtle loading
  Article 3/5 source indexing           vocabulary validation
  FRBR / CELEX / eId anchors            practice/element/right/exception queries
           |                                      |
           +------------------+-------------------+
                              |
                              v
                    app/reasoning/
                    --------------
                    deterministic fact extraction
                    legal element status checks
                    Article 5 candidate assembly
                              |
                              v
                    app/analysis/report_builder.py
                    -------------------------------
                    API JSON, markdown, graph, UI data
```

The active legal-analysis path is deliberately narrow and auditable:

```text
User text
   |
   v
CaseInput
   |
   v
FactExtractor
   |
   |  candidate evidence only
   |  no legal conclusion here
   v
LegalOntologyStore  <--------- data/ontology/article5_reviewed.ttl
   |
   v
LegalElementChecker
   |
   |  supported / missing / uncertain / contradicted /
   |  exception_possible / not_applicable
   v
Article5Reasoner  <----------- validated AKN source index
   |
   v
PreliminaryAnalysis
   |
   v
ReportBuilder
   |
   +--> AnalysisResponse JSON
   +--> browser result hierarchy
   +--> graph nodes/edges
   +--> case RDF preview
   +--> optional LLM candidate facts / wording refinement
```

## Academic Design Position

The core design choice is that the law is not embedded in prompts or keyword rules.

```text
Not this:

  input text -> LLM prompt -> legal answer

But this:

  input text -> deterministic evidence extraction
             -> optional LLM-suggested candidate facts
             -> reviewed RDF legal model
             -> validated AKN source anchors
             -> structured preliminary output
             -> optional wording refinement
```

This makes the project easier to defend:

- **Traceability:** legal outputs are linked to Article 5 source anchors where available.
- **Source separation:** AKN XML is source-law material; RDF/OWL is the reviewed model; JSON is output.
- **Determinism:** the same input, source XML, and ontology produce the same backend result.
- **Fail-closed behavior:** missing or invalid legal sources produce `analysis_unavailable`; there is no silent fallback.
- **Amended Article 5 boundary:** amended Article 5 material is grouped separately for clarity and integrated in this prototype.
- **LLM containment:** LLM usage is optional, provenance-labelled, and limited to candidate fact suggestions plus wording.

## Deterministic Workflow Boundary

The system separates **context discovery** from **legal validation**.

```text
                               SAME LEGAL ENGINE IN BOTH MODES

                    +---------------------------------------------+
                    |  validated AKN source law                   |
                    |  reference/akoma-ntoso/aiAct-2024-1689.xml  |
                    +----------------------+----------------------+
                                           |
                                           v
                    +---------------------------------------------+
                    |  reviewed RDF/OWL Article 5 ontology        |
                    |  data/ontology/article5_reviewed.ttl        |
                    +----------------------+----------------------+
                                           |
                                           v
                    +---------------------------------------------+
                    |  deterministic legal element checker        |
                    |  supported / missing / exception_possible   |
                    +----------------------+----------------------+
                                           |
                                           v
                    +---------------------------------------------+
                    |  Article5Reasoner                           |
                    |  no JSON rule fallback                      |
                    |  no LLM-created legal conclusion            |
                    +----------------------+----------------------+
                                           |
                                           v
                    +---------------------------------------------+
                    |  structured AnalysisResponse                |
                    |  traceability + source anchors + disclaimer |
                    +---------------------------------------------+
```

The only optional variation is how candidate facts are discovered before the legal checker runs:

```text
DETERMINISTIC MODE

  user text
     |
     v
  regex / controlled vocabulary extractor
     |
     v
  candidate_facts[]
     provenance = "deterministic"
     |
     v
  RDF/AKN-gated legal validation


LLM-ASSISTED MODE

  user text
     |
     +------------------------------+
     |                              |
     v                              v
  deterministic extractor       LLM candidate-fact extractor
     |                              |
     |                              v
     |                         JSON candidate facts only
     |                         exact evidence snippets required
     |                         allowed ontology candidates only
     |                              |
     +--------------+---------------+
                    |
                    v
             backend validation gate
             rejects unsupported or unevidenced facts
                    |
                    v
             candidate_facts[]
             provenance = "deterministic" or "llm_suggested"
                    |
                    v
             RDF/AKN-gated legal validation
```

The LLM can therefore help with language such as:

```text
"boss of the farm"       -> suggested Workplace context
"cameras connected to AI" -> suggested CameraMonitoring context
"animals eat the plants" -> suggested AnimalPlantTarget
```

But it cannot do this:

```text
"boss of the farm" -> Article 5 violation
```

The backend still requires ontology-defined legal elements and source-law anchors before it reports a grounded Article 5 candidate.

## Public Deployment

```text
https://ai-act.democracyroutes.com
```

The deployment uses Nginx and HTTPS in front of a local FastAPI service.

```text
Internet
   |
   v
Nginx + TLS + rate limits + body limits
   |
   v
127.0.0.1:8097
   |
   v
uvicorn app.main:app
```

## Repository Layout

```text
app/
  main.py                       FastAPI app, route wiring, runtime singletons
  config.py                     Environment and path settings
  models.py                     Pydantic request/response/domain models

  analysis/
    input_processor.py          Builds CaseInput from user text
    report_builder.py           Converts PreliminaryAnalysis to API/UI output
    llm_agent.py                Optional LLM candidate facts and wording refinement
    prompt_templates.py         LLM prompt text

  legal_source/
    akn_parser.py               Parses Akoma Ntoso articles for article endpoints
    akn_validator.py            Validates AI Act XML against local XSD files
    legal_db.py                 In-memory article/definition store
    source_index.py             Article 3 and Article 5 source-anchor index

  ontology/
    legal_ontology_store.py     Reviewed Article 5 RDF/OWL loader and validator
    case_graph.py               Per-analysis RDF graph builder

  reasoning/
    fact_extractor.py           Deterministic candidate-fact extraction
    legal_element_checker.py    Maps candidate facts to ontology elements
    article5_reasoner.py        Ontology-first Article 5 reasoner

  static/
    favicon.svg
    style.css
    icons/rights/               Optimized UI icons used in result cards

  templates/
    index.html                  Browser UI and client-side graph rendering

data/
  ontology/
    article5_reviewed.ttl       Reviewed Article 5 legal ontology
  supporting/
    seed_concepts.json          Non-legal labels used by the article/definition store

reference/
  akoma-ntoso/
    aiAct-2024-1689.xml         Source-law XML used by the app
    akomantoso30.xml            Hackathon/reference AKN material
    akomantoso30.xsd            AKN schema
    xml.xsd                     XML namespace schema dependency
  hackathon/
    LegalDesign-LAST_JD-2026-hackathon.pdf

examples/
  sample-inputs/                Example text inputs for manual testing/demo

scripts/
  parse_ai_act.py               Parser smoke-check script

tests/
  test_akn_parser.py
  test_api.py
  test_ontology_first_architecture.py
```

Important distinction:

```text
data/ontology/      = reviewed legal model used by Article5Reasoner
data/supporting/    = support data for broad ontology export endpoints
reference/          = external/legal/hackathon source materials
generated/          = rebuildable export artifacts
examples/           = demo inputs only
```

## Runtime Initialization

`app/main.py` creates the runtime components once at import/startup:

```text
settings
   |
   +--> LegalKnowledgeDB
   |       loads AKN articles for /api/articles
   |
   +--> validate_akn_xml(...)
   |       validates reference/akoma-ntoso/aiAct-2024-1689.xml
   |
   +--> LegalSourceIndex
   |       available only if AKN validation succeeds
   |
   +--> LegalOntologyStore
   |       loads and validates data/ontology/*.ttl
   |
   +--> Article5Reasoner
   |       receives ontology store + source index + validation status
   |
   +--> ReportBuilder / CaseGraphBuilder / OptionalLLMAgent
```

If AKN validation fails, the source index is not used. If the source index or legal ontology is unavailable, analysis fails closed.

## Source-Law Layer

The active source-law file is:

```text
reference/akoma-ntoso/aiAct-2024-1689.xml
```

The validator uses:

```text
reference/akoma-ntoso/akomantoso30.xsd
reference/akoma-ntoso/xml.xsd
```

`app/legal_source/source_index.py` indexes:

- Article 3 definitions;
- Article 5 as a whole;
- Article 5(1)(a)-(h);
- nested Article 5(1)(c)(i)-(ii);
- nested Article 5(1)(h)(i)-(iii);
- Article 5(2)-(7) source anchors where available.

Each source node can preserve:

- article number;
- heading;
- paragraph;
- point;
- `eId`;
- text;
- FRBR URI;
- CELEX identifier.

## Reviewed Legal Ontology

The active reviewed ontology is:

```text
data/ontology/article5_reviewed.ttl
```

`LegalOntologyStore` loads every `.ttl` file in `data/ontology/`, merges them into one `rdflib.Graph`, and validates that the supported vocabulary is present.

It exposes query methods for:

- prohibited practices;
- required legal elements;
- exceptions;
- required exception/condition elements;
- affected rights;
- source anchors;
- original vs amended Article 5 material.

The app currently supports the reviewed CIRSFID-style Article 5 vocabulary and a small `aid:` fixture vocabulary used by tests.

## Reasoning Model

The reasoner does not use an LLM and does not use a JSON rule fallback.

```text
Candidate facts:
  extracted from input text by deterministic patterns

Ontology elements:
  loaded from reviewed RDF/OWL triples

Element checker:
  compares facts to ontology-required elements
  returns structured LegalElementResult objects

Article5Reasoner:
  includes a candidate practice only when enough ontology-defined elements
  are supported by evidence
```

Element statuses are represented as strings:

```text
supported
missing
uncertain
contradicted
exception_possible
not_applicable
```

The first implementation is intentionally conservative. It provides element-level explainability and traceability, not a complete formal legal reasoner.

## Fail-Closed Behavior

Expected configuration/source failures do not crash the app and do not return HTTP 500.

If the AKN file, XSD validation, source index, or legal ontology is missing or invalid, `/api/analyze` returns HTTP 200 with a valid `AnalysisResponse`:

```text
case_summary: "Legal analysis unavailable"
matched_prohibited_practices: []
missing_questions: configuration/source/model questions
notes: includes "analysis_unavailable"
disclaimer: says no legal assessment was performed
raw_rule_output.status: "analysis_unavailable"
```

This is intentional. It prevents the app from silently substituting a weaker legal source.

## Optional LLM Candidate-Fact Assistance

The backend can use the LLM in two limited ways when `use_llm=true` and a provider is configured:

1. candidate-fact assistance before legal-element checking;
2. wording refinement after deterministic analysis.

The LLM does not decide whether Article 5 applies.

```text
User text
          |
          +-- deterministic facts always run
          |
          +-- if use_llm=true and provider configured
                    |
                    v
             LLM suggests candidate facts
             evidence snippets must appear in the input text
             unsupported ontology candidates are rejected
                    |
                    v
             Article5Reasoner checks facts against RDF elements
                    |
                    v
             optional LLM wording refinement
```

Accepted LLM-suggested facts are marked with:

```text
provenance: "llm_suggested"
```

The LLM fact extractor receives:

- the user text;
- an allowed list of candidate ontology/context labels.

It must return exact evidence snippets copied from the input. The backend rejects unsupported candidates and candidates without direct evidence.

The LLM wording refiner receives:

- the user text;
- the deterministic preliminary output;
- selected legal source snippets;
- ontology-derived concepts.

It is instructed not to invent:

- prohibited-practice matches;
- affected rights;
- trigger conditions;
- safeguards;
- contexts;
- targets;
- exceptions;
- legal elements.

Example broad-context behavior:

```text
Input: "In a farm, the boss of the farm wants to put cameras connected to AI to check if animals eat the plants."

LLM may suggest:
  Workplace context       evidence: "boss of the farm"
  Camera monitoring       evidence: "cameras connected to AI"
  Animal/plant target     evidence: "animals eat the plants"

Backend result:
  No grounded Article 5 prohibited-practice match unless RDF-required elements are supported.
  Missing questions ask whether workers are recorded, evaluated, identified, emotionally analyzed, or subject to decisions.
```

Environment variables currently use OpenRouter naming because the configured provider exposes an OpenAI-compatible endpoint:

```text
OPENROUTER_API_KEY=
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
OPENROUTER_MODEL=moonshotai/kimi-k2.6:free
OPENROUTER_SITE_URL=https://ai-act.democracyroutes.com
OPENROUTER_APP_TITLE=AI Act Prohibitions Checker
```

If no API key is configured, the app runs fully in deterministic mode.

## Browser UI

`GET /` serves `app/templates/index.html`.

The UI supports:

- direct text input;
- `.txt` upload;
- optional LLM context suggestions and wording refinement;
- result cards for matched practices;
- legal element status display;
- exception/condition display;
- affected-right icons;
- source-anchor details;
- traceability rows;
- graph/ontology views;
- raw JSON output.

UI icons are loaded from:

```text
app/static/icons/rights/
```

The original large extracted icon sources were removed; only optimized runtime icons are kept.

## API Reference

### `GET /`

Returns the browser interface.

### `POST /api/analyze`

Analyzes a JSON scenario.

Input limits:

- `text`: 1 to 20,000 characters;
- `title`: maximum 160 characters;
- `persona`: maximum 80 characters.

Request:

```json
{
  "title": "Optional title",
  "text": "Scenario or transcript text",
  "persona": "citizen",
  "use_llm": false
}
```

Response model: `AnalysisResponse`.

Important fields:

```text
case_summary
candidate_facts
matched_prohibited_practices
detected_actors
detected_contexts
detected_ai_functions
possible_risks
possible_rights_or_interests
obligations_to_verify
missing_questions
relevant_ai_act_sources
traceability
notes
citizen_explanation
disclaimer
raw_rule_output          historical field name retained for API compatibility
rdf_triples_preview
markdown_summary
graph
```

### `POST /api/upload`

Analyzes an uploaded `.txt` file.

Limits:

- only `.txt`;
- reads at most 80,001 bytes;
- rejects content above the 20,000-character analysis limit.

Query parameter:

```text
use_llm=false
```

### `GET /api/articles`

Returns parsed AI Act article metadata.

### `GET /api/articles/{number}`

Returns one parsed article.

Example:

```text
GET /api/articles/5
```

### `GET /api/legal-ontology.ttl`

Returns the merged reviewed legal ontology from `LegalOntologyStore` as Turtle.

### `GET /api/legal-ontology.jsonld`

Returns the merged reviewed legal ontology as JSON-LD.

### `GET /api/health`

Returns runtime status, including:

- active analysis path;
- analysis availability;
- AKN XML path;
- XSD paths;
- AKN validation result;
- source index status;
- legal ontology directory;
- legal ontology load/validation status;
- Article count;
- legal source warnings;
- broad ontology triple count;
- LLM availability;
- `legacy_json_rule_path_removed`.

## Data Flow In More Detail

```text
                  +-------------------------+
                  |  POST /api/analyze      |
                  +-----------+-------------+
                              |
                              v
                  +-------------------------+
                  |  CaseInputRequest       |
                  |  Pydantic limits        |
                  +-----------+-------------+
                              |
                              v
                  +-------------------------+
                  |  build_case_input       |
                  |  text normalization     |
                  +-----------+-------------+
                              |
                              v
                  +-------------------------+
                  |  Article5Reasoner       |
                  +-----------+-------------+
                              |
            +-----------------+------------------+
            |                                    |
            v                                    v
 +----------------------+             +----------------------+
 | FactExtractor        |             | LegalOntologyStore   |
 | candidate facts      |             | RDF practices        |
 | evidence snippets    |             | elements/exceptions  |
 +----------+-----------+             +----------+-----------+
            |                                    |
            +-----------------+------------------+
                              |
                              v
                  +-------------------------+
                  | LegalElementChecker     |
                  | supported/missing/etc.  |
                  +-----------+-------------+
                              |
                              v
                  +-------------------------+
                  | Source anchors          |
                  | from LegalSourceIndex   |
                  +-----------+-------------+
                              |
                              v
                  +-------------------------+
                  | PreliminaryAnalysis     |
                  +-----------+-------------+
                              |
                              v
                  +-------------------------+
                  | ReportBuilder           |
                  +-----------+-------------+
                              |
              +---------------+----------------+
              |                                |
              v                                v
   +----------------------+          +----------------------+
   | AnalysisResponse     |          | Browser rendering    |
   | JSON                 |          | cards/graphs/tables  |
   +----------------------+          +----------------------+
```

## Case Graph Preview

For each analysis, `CaseGraphBuilder` creates a temporary RDF graph separate from the static legal ontology.

```text
scenario
   |
   +-- hasEvidence ------------> evidence snippet
   |
   +-- candidatePractice ------> prohibited practice
                                      |
                                      +-- elementSupport --> legal element
                                      |
                                      +-- sourceAnchor ----> AKN source anchor
```

Only a short Turtle preview is returned in `rdf_triples_preview`.

## Legal Ontology Export

There is one RDF/OWL ontology surface for the active checker:

```text
Reviewed Article 5 legal ontology:
  data/ontology/article5_reviewed.ttl
  /api/legal-ontology.ttl
  /api/legal-ontology.jsonld
  /api/article5/explorer
  Used by Article5Reasoner
```

The per-case RDF preview in `rdf_triples_preview` is generated from one analysis result. It is not a second legal ontology.

## Local Setup

Create and activate a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Run the app:

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

## Useful Commands

Validate tests:

```bash
PYTHONPATH=. pytest
```

Check AKN parsing:

```bash
python scripts/parse_ai_act.py
```

Run one local API request:

```bash
curl -sS http://127.0.0.1:8000/api/health
```

## Testing Coverage

The test suite covers:

- AKN parser behavior;
- source-law validation/index behavior;
- Article 5 source-anchor extraction;
- reviewed ontology loading/validation;
- fail-closed analysis when ontology/source configuration is unavailable;
- no dependency on the removed legacy JSON rule path;
- LLM-suggested candidate facts remain provenance-labelled and cannot create Article 5 matches by themselves;
- API health and analyze behavior;
- input length validation;
- broad ontology export generation.

Current expected suite size:

```text
21 tests
```

## Production Notes

The current deployment uses:

- systemd service: `ai-act-deliberation-explainer.service`;
- app bind address: `127.0.0.1:8097`;
- reverse proxy: Nginx;
- public domain: `https://ai-act.democracyroutes.com`;
- TLS: Let's Encrypt / Certbot;
- Nginx body limit: `256k`;
- Nginx API rate limit for analysis/upload routes;
- security headers including CSP, HSTS, `X-Frame-Options`, `X-Content-Type-Options`, `Referrer-Policy`, and `Permissions-Policy`;
- systemd hardening including `NoNewPrivileges`, private temp/devices, read-only system/home protection, task limits, and memory cap.

Recommended next hardening:

- run the service under a dedicated non-root user;
- keep dependency versions pinned and reviewed;
- keep app-level input limits;
- keep rate limiting;
- keep LLM refinement disabled unless privacy notices and data-sharing boundaries are acceptable;
- monitor errors and request volume.

## Known Limitations

- The app checks Article 5 prohibited-practice signals only.
- It does not perform a full AI Act classification.
- It does not decide whether a system is lawful, unlawful, compliant, or non-compliant.
- The current element checker is deterministic and intentionally simple; it is not a complete formal logic reasoner.
- The reviewed ontology contains amended Article 5 material that is integrated in this prototype and grouped separately in the explorer.
- Some source anchors may not expose every nested `eId` depending on AKN structure.
- Uploaded text is processed in memory and is not persisted by the application.
- Optional LLM candidate-fact assistance and wording refinement may send user text to the configured provider if enabled.

## Design Boundary

This project should be presented as:

- an ontology-assisted legal-design explainer;
- a traceability demonstrator;
- an Article 5 source/ontology/API prototype;
- a human-review support tool.

It should not be presented as:

- legal advice;
- a compliance certificate;
- a complete AI Act classifier;
- an autonomous legal decision-maker;
- an LLM legal oracle.

## License

This repository is licensed under the Creative Commons Attribution 4.0 International License (CC BY 4.0).

You may share and adapt the material, including for commercial purposes, provided that appropriate attribution is given, a link to the license is provided, and changes are indicated.

See `LICENSE` for the repository notice and the canonical license links.
