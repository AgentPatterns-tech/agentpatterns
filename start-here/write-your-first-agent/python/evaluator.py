def parse_int(text: str) -> int | None:
    """Returns int or None if the text is not a valid integer."""
    try:
        return int(text.strip())
    except (ValueError, AttributeError):
        return None

def is_goal_reached(number: int, goal: int) -> bool:
    """Returns True if the number satisfies the goal condition."""
    return number > goal
