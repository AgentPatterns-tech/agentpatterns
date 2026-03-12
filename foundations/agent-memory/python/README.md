# Agent Memory - Python Implementation

Runnable learning example that highlights short-term vs long-term memory in agents.

---

## Quick start

```bash
# (optional) create venv
python -m venv .venv && source .venv/bin/activate

# install dependencies (none required, command kept for consistency)
pip install -r requirements.txt

# run the demo
python main.py
```

## What it demonstrates

- Short-term memory can lose early instructions when context is small
- Long-term memory persists user preferences across tasks
- Same report request can produce different output depending on memory strategy

## Project layout

```text
examples/
  foundations/
    agent-memory/
      python/
        README.md
        main.py
        agent.py
        memory.py
        tools.py
        requirements.txt
```

## Notes

- This code is intentionally simple for learning.
- The website contains multilingual explanation and context.

## License

MIT
