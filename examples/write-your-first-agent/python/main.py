from llm import generate_number
from evaluator import parse_int, is_goal_reached

GOAL = 10
MAX_STEPS = 5

def run():
    for step in range(1, MAX_STEPS + 1):
        print(f"\n🤖 Step {step}: Agent is trying...")

        output = generate_number()
        print(f"💬 Model generated: {output}")

        number = parse_int(output)
        if number is None:
            print("❌ Not a number. Trying again...")
            continue

        if is_goal_reached(number, GOAL):
            print(f"✅ Goal reached! {number} > {GOAL}")
            return

        print(f"❌ Not enough. {number} ≤ {GOAL}. Trying again...")

    print("\n⚠️ Max steps reached without success")

if __name__ == "__main__":
    run()
