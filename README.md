# AgentPatterns Examples

Runnable code examples that accompany articles on [agentpatterns.tech](https://www.agentpatterns.tech).

This repository is a practical companion to the main project: each article can include a small, focused example you can run locally and adapt for your own use cases.

## What lives here

- `examples/` contains article-aligned examples.
- Each example is grouped by topic, then by language/runtime.
- Examples are intentionally minimal: clear logic, fast setup, easy to remix.

## Current structure

```text
examples/
  write-your-first-agent/
    python/
```

## Quick start (Python example)

```bash
cd examples/write-your-first-agent/python
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export OPENAI_API_KEY="sk-..."
python main.py
```

## Relation to agentpatterns.tech

- Articles explain concepts and patterns.
- This repo provides runnable implementations for those materials.
- As new articles are published, matching examples are added here.
