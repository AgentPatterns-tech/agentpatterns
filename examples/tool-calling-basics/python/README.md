# Tool Calling Basics - Python Implementation

Runnable implementation of basic tool calling:
the model decides when to call tools, and the system executes them safely.

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
https://agentpatterns.tech/en/foundations/tool-calling-basics

## What's inside

- Core tool-calling loop (`assistant -> tool -> assistant`)
- Tool schema definitions passed to the model
- Executor boundary with allowlist checks
- Deterministic tools for profile and balance lookups
- Step budget to stop infinite loops

## Learn the pattern (Docs)

Background concepts used by this example:

- Tool Calling Basics
  https://agentpatterns.tech/en/foundations/tool-calling-basics
- Tool Calling
  https://agentpatterns.tech/en/foundations/tool-calling
- LLM Limits in Agents
  https://agentpatterns.tech/en/foundations/llm-limits-agents

## Project layout

```text
examples/
  tool-calling-basics/
    python/
      README.md
      main.py
      llm.py
      executor.py
      tools.py
      requirements.txt
```

## Notes

- Code and README are English-only by design.
- The website provides multilingual explanations and theory.

## License

MIT
