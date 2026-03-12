import json

from executor import execute_tool_call
from llm import ask_model

MAX_STEPS = 6

TASK = "Prepare a short account summary for user_id=42: name, tier, and balance."


def to_assistant_message(message) -> dict:
    tool_calls = []
    for tc in message.tool_calls or []:
        tool_calls.append(
            {
                "id": tc.id,
                "type": "function",
                "function": {
                    "name": tc.function.name,
                    "arguments": tc.function.arguments,
                },
            }
        )
    return {
        "role": "assistant",
        "content": message.content or "",
        "tool_calls": tool_calls,
    }


def run():
    messages: list[dict] = [{"role": "user", "content": TASK}]

    for step in range(1, MAX_STEPS + 1):
        print(f"\n=== STEP {step} ===")
        assistant = ask_model(messages)
        messages.append(to_assistant_message(assistant))

        text = assistant.content or ""
        if text.strip():
            print(f"Assistant: {text.strip()}")

        tool_calls = assistant.tool_calls or []
        if not tool_calls:
            print("\nDone: model finished without a new tool call.")
            return

        for tc in tool_calls:
            print(f"Tool call: {tc.function.name}({tc.function.arguments})")
            execution = execute_tool_call(
                tool_name=tc.function.name,
                arguments_json=tc.function.arguments,
            )
            print(f"Tool result: {execution}")

            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": json.dumps(execution, ensure_ascii=False),
                }
            )

    print("\nStop: MAX_STEPS reached.")


if __name__ == "__main__":
    run()
