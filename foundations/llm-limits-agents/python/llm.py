import os
from openai import OpenAI

api_key = os.environ.get("OPENAI_API_KEY")

if not api_key:
    raise EnvironmentError(
        "OPENAI_API_KEY is not set.\n"
        "Run: export OPENAI_API_KEY='sk-...'"
    )

client = OpenAI(api_key=api_key)

SYSTEM_PROMPT = """
You are a support agent.
Reply with VALID JSON only in this format:
{
  "answer": "short answer",
  "citations": ["KB-101"],
  "confidence": 0.0,
  "needs_human": false
}
Use only sources that exist in the provided context.
If data is insufficient, set needs_human=true.
""".strip()


def ask_model(question: str, context: str, feedback: str | None = None) -> str:
    user_prompt = (
        f"Customer question:\n{question}\n\n"
        f"Context:\n{context}\n\n"
        "Return JSON only."
    )

    if feedback:
        user_prompt += f"\n\nFix your previous response using this error feedback: {feedback}"

    completion = client.chat.completions.create(
        model="gpt-4.1-mini",
        temperature=0,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
    )

    content = completion.choices[0].message.content
    return (content or "").strip()
