from agent import build_weekly_report, save_user_preferences
from memory import LongMemoryStore, ShortMemory

USER_ID = 42
USER_KEY = "user:anna"


def print_result(title: str, result: dict) -> None:
    print(f"\n=== {title} ===")
    print("Resolved prefs:", result["prefs"])
    print("\nReport:")
    print(result["report"])
    print("\nTrace:")
    for line in result["trace"]:
        print(" ", line)


def main() -> None:
    long_memory = LongMemoryStore()

    # Scenario 1: only short-term memory, early instruction falls out of context.
    short_memory_1 = ShortMemory(max_items=4)
    short_memory_1.add("user", "pref:report_format=short-bullets")
    short_memory_1.add("user", "pref:currency=EUR")
    short_memory_1.add("assistant", "working...")
    short_memory_1.add("assistant", "still working...")
    short_memory_1.add("assistant", "collecting data...")  # pushes out old prefs

    result_short_only = build_weekly_report(
        user_id=USER_ID,
        user_key=USER_KEY,
        request="Build weekly sales report",
        short_memory=short_memory_1,
        long_memory=long_memory,
        use_long_memory=False,
    )
    print_result("SCENARIO 1: SHORT MEMORY ONLY", result_short_only)

    # Scenario 2: persist prefs in long-term memory, then start a new task.
    short_memory_2 = ShortMemory(max_items=4)
    save_user_preferences(
        user_key=USER_KEY,
        prefs={"report_format": "short-bullets", "currency": "EUR"},
        short_memory=short_memory_2,
        long_memory=long_memory,
    )
    short_memory_2.clear()  # new task, short memory resets

    result_with_long = build_weekly_report(
        user_id=USER_ID,
        user_key=USER_KEY,
        request="Build weekly sales report like last time",
        short_memory=short_memory_2,
        long_memory=long_memory,
        use_long_memory=True,
    )
    print_result("SCENARIO 2: WITH LONG MEMORY", result_with_long)


if __name__ == "__main__":
    main()
