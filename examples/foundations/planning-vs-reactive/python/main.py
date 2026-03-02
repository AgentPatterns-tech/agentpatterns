from planning_agent import run_planning_agent
from reactive_agent import run_reactive_agent

TASK = "Prepare a short account summary for user_id=42 with profile, orders, and balance."
USER_ID = 42


def print_result(result: dict) -> None:
    print(f"\n=== {result['mode'].upper()} ===")
    print(f"done={result['done']} | steps={result['steps']}")
    print("summary:", result["state"].get("summary"))
    print("\ntrace:")
    for line in result["trace"]:
        print(" ", line)


def main() -> None:
    planning = run_planning_agent(task=TASK, user_id=USER_ID)
    reactive = run_reactive_agent(task=TASK, user_id=USER_ID)

    print_result(planning)
    print_result(reactive)


if __name__ == "__main__":
    main()
