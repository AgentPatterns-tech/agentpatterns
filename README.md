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

| Example | Local path | Article |
| --- | --- | --- |
| <strong><big>ReAct Agent</big></strong> | `examples/react-agent/python` | [Read article](https://agentpatterns.tech/en/agent-patterns/react-agent) |
| <strong><big>Routing Agent</big></strong> | `examples/routing-agent/python` | [Read article](https://agentpatterns.tech/en/agent-patterns/routing-agent) |
| <strong><big>Task Decomposition Agent</big></strong> | `examples/task-decomposition-agent/python` | [Read article](https://agentpatterns.tech/en/agent-patterns/task-decomposition-agent) |

### Foundations

| Example | Local path | Article |
| --- | --- | --- |
| **Write Your First Agent** | `examples/write-your-first-agent/python` | [Read article](https://agentpatterns.tech/en/start-here/write-your-first-agent) |
| **Tool Calling Basics** | `examples/tool-calling-basics/python` | [Read article](https://agentpatterns.tech/en/foundations/tool-calling-basics) |
| **Tool Calling** | `examples/tool-calling/python` | [Read article](https://agentpatterns.tech/en/foundations/tool-calling) |
| **LLM Limits in Agents** | `examples/llm-limits-agents/python` | [Read article](https://agentpatterns.tech/en/foundations/llm-limits-agents) |

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
