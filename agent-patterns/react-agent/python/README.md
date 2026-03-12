# ReAct Agent - Python Implementation

Runnable implementation of a **ReAct (Reason + Act)** agent that performs
step-by-step reasoning and interacts with external tools in a controlled loop.

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
https://agentpatterns.tech/en/agent-patterns/react-agent

## What's inside

- ReAct loop (Think -> Act -> Observe)
- Tool registry and allowlist-based tool gateway
- Tool calling interface and action validation
- Step, tool-call, and time budgeting
- Stop conditions (timeouts, invalid actions, loop detection, budget limits)
- Execution state tracking (`history` + `trace`)

## Learn the pattern (Docs)

Background concepts used by this example:

- ReAct Agent
  https://agentpatterns.tech/en/agent-patterns/react-agent
- Tool Calling
  https://agentpatterns.tech/en/foundations/tool-calling
- Stop Conditions
  https://agentpatterns.tech/en/foundations/stop-conditions

## Project layout

```text
examples/
  agent-patterns/
    react-agent/
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
