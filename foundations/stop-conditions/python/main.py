import json

from agent import StopPolicy, run_agent

TASK = "Build weekly orders summary"
POLICY = StopPolicy(max_steps=6, max_errors=2, max_no_progress=3)
STEP_LIMIT_POLICY = StopPolicy(max_steps=1, max_errors=2, max_no_progress=3)


def compact_result(result: dict) -> str:
    return (
        "{"
        f"\"done\": {str(bool(result.get('done'))).lower()}, "
        f"\"stop_reason\": {json.dumps(result.get('stop_reason'), ensure_ascii=False)}, "
        f"\"steps\": {int(result.get('steps', 0))}, "
        f"\"errors\": {int(result.get('errors', 0))}, "
        f"\"no_progress\": {int(result.get('no_progress', 0))}, "
        f"\"summary\": {json.dumps(result.get('summary'), ensure_ascii=False)}, "
        "\"history\": [{...}]"
        "}"
    )


def print_policy(policy: StopPolicy) -> None:
    print(
        "Policy:",
        json.dumps(
            {
                "max_steps": policy.max_steps,
                "max_errors": policy.max_errors,
                "max_no_progress": policy.max_no_progress,
            },
            ensure_ascii=False,
        ),
    )


def main() -> None:
    print("=== SCENARIO 1: GOAL REACHED ===")
    print_policy(POLICY)
    result_ok = run_agent(
        task=TASK,
        user_id=42,
        fail_fetch_times=1,
        policy=POLICY,
    )
    print("Run result:", compact_result(result_ok))

    print("\n=== SCENARIO 2: STOPPED BY ERROR LIMIT ===")
    print_policy(POLICY)
    result_stopped = run_agent(
        task=TASK,
        user_id=42,
        fail_fetch_times=10,
        policy=POLICY,
    )
    print("Run result:", compact_result(result_stopped))

    print("\n=== SCENARIO 3: STOPPED BY STEP LIMIT ===")
    print_policy(STEP_LIMIT_POLICY)
    result_step_limit = run_agent(
        task=TASK,
        user_id=42,
        fail_fetch_times=0,
        policy=STEP_LIMIT_POLICY,
    )
    print("Run result:", compact_result(result_step_limit))


if __name__ == "__main__":
    main()
