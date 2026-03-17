from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List


class BaseAgent(ABC):
    """
    PM-required SOP interface:
    Input -> Process -> Output -> Feedback

    Notes:
    - `process()` MUST return a dict containing a structured 'reasoning' payload
      suitable for OpenClaw-style UI rendering.
    """

    def __init__(self, name: str, role: str):
        self.name = name
        self.role = role
        self.memory: List[Dict[str, Any]] = []

    @abstractmethod
    async def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Core processing logic.

        Contract:
        - Return value MUST include:
          - 'reasoning': structured log object
        """
        raise NotImplementedError

    def log_reasoning(self, thought: str, decision: Any) -> Dict[str, Any]:
        """
        Structured reasoning log for OpenClaw UI rendering.
        """
        entry = {"agent": self.name, "role": self.role, "thought": thought, "decision": decision}
        self.memory.append(entry)
        return entry
