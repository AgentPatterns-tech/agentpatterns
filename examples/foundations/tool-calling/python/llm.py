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
Use tools when data is missing.
If a tool or action is blocked, do not argue; suggest a safe manual next step.
Reply briefly in English.
""".strip()

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "customer_db",
            "description": "Customer data operations: read or update tier",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "enum": ["read", "update_tier"]},
                    "customer_id": {"type": "integer"},
                    "new_tier": {"type": "string"},
                },
                "required": ["action", "customer_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "email_service",
            "description": "Sends an email to the customer",
            "parameters": {
                "type": "object",
                "properties": {
                    "to": {"type": "string"},
                    "subject": {"type": "string"},
                    "body": {"type": "string"},
                },
                "required": ["to", "subject", "body"],
            },
        },
    },
]


def ask_model(messages: list[dict]):
    completion = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[{"role": "system", "content": SYSTEM_PROMPT}, *messages],
        tools=TOOLS,
        tool_choice="auto",
    )
    return completion.choices[0].message
