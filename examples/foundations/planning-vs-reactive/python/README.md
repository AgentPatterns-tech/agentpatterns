# Planning vs Reactive - Python Implementation

Runnable learning example that compares two agent strategies on the same task:
planning-first execution vs reactive step-by-step decisions.

---

## Quick start

```bash
# (optional) create venv
python -m venv .venv && source .venv/bin/activate

# install dependencies (none required, command kept for consistency)
pip install -r requirements.txt

# run the comparison
python main.py
```

## Full walkthrough

Read the concept article:
https://agentpatterns.tech/en/foundations/planning-vs-reactive

## What's inside

- Deterministic flaky tools (orders fails once, then succeeds)
- Planning agent with explicit `create_plan -> execute -> replan`
- Reactive agent that chooses the next action from current state
- Side-by-side trace output for easy comparison

## Project layout

```text
examples/
  foundations/
    planning-vs-reactive/
      python/
        README.md
        main.py
        llm.py
        planning_agent.py
        reactive_agent.py
        tools.py
        requirements.txt
```

## Notes

- This code is intentionally simple for learning.
- The website provides multilingual explanation and context.

## License

MIT
