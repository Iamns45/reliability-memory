from __future__ import annotations

from typing import Any

from ..repository import MemoryRepository


class CustomerContextSkill:
    def __init__(self, repository: MemoryRepository) -> None:
        self.repository = repository

    def load(self, customer_id: str) -> dict[str, Any]:
        return self.repository.get_customer_context(customer_id)
