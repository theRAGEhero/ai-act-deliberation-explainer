# AI Act Deliberation Explainer

Backend-first prototype for a legal design / civic-tech hackathon. It turns a meeting note, transcript, or AI-use scenario into a preliminary AI Act discussion map: detected concepts, actors, possible risks, rights/interests, obligations to verify, missing questions, source references, traceability, JSON, and RDF/Turtle.

It does not provide legal advice, certify compliance, or decide whether a system is legal, illegal, compliant, or non-compliant.

## Run

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Visit `http://localhost:8000`.

## Legal Source

Place the EU AI Act Akoma Ntoso XML at:

```text
data/aiACT.xml
```

If the file is missing or malformed, the app still runs with seeded AI Act article references from `data/seed_concepts.json`.

## Endpoints

- `GET /` minimal HTML test UI
- `POST /api/analyze` JSON body with `text`, optional `title`, `persona`, `use_llm`
- `POST /api/upload` upload a `.txt` file
- `GET /api/articles` parsed/seeded article list
- `GET /api/articles/{number}` article detail
- `GET /api/ontology.ttl` RDF/Turtle ontology
- `GET /api/ontology.jsonld` JSON-LD ontology
- `GET /api/health` parser and ontology status

## Architecture

- `app/legal_source/akn_parser.py` parses AKN XML with namespace-aware, tolerant `lxml` logic.
- `app/legal_source/legal_db.py` keeps parsed and seeded articles searchable in memory.
- `app/analysis/rule_engine.py` performs deterministic analysis without an API key.
- `app/analysis/llm_agent.py` optionally refines output with an OpenAI-compatible API, constrained by rule output and legal snippets.
- `app/ontology/ontology_builder.py` builds a small RDF layer using `rdflib`.
- `app/main.py` exposes the FastAPI app and minimal frontend.

## RDF Use

The ontology models AI Act articles, actors, concepts, risks, rights/interests, obligations, scenarios, evidence snippets, missing questions, and Annex III areas. It is used as a semantic layer and exported as Turtle and JSON-LD.

## AKN Use

The parser extracts article number, heading, `eId`, full text, paragraphs, and Article 3 definitions when detectable. It tolerates imperfect XML and falls back to seeded references.

## Sample Input

```text
Municipality X wants to use an AI system to rank social housing applications. The model uses historical welfare data. A human officer can approve the final decision, but applicants will not see the score.
```

Expected signals include public services, ranking/scoring, deployer, affected person, bias, opacity, automation bias, contestability, Article 13, Article 14, Article 26, Article 27, Article 86, and Annex III public services relevance.

## Scripts

```bash
python scripts/parse_ai_act.py
python scripts/build_ontology.py
```

## Tests

```bash
pytest
```

## Legal Disclaimer

This is a preliminary legal-design analysis for discussion and education. It is not legal advice and does not certify AI Act compliance.

## Future Improvements

- Better AKN structural extraction for annexes and cross-references.
- Richer ontology queries for article-to-risk paths.
- Speaker-aware transcript analysis for consensus and dissent.
- Better visual graph output while keeping backend-first design.
