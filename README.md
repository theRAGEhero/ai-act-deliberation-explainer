# AI Act Prohibitions Checker

AI Act Prohibitions Checker is a FastAPI application that turns a short AI-use scenario, meeting note, or transcript into a preliminary legal-design map under the EU AI Act.

A traceable, ontology-assisted approach to evaluate whether an AI system is prohibited under the AI Act.

The app is designed to support discussion, teaching, workshops, and early issue spotting. It connects four layers:

- citizen-readable explanations
- deterministic legal-design signals
- AI Act source references
- machine-readable ontology output

It does not provide legal advice, certify compliance, or decide whether an AI system is legal, illegal, compliant, or non-compliant.

## What The App Does

Given a text input, the app:

1. Normalizes the text and splits it into claims.
2. Detects AI-system signals, actors, contexts, AI functions, and Article 5 prohibition keywords.
3. Compares the text against explicit Article 5 prohibited-practice mappings.
4. Copies targets, contexts, trigger conditions, exceptions, safeguards, and affected rights only from the matched mapping.
5. Builds a traceability table from input snippets to the matched Article 5 point.
6. Produces a citizen-facing explanation.
7. Exposes the result as JSON.
8. Exposes a small RDF ontology as Turtle and JSON-LD.
9. Shows visual maps in the browser, including network, trace-flow, actor, risk, source, obligation, lifecycle, and question views.

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

- the app detects AI-system context and functions
- the app does not create a high-risk or general-obligations map
- the app reports no grounded Article 5 prohibited-practice match unless the text also contains Article 5 facts

Example Article 5 input:

```text
A public authority uses an AI system for social scoring based on social
behaviour and personality characteristics. The score can cause detrimental
treatment in access to services.
```

Expected discussion signals include:

- Article 5(1)(c) social scoring leading to detrimental treatment
- targets, contexts, trigger conditions, and affected rights copied from `data/seed_prohibitions.json`
- Article 5 as the selected AI Act source
- traceability from the input text to the matched Article 5 point

All signals still require human legal review.

## Main Features

### Browser Interface

`GET /` serves the HTML interface in `app/templates/index.html`.

The page lets a user:

- paste a scenario or transcript
- upload a `.txt` file
- optionally request LLM refinement if configured
- view detected actors, contexts, functions, risks, rights/interests, obligations, missing questions, sources, traceability, visual maps, and raw JSON

### Deterministic Rule Engine

`app/analysis/rule_engine.py` contains the core deterministic analysis. It is currently scoped to Article 5 prohibited AI practices.

It uses keyword and concept mappings to detect:

- actors: provider, deployer, human operator, affected person
- contexts: employment, education, public services, healthcare, law enforcement, migration, justice, democratic processes, chatbot/content AI
- AI functions: scoring, ranking, filtering, recommendation, automated decision, biometric identification, prediction, content generation, chatbot interaction
- Article 5 prohibited-practice matches from `data/seed_prohibitions.json`
- rights/interests only when they are explicitly defined by the matched Article 5 rule
- limited verification tasks and missing questions for Article 5 review

This engine works without an API key.

If the submitted text does not contain enough evidence of an AI system, automated system, AI function, context, or risk, the app returns a no-sufficient-signal result instead of inventing a legal map.

If the submitted text describes an AI system but does not match an Article 5 prohibited-practice rule, the app returns Article 5 as the review boundary and says that no grounded Article 5 match was detected. It does not fan out into high-risk obligations or other AI Act articles.

### Legal Source Layer

`app/legal_source/akn_parser.py` parses the EU AI Act Akoma Ntoso XML file from:

```text
data/aiACT.xml
```

The parser extracts:

- article number
- heading
- `eId`
- full article text
- paragraph text
- Article 3 definitions where detectable

`app/legal_source/legal_db.py` keeps the parsed articles in memory. If the XML is missing or malformed, the app falls back to seeded article references.

### Article 5 Prohibition Mapping

`data/seed_prohibitions.json` is the controlling deterministic mapping for prohibited practices. Each entry defines:

- `id`
- `label`
- `article_point`
- `keywords`
- `minimum_matches`
- `targets`
- `contexts`
- `trigger_conditions`
- `exceptions`
- `affected_rights`
- `safeguards`

The rule engine must not infer additional affected rights, trigger conditions, safeguards, targets, contexts, or exceptions. When a rule matches, the app includes all fields defined by that rule. When no rule matches, these fields remain empty.

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

The deterministic Article 5 mapping is represented separately in `data/seed_prohibitions.json`. The current workflow is:

```text
input text -> deterministic Article 5 rule mapping -> structured JSON response
           -> source/traceability view -> RDF ontology export for project concepts
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

The OpenRouter prompt is also scoped to Article 5. It is instructed not to invent prohibited-practice matches and not to add rights, trigger conditions, safeguards, contexts, targets, or exceptions beyond the matched mapping.

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
    rule_engine.py              Deterministic AI Act signal detection
    report_builder.py           Final response, markdown, graph data
    llm_agent.py                Optional OpenRouter refinement
    prompt_templates.py         LLM prompts
  legal_source/
    akn_parser.py               Akoma Ntoso XML parser
    legal_db.py                 In-memory legal article store
    article_selector.py         Legacy concept-to-article mapping, not used by the Article 5 rule engine
  ontology/
    ontology_builder.py         RDF graph construction
    ontology_store.py           Ontology access and serialization
    export.py                   File export helper
  static/style.css              Browser UI styles
  templates/index.html          Browser UI and client-side visual maps

data/
  aiACT.xml                     EU AI Act AKN XML source
  seed_concepts.json            Seed actors, concepts, risks, rights, obligations
  seed_annexes.json             Seed Annex III areas and questions
  seed_prohibitions.json        Article 5 prohibited-practice mappings
  sample_transcripts/           Example text inputs

generated/
  ontology.ttl                  Generated Turtle ontology
  ontology.jsonld               Generated JSON-LD ontology

scripts/
  parse_ai_act.py               Parser check script
  build_ontology.py             Rebuild generated ontology files

tests/
  test_akn_parser.py
  test_api.py
  test_ontology_builder.py
  test_rule_engine.py
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
AI_ACT_AKN_PATH=data/aiACT.xml
```

If `OPENROUTER_API_KEY` is empty, OpenRouter refinement is unavailable and the app runs with deterministic rules only.

## Legal Source Data

The preferred legal source is the AI Act Akoma Ntoso XML file:

```text
data/aiACT.xml
```

The app also has root-level `aiACT.xml`; the runtime default points to `data/aiACT.xml`.

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
