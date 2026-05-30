# Backend Refactor Plan

## Previous Active Path

The MVP previously used a deterministic Python `RuleEngine` that loaded Article 5 practice mappings from `data/seed_prohibitions.json`. That path was useful for a quick demo, but it made JSON seed data look like a legal source of truth.

That legacy engine may remain temporarily in the codebase for historical comparison, but it is removed from the active `/api/analyze` and `/api/upload` analysis path.

## Ontology-First Path

The active backend path is now designed as:

```text
Akoma Ntoso AI Act XML
  -> XSD validation
  -> source anchor index for Article 3 and Article 5
  -> reviewed Article 5 RDF ontology
  -> legal element checker
  -> structured JSON API output
```

There is no runtime switch back to the legacy legal-reasoning path.

## Hackathon Legal Sources

The repository contains hackathon-provided Akoma Ntoso files:

- `reference/akoma-ntoso/aiAct-2024-1689.xml`
- `reference/akoma-ntoso/akomantoso30.xml`
- `reference/akoma-ntoso/akomantoso30.xsd`
- `reference/akoma-ntoso/xml.xsd`

The XML is the source-law layer. The XSD files are used to validate that source-law layer before legal analysis runs.

## No Silent Legal Fallback

If the source XML, schema validation, source index, or reviewed legal ontology is missing or invalid, analysis fails closed.

Expected fail-closed cases return HTTP 200 with an `AnalysisResponse` whose `case_summary` is `Legal analysis unavailable` and whose `raw_rule_output.status` is `analysis_unavailable`.

The app must not silently fall back to `seed_prohibitions.json`, keyword rules, or generated JSON mappings.

## JSON Is Output

JSON is an API/frontend transport format. It is not the legal source of truth.

The source-law layer is the validated Akoma Ntoso XML. The future legal model is the reviewed RDF ontology.

## Reviewed RDF Ontology

The reviewed Article 5 RDF ontology is now present at `data/ontology/article5_reviewed.ttl`.

The backend expects legal ontology Turtle files in `data/ontology/` by default. The `LegalOntologyStore` validates the supported vocabulary and exposes original and amended Article 5 material from the reviewed ontology.

## Test Fixture Ontology

`tests/fixtures/ontology/minimal_article5.ttl` is a test fixture only. It is not the legal model and must not be used as production legal content.

## Future Legal Material

If future proposed amendments, guidance, or non-binding interpretation layers are added later, they must be marked separately from the reviewed Article 5 ontology used by the active checker.
