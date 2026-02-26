# LLM Limits in Agents - Python Implementation

Runnable implementation that shows practical guardrails for common LLM limits:
retrieval scope, output validation, confidence checks, and human handoff.

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
https://agentpatterns.tech/en/foundations/llm-limits-agents

## What's inside

- Knowledge retrieval with explicit snippet limit
- Context builder with character budget
- Strict JSON output contract (`answer`, `citations`, `confidence`, `needs_human`)
- Citation allowlist validation against retrieved sources
- Retry loop with validator feedback
- Confidence threshold and escalation to human

## Learn the pattern (Docs)

Background concepts used by this example:

- LLM Limits in Agents
  https://agentpatterns.tech/en/foundations/llm-limits-agents
- Stop Conditions
  https://agentpatterns.tech/en/foundations/stop-conditions
- Tool Calling Basics
  https://agentpatterns.tech/en/foundations/tool-calling-basics

## Project layout

```text
examples/
  foundations/
    llm-limits-agents/
      python/
        README.md
        main.py
        llm.py
        knowledge.py
        validator.py
        requirements.txt
```

## Notes

- Code and README are English-only by design.
- The website provides multilingual explanations and theory.

## License

MIT
