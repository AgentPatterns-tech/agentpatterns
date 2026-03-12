# AgentPatterns Examples: Python AI Agent Patterns (ReAct, RAG, Routing, Tool Calling)

Production-ready and beginner-friendly **Python AI agent examples** that map directly to guides on [agentpatterns.tech](https://agentpatterns.tech).

Build and understand **LLM agents** with real execution loops: tool calling, memory, routing, orchestration, guardrails, and recovery.

## Topics Covered

- Python AI agents
- LLM agent architecture
- ReAct, RAG, and routing agent patterns
- Tool calling and function calling
- Multi-agent orchestration and collaboration
- Guardrails, fallback, and recovery

## Main Agent Patterns

> **Core section of this repo.** If you are here for practical reusable architectures, start with these patterns.

| Pattern | What you learn | Local path | Article |
| --- | --- | --- | --- |
| ReAct Agent | Thought-action-observation loops | `agent-patterns/react-agent/python` | [Read article](https://agentpatterns.tech/en/agent-patterns/react-agent) |
| Routing Agent | Intent-based task dispatch | `agent-patterns/routing-agent/python` | [Read article](https://agentpatterns.tech/en/agent-patterns/routing-agent) |
| Task Decomposition Agent | Break work into executable sub-tasks | `agent-patterns/task-decomposition-agent/python` | [Read article](https://agentpatterns.tech/en/agent-patterns/task-decomposition-agent) |
| RAG Agent | Retrieval-augmented reasoning | `agent-patterns/rag-agent/python` | [Read article](https://agentpatterns.tech/en/agent-patterns/rag-agent) |
| Supervisor Agent | Controller-worker delegation | `agent-patterns/supervisor-agent/python` | [Read article](https://agentpatterns.tech/en/agent-patterns/supervisor-agent) |
| Orchestrator Agent | Multi-worker execution orchestration | `agent-patterns/orchestrator-agent/python` | [Read article](https://agentpatterns.tech/en/agent-patterns/orchestrator-agent) |
| Research Agent | Structured web-style investigation flow | `agent-patterns/research-agent/python` | [Read article](https://agentpatterns.tech/en/agent-patterns/research-agent) |
| Data Analysis Agent | Analysis workflows with tool constraints | `agent-patterns/data-analysis-agent/python` | [Read article](https://agentpatterns.tech/en/agent-patterns/data-analysis-agent) |
| Reflection Agent | Self-review and iterative improvement | `agent-patterns/reflection-agent/python` | [Read article](https://agentpatterns.tech/en/agent-patterns/reflection-agent) |
| Self-Critique Agent | Audit and revise model output | `agent-patterns/self-critique-agent/python` | [Read article](https://agentpatterns.tech/en/agent-patterns/self-critique-agent) |
| Memory-Augmented Agent | Short-term and durable memory usage | `agent-patterns/memory-augmented-agent/python` | [Read article](https://agentpatterns.tech/en/agent-patterns/memory-augmented-agent) |
| Multi-Agent Collaboration | Role-based agent teamwork | `agent-patterns/multi-agent-collaboration/python` | [Read article](https://agentpatterns.tech/en/agent-patterns/multi-agent-collaboration) |
| Guarded Policy Agent | Policy checks and safe action gating | `agent-patterns/guarded-policy-agent/python` | [Read article](https://agentpatterns.tech/en/agent-patterns/guarded-policy-agent) |
| Fallback Recovery Agent | Checkpoints, retries, and fallback logic | `agent-patterns/fallback-recovery-agent/python` | [Read article](https://agentpatterns.tech/en/agent-patterns/fallback-recovery-agent) |
| Code Execution Agent | Controlled code execution loops | `agent-patterns/code-execution-agent/python` | [Read article](https://agentpatterns.tech/en/agent-patterns/code-execution-agent) |

## Quick Start

1. Choose an example.
2. Install dependencies.
3. Run the agent.

```bash
CATEGORY=agent-patterns
EXAMPLE=react-agent
cd $CATEGORY/$EXAMPLE/python

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export OPENAI_API_KEY="sk-..."
python main.py
```

## Learning Path

- `start-here` for your first runnable agent.
- `foundations` for core building blocks.
- `agent-patterns` for production-style architectures.

## Start Here

| Example | Local path | Article |
| --- | --- | --- |
| Write Your First Agent | `start-here/write-your-first-agent/python` | [Read article](https://agentpatterns.tech/en/start-here/write-your-first-agent) |

## Foundations

| Example | Local path | Article |
| --- | --- | --- |
| Tool Calling Basics | `foundations/tool-calling-basics/python` | [Read article](https://agentpatterns.tech/en/foundations/tool-calling-basics) |
| Tool Calling | `foundations/tool-calling/python` | [Read article](https://agentpatterns.tech/en/foundations/tool-calling) |
| Agent Memory | `foundations/agent-memory/python` | [Read article](https://agentpatterns.tech/en/foundations/agent-memory) |
| Allowed Actions | `foundations/allowed-actions/python` | [Read article](https://agentpatterns.tech/en/foundations/allowed-actions) |
| Planning vs Reactive | `foundations/planning-vs-reactive/python` | [Read article](https://agentpatterns.tech/en/foundations/planning-vs-reactive) |
| Stop Conditions | `foundations/stop-conditions/python` | [Read article](https://agentpatterns.tech/en/foundations/stop-conditions) |
| LLM Limits in Agents | `foundations/llm-limits-agents/python` | [Read article](https://agentpatterns.tech/en/foundations/llm-limits-agents) |

## Extra Example

| Example | Local path | Article |
| --- | --- | --- |
| Support Agent | `examples/support-agent/python` | Code example |

## Why This Repository

- Real runnable AI agent code, not pseudo-code.
- Clear path from beginner examples to advanced patterns.
- Minimal production-style implementations you can reuse.
- Direct mapping to the architecture guides on `agentpatterns.tech`.

## Prerequisites

- Python 3.10+ (3.11+ recommended)
- `OPENAI_API_KEY` environment variable
- macOS/Linux shell commands above (adapt for Windows if needed)

## License

MIT
