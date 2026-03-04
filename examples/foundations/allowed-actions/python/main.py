import json

from gateway import execute_action

MODEL_CALLS = [
    {"action": "read_user", "parameters": {"user_id": 42}},
    {"action": "send_webhook", "parameters": {"event": "user-reviewed"}},
    {"action": "update_user_status", "parameters": {"user_id": 42, "status": "paused"}},
    {"action": "delete_user", "parameters": {"user_id": 42}},
]


def compact_result(execution: dict) -> str:
    base = (
        '{'
        f'"ok": {str(bool(execution.get("ok"))).lower()}, '
        f'"action": {json.dumps(execution.get("action"), ensure_ascii=False)}, '
        '"history": [{...}]'
    )

    if execution.get("ok"):
        return (
            base
            + ', '
            + '"result": '
            + json.dumps(execution.get("result"), ensure_ascii=False)
            + '}'
        )

    return (
        base
        + ', '
        + '"error": '
        + json.dumps(execution.get("error"), ensure_ascii=False)
        + '}'
    )


def run() -> None:
    history: list[dict] = []

    for step, call in enumerate(MODEL_CALLS, start=1):
        print(f"\n=== STEP {step} ===")
        print("Model call:", json.dumps(call, ensure_ascii=False))

        execution = execute_action(call, history)
        print("Gateway result:", compact_result(execution))

    print("\nDone: policy boundary demonstrated.")


if __name__ == "__main__":
    run()
