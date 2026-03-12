# Tool Calling - Python Implementation

Runnable implementation of an agent that uses tool calls through a gateway
with explicit policy restrictions.

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
https://agentpatterns.tech/en/foundations/tool-calling

## What's inside

- Tool-calling loop with LLM decisions and tool execution feedback
- Tool registry with explicit allowlist (`ALLOWED_TOOLS`)
- Action-level restrictions inside a tool (`ALLOWED_ACTIONS`)
- Safe handling of blocked tools/actions and bad arguments
- Step budget to prevent unbounded loops

## Learn the pattern (Docs)

Background concepts used by this example:

- Tool Calling
  https://agentpatterns.tech/en/foundations/tool-calling
- Tool Calling Basics
  https://agentpatterns.tech/en/foundations/tool-calling-basics
- Stop Conditions
  https://agentpatterns.tech/en/foundations/stop-conditions

## Project layout

```text
examples/
  foundations/
    tool-calling/
      python/
        README.md
        main.py
        llm.py
        gateway.py
        tools.py
        requirements.txt
```

## Notes

- Code and README are English-only by design.
- The website provides multilingual explanations and theory.

## License

MIT
