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
You are an AI support agent. When you need data, call the available tools.
Once you have enough information, give a short answer.
""".strip()

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_user_profile",
            "description": "Returns user profile by user_id",
            "parameters": {
                "type": "object",
                "properties": {"user_id": {"type": "integer"}},
                "required": ["user_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_user_balance",
            "description": "Returns user balance by user_id",
            "parameters": {
                "type": "object",
                "properties": {"user_id": {"type": "integer"}},
                "required": ["user_id"],
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
