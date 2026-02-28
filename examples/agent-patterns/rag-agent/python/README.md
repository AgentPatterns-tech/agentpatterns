# RAG Agent - Python Implementation

Runnable implementation of a RAG agent that plans retrieval, validates retrieval
intent via policy, grounds answers in approved documents, and returns citations.

---

## Quick start

```bash
# (optional) create venv
python -m venv .venv && source .venv/bin/activate

# install dependencies
pip install -r requirements.txt

# set API key
export OPENAI_API_KEY="sk-..."

# run the agent
python main.py
```

## Full walkthrough

Read the complete implementation guide:
https://agentpatterns.tech/en/agent-patterns/rag-agent

## What's inside

- Retrieval intent planning (`kind=retrieve`)
- Policy boundary for retrieval shape and source allowlist
- Execution boundary for runtime source access
- Deterministic retriever and context packing
- Grounded answer synthesis with citation checks
- Fallback path when no grounded context is available
- Trace and history for auditability

## Project layout

```text
examples/
  agent-patterns/
    rag-agent/
      python/
        README.md
        main.py
        llm.py
        gateway.py
        retriever.py
        kb.py
        requirements.txt
```

## Notes

- Code and README are English-only by design.
- The website provides multilingual explanations and theory.

## License

MIT
