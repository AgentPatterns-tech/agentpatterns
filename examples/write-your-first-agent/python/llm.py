import os
from openai import OpenAI

api_key = os.environ.get("OPENAI_API_KEY")

if not api_key:
    raise EnvironmentError(
        "OPENAI_API_KEY is not set.\n"
        "Run: export OPENAI_API_KEY='sk-...'"
    )

client = OpenAI(api_key=api_key)

PROMPT = "Write ONLY a random number between 1 and 20. No text, no explanation."

def generate_number() -> str:
    resp = client.responses.create(
        model="gpt-4.1-mini",
        input=PROMPT,
    )
    return resp.output_text.strip()
