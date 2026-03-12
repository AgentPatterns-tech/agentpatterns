# Routing Agent - Python Implementation

Runnable implementation of a routing agent that selects the right specialist,
delegates the task, and then composes a final user answer.

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
https://agentpatterns.tech/en/agent-patterns/routing-agent

## What's inside

- Route decision step (`kind=route`) with strict schema validation
- Separate policy and execution allowlists for route targets
- Delegation gateway with loop detection and delegation budget
- Reroute flow when specialist returns `needs_reroute`
- Final synthesis step after successful routing
- Execution trace and stop reasons for debugging

## Learn the pattern (Docs)

Background concepts used by this example:

- Routing Agent
  https://agentpatterns.tech/en/agent-patterns/routing-agent
- Orchestrator Agent
  https://agentpatterns.tech/en/agent-patterns/orchestrator-agent
- Supervisor Agent
  https://agentpatterns.tech/en/agent-patterns/supervisor-agent
- Multi-Agent Collaboration
  https://agentpatterns.tech/en/agent-patterns/multi-agent-collaboration

## Project layout

```text
examples/
  agent-patterns/
    routing-agent/
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
