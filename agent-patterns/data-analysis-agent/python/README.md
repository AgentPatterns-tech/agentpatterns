# Data-Analysis Agent (Python)

Production-style runnable example of a data-analysis agent with:

- fixed analysis workflow (`ingest -> profile -> transform -> analyze -> validate`)
- policy check for source/region before ingest
- deterministic dedupe (`latest_by_event_ts`) instead of list-order wins
- explicit cleaning rules from `policy_hints.analysis_rules`
- quality-gate validation including aggregate consistency checks
- trace/history for auditability

## Run

```bash
python main.py
```

No external dependencies are required.

## Try

- Set `source="warehouse_refunds_daily"` in `REQUEST` to trigger `policy_block:source_denied_execution`.
