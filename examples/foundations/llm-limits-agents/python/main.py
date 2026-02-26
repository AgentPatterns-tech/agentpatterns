from knowledge import build_context, search_kb
from llm import ask_model
from validator import validate_model_output

MAX_STEPS = 4
MIN_CONFIDENCE = 0.65

QUESTION = "Can I get a refund for my subscription if 10 days have passed since payment?"


def run():
    snippets = search_kb(QUESTION, limit=2)
    allowed_sources = {s["id"] for s in snippets}
    context = build_context(snippets, max_chars=700)

    print("Allowed sources:", allowed_sources)
    print("Context:")
    print(context)

    feedback: str | None = None

    for step in range(1, MAX_STEPS + 1):
        print(f"\n=== STEP {step} ===")
        raw = ask_model(QUESTION, context, feedback=feedback)
        print("Model raw output:", raw)

        validation = validate_model_output(raw, allowed_sources)
        if not validation.ok:
            print("Validation failed:", validation.errors)
            feedback = "; ".join(validation.errors)
            continue

        data = validation.data
        assert data is not None

        if data["needs_human"] or data["confidence"] < MIN_CONFIDENCE:
            print("\nHandoff required:")
            print(
                "Model confidence is too low. Escalate this case to a human "
                f"(confidence={data['confidence']})."
            )
            return

        print("\nFinal answer:")
        print(data["answer"])
        print("Citations:", data["citations"])
        return

    print("\nStop: MAX_STEPS reached without a valid answer. Escalate to human.")


if __name__ == "__main__":
    run()
