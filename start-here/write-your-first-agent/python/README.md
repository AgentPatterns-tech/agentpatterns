# Write Your First Agent - Python Implementation

Runnable beginner example of a simple agent loop:
generate -> validate -> retry until success or step limit.

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
https://agentpatterns.tech/en/start-here/write-your-first-agent

## What's inside

- Agent loop with a fixed step budget (`MAX_STEPS`)
- LLM call isolated in `llm.py`
- Output validation in `evaluator.py` (`parse_int`, goal check)
- Explicit stop on success or max steps reached

## Learn the pattern (Docs)

Background concepts used by this example:

- Build Your First Agent
  https://agentpatterns.tech/en/start-here/write-your-first-agent
- Workflow vs Agent
  https://agentpatterns.tech/en/start-here/workflow-vs-agent
- When Agent Needs Boundaries
  https://agentpatterns.tech/en/start-here/when-agent-needs-boundaries

## Project layout

```text
examples/
  start-here/
    write-your-first-agent/
      python/
        README.md
        main.py
        llm.py
        evaluator.py
        requirements.txt
```

## Notes

- Code and README are English-only by design.
- The website provides multilingual explanations and theory.

## License

MIT
