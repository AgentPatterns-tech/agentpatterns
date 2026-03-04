# Code-Execution Agent (Python)

Production-style runnable example of a code-execution agent with:

- plan/generate code step
- policy checks before execution
- sandboxed process execution with timeout/output limits
- output schema validation
- trace/history for audit

Notes:

- Policy checks here include heuristic guards (for example, suspicious attribute names and URL literals).
- This example uses a separate subprocess boundary; it is not a full security sandbox.

## Run

```bash
python main.py
```

No external dependencies are required.
