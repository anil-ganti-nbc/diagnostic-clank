# Local report emitter

Agents should not hard-code inbox paths.

```bash
diagnostic-clank paths                    # show resolved locations
diagnostic-clank report submit --file report.md \
  --agent grok --project diagnostic-clank --task my-task --append-record
diagnostic-clank scan-inbox
```

Env overrides:
- `DIAGNOSTIC_DATA_DIR` / `DIAGNOSTIC_CLANK_HOME`
- `CLANKOPS_REPORT_ROOT`

Filename convention (advisory): `YYYYMMDD-HHMMSS_<agent>_<project>_<task-slug>.md`
