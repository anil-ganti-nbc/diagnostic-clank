# Implementation requirements (for Claude/Codex — do not implement here)

1. Immutable raw evidence store with content hash + dedupe by hash  
2. Claim history with supersession/dispute (no overwrite-delete)  
3. Contradiction records as first-class (not corruption)  
4. Incident lifecycle states including AUTOMATED_VERIFIED ≠ owner accepted  
5. Distinct fields: fix, lesson, clankops_consequence  
6. Multi-evidence ↔ multi-incident links  
7. Search by clank_id, classification, status, free text with provenance  
8. Agent output ingestion preserving agent family + raw text  
9. UNKNOWN root cause representable and queryable  
10. Quarantine path for corrupt input without damaging canonical state  

# Architectural decisions required (owner/ChatGPT)

1. Canonical Diagnostic Clank GitHub repo URL / default branch after Claude v0.1  
2. Whether fleet-wide incidents use clank_id `fleet-wide` or a dedicated project id  
3. Minimum evidence set to mark RESOLVED for native-client failures  
4. Whether DiagnosticBench lives in Diagnostic repo (`diagnosticbench/`) or ProjectClankOps staging only until first merge  
5. Authority on conflicting owner vs automated test for non-UI claims  
