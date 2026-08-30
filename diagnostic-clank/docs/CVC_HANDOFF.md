# Diagnostic → CVC handoff

Diagnostic owns the question **“what failed and why?”** CVC owns the separate
question **“what does this teach the fleet?”** Diagnostic can create a bounded
evidence package, but creating it never opens CVC, ingests evidence, changes a
support grade, or creates a review/ratification decision.

An operator-authored JSON description can be packaged explicitly:

```text
diagnostic-clank handoff create \
  --file operator-evidence.json \
  --output cvc-handoff.json \
  --source-revision <diagnostic-revision>
```

The output follows CVC's `diagnostic-to-cvc-handoff.v0.1` schema and includes a
hash of the source description. The operator may then inspect it and, in a
separate deliberate action, run `cvc ingest cvc-handoff.json` followed by any
needed trigger check or review. Diagnostic does not automate that step.

The package accepts positive evidence as well as incidents: successful restore
or migration, restart survivability, bounded replay, durable delivery, and
independent implementation evidence can use an explicit success verdict and
`NOT_APPLICABLE` failed-gate/root-cause values where appropriate.
