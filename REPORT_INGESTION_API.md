# Report Ingestion API v1

Diagnostic Clank accepts large diagnostic reports as durable evidence. The
pipeline stores the raw bytes by SHA-256 before deterministic processing:

`RAW_STORED → CHUNKED → EXTRACTED → INDEXED → COMPLETE`

Raw reports are immutable. Chunks, claims, candidate findings, and lessons are
derived records with a processing revision; reprocessing creates a later
revision and does not replace earlier extraction. Exact duplicate uploads are
deduplicated by SHA-256.

## Endpoints

- `POST /api/v1/reports` or `/api/v1/reports/upload` — raw text body, or JSON
  `{ "raw_text": "..." }`. Optional headers include `X-Source-Agent`,
  `X-Primary-Clank`, `X-Filename`, and `X-Operator-Note`.
- `GET /api/v1/reports`
- `GET /api/v1/reports/{report_id}`
- `GET /api/v1/reports/{report_id}/status|chunks|claims|incidents|lessons`

The deterministic processor recognizes Markdown Historical L Register sections,
stable incident IDs, URLs, Git-like SHAs, status labels, lessons, and selected
failure classes. Extracted claims default to `REPORTED`; findings default to
`AUTO_EXTRACTED` and `CANDIDATE` semantics. No canonical incidents, gold cases,
or regression fixtures are created automatically.

The raw report is retained under the Diagnostic state evidence directory and
metadata/chunks are stored in the existing SQLite knowledge store. Domain truth,
promotion, and review remain explicit later workflows.
