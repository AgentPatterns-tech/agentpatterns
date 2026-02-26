# AgentPatterns Examples: Runnable AI Agent Patterns in Python

Production-style and beginner-friendly **AI agent examples** that map directly to the guides on [agentpatterns.tech](https://agentpatterns.tech).

If you want to learn how to build agents with real execution loops, tool boundaries, routing, and safety checks, this repo is the fastest way to run and inspect working code.

## Why this repository

- Learn by running real code, not pseudo-code.
- Move from simple loops to advanced multi-step agent patterns.
- Reuse minimal, clean implementations in your own projects.
- Follow examples that are aligned with concrete docs and architecture explanations.

## Available examples

### Agent Patterns (Core Block)

The most important block of the site and the main architecture layer for production agents.

| Example | Focus | Local path | Article |
| --- | --- | --- | --- |
| ReAct Agent | `Think -> Act -> Observe` with budgets | `examples/react-agent/python` | https://agentpatterns.tech/en/agent-patterns/react-agent |
| Routing Agent | Delegate to best specialist route | `examples/routing-agent/python` | https://agentpatterns.tech/en/agent-patterns/routing-agent |
| Task Decomposition Agent | `Plan -> Execute -> Combine` workflow | `examples/task-decomposition-agent/python` | https://agentpatterns.tech/en/agent-patterns/task-decomposition-agent |

### Foundations

| Example | Focus | Local path | Article |
| --- | --- | --- | --- |
| Write Your First Agent | First loop (`Act -> Check -> Retry`) | `examples/write-your-first-agent/python` | https://agentpatterns.tech/en/start-here/write-your-first-agent |
| Tool Calling Basics | Basic tool execution loop | `examples/tool-calling-basics/python` | https://agentpatterns.tech/en/foundations/tool-calling-basics |
| Tool Calling | Tool + action restrictions (policy boundary) | `examples/tool-calling/python` | https://agentpatterns.tech/en/foundations/tool-calling |
| LLM Limits in Agents | Validation, citations, confidence, handoff | `examples/llm-limits-agents/python` | https://agentpatterns.tech/en/foundations/llm-limits-agents |

## Project structure

```text
examples/
  write-your-first-agent/
    python/
  tool-calling-basics/
    python/
  tool-calling/
    python/
  llm-limits-agents/
    python/
  react-agent/
    python/
  routing-agent/
    python/
  task-decomposition-agent/
    python/
```

## Quick start

### 1) Choose an example

```bash
EXAMPLE=react-agent
cd examples/$EXAMPLE/python
```

### 2) Install and run

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export OPENAI_API_KEY="sk-..."
python main.py
```

## Prerequisites

- Python 3.10+ (3.11+ recommended)
- `OPENAI_API_KEY` environment variable
- macOS/Linux shell commands above (adapt activation/export commands on Windows)

## How this maps to agentpatterns.tech

- **Docs** explain when and why to use each agent pattern.
- **This repo** shows runnable implementations of those exact patterns.
- Each example folder includes its own README with direct links to related concepts.

## License

MIT
