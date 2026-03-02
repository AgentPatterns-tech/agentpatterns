# Fallback-Recovery Agent (Python)

Production-style example for the Fallback-Recovery pattern:

- detect and classify tool failures
- retry retriable failures within budget
- switch to fallback tools when primary path is unstable
- keep progress via checkpointed step results
- finish with explicit `stop_reason`, `trace`, and `history`

## Run

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

export OPENAI_API_KEY="sk-..."
# optional:
# export OPENAI_MODEL="gpt-4.1-mini"
# export OPENAI_TIMEOUT_SECONDS="60"

python main.py
```

## Files

- `main.py` - run flow and final output
- `gateway.py` - recovery policy, retries, fallbacks, budgets
- `tools.py` - deterministic primary/fallback tool stubs
- `checkpoint_store.py` - in-memory step checkpointing
- `llm.py` - final brief synthesis
- `context.py` - request and policy hints

