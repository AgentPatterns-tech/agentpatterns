from dataclasses import dataclass, field
from typing import Any


@dataclass
class ShortMemory:
    max_items: int = 6
    items: list[dict[str, Any]] = field(default_factory=list)

    def add(self, role: str, content: str) -> None:
        self.items.append({"role": role, "content": content})
        if len(self.items) > self.max_items:
            self.items = self.items[-self.max_items :]

    def snapshot(self) -> list[dict[str, Any]]:
        return list(self.items)

    def clear(self) -> None:
        self.items.clear()


@dataclass
class LongMemoryStore:
    _prefs: dict[str, dict[str, str]] = field(default_factory=dict)

    def save_prefs(self, user_key: str, prefs: dict[str, str]) -> None:
        self._prefs[user_key] = dict(prefs)

    def load_prefs(self, user_key: str) -> dict[str, str]:
        return dict(self._prefs.get(user_key, {}))
