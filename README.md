# AgentPatterns Examples: Python AI Agent Patterns (ReAct, RAG, Routing, Tool Calling)

Production-ready and beginner-friendly **Python AI agent examples** that map directly to guides on [agentpatterns.tech](https://agentpatterns.tech).

This repository helps you build and understand **LLM agents** with real execution loops, tool calling, memory, routing, orchestration, safety constraints, and recovery strategies.

## Why this repository

- Run real AI agent code, not pseudo-code.
- Learn a practical path from first agent to advanced multi-agent systems.
- Reuse minimal production-style implementations in your own projects.
- Follow examples that stay aligned with architecture guides on `agentpatterns.tech`.

## Topics covered (SEO keywords)

- Python AI agents
- LLM agent architecture
- ReAct agent pattern
- RAG agent in Python
- Tool calling and function calling
- Multi-agent collaboration and orchestration
- Agent memory, routing, reflection, and guardrails
- AI agent reliability: fallback and recovery

## Available examples

### Start here

| Example | Local path | Article |
| --- | --- | --- |
| Write Your First Agent | `examples/start-here/write-your-first-agent/python` | [Read article](https://agentpatterns.tech/en/start-here/write-your-first-agent) |

### Foundations

| Example | Local path | Article |
| --- | --- | --- |
| Tool Calling Basics | `examples/foundations/tool-calling-basics/python` | [Read article](https://agentpatterns.tech/en/foundations/tool-calling-basics) |
| Tool Calling | `examples/foundations/tool-calling/python` | [Read article](https://agentpatterns.tech/en/foundations/tool-calling) |
| Agent Memory | `examples/foundations/agent-memory/python` | Code example |
| Allowed Actions | `examples/foundations/allowed-actions/python` | Code example |
| Planning vs Reactive | `examples/foundations/planning-vs-reactive/python` | [Read article](https://agentpatterns.tech/en/foundations/planning-vs-reactive) |
| Stop Conditions | `examples/foundations/stop-conditions/python` | Code example |
| LLM Limits in Agents | `examples/foundations/llm-limits-agents/python` | [Read article](https://agentpatterns.tech/en/foundations/llm-limits-agents) |

### Agent patterns

| Example | Local path | Article |
| --- | --- | --- |
| ReAct Agent | `examples/agent-patterns/react-agent/python` | [Read article](https://agentpatterns.tech/en/agent-patterns/react-agent) |
| Routing Agent | `examples/agent-patterns/routing-agent/python` | [Read article](https://agentpatterns.tech/en/agent-patterns/routing-agent) |
| Task Decomposition Agent | `examples/agent-patterns/task-decomposition-agent/python` | [Read article](https://agentpatterns.tech/en/agent-patterns/task-decomposition-agent) |
| RAG Agent | `examples/agent-patterns/rag-agent/python` | [Read article](https://agentpatterns.tech/en/agent-patterns/rag-agent) |
| Supervisor Agent | `examples/agent-patterns/supervisor-agent/python` | [Read article](https://agentpatterns.tech/en/agent-patterns/supervisor-agent) |
| Orchestrator Agent | `examples/agent-patterns/orchestrator-agent/python` | [Read article](https://agentpatterns.tech/en/agent-patterns/orchestrator-agent) |
| Research Agent | `examples/agent-patterns/research-agent/python` | Code example |
| Data Analysis Agent | `examples/agent-patterns/data-analysis-agent/python` | Code example |
| Reflection Agent | `examples/agent-patterns/reflection-agent/python` | [Read article](https://agentpatterns.tech/en/agent-patterns/reflection-agent) |
| Self-Critique Agent | `examples/agent-patterns/self-critique-agent/python` | [Read article](https://agentpatterns.tech/en/agent-patterns/self-critique-agent) |
| Memory-Augmented Agent | `examples/agent-patterns/memory-augmented-agent/python` | [Read article](https://agentpatterns.tech/en/agent-patterns/memory-augmented-agent) |
| Multi-Agent Collaboration | `examples/agent-patterns/multi-agent-collaboration/python` | [Read article](https://agentpatterns.tech/en/agent-patterns/multi-agent-collaboration) |
| Guarded Policy Agent | `examples/agent-patterns/guarded-policy-agent/python` | Code example |
| Fallback Recovery Agent | `examples/agent-patterns/fallback-recovery-agent/python` | Code example |
| Code Execution Agent | `examples/agent-patterns/code-execution-agent/python` | Code example |

## Quick start

### 1) Choose an example

```bash
CATEGORY=agent-patterns
EXAMPLE=react-agent
cd examples/$CATEGORY/$EXAMPLE/python
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

- **Docs** explain when and why to use each AI agent pattern.
- **This repo** provides runnable implementations of those exact patterns.
- Each example folder includes its own README and direct links to relevant concepts.

## License

MIT
