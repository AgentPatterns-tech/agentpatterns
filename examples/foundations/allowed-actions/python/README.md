# Allowed Actions - Python Implementation

Runnable learning example that shows policy boundaries using action levels.

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

- Action levels: read / write / execute / delete
- Least-privilege policy for an agent
- Gateway checks before every tool call
- Safe blocking of disallowed actions

## Project layout

```text
examples/
  foundations/
    allowed-actions/
      python/
        README.md
        main.py
        gateway.py
        tools.py
        requirements.txt
```

## Notes

- This code is intentionally simple for learning.
- The website contains multilingual explanation and context.

## License

MIT
