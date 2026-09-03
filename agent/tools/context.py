from __future__ import annotations

from datetime import date

from core.state import State
from core.state import state as default_state


class ToolContext:
    def __init__(self, run_id: str, as_of: date, store: State | None = None) -> None:
        self.run_id = run_id
        self.as_of = as_of
        self.store = store or default_state
