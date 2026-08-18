from __future__ import annotations

import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.domain import CustomerCase, SimilarExperience
from app.reliability import HistoricalStats, ReliabilityEngine
from app.skills.experience_memory import ExperienceMemorySkill


class FakeEmbeddingProvider:
    model_id = "test-embedding-model-v1"

    def embed(self, text: str) -> list[float]:
        del text
        return [1.0] + [0.0] * 1_023


class FakeMemoryRepository:
    def __init__(self, experiences: tuple[SimilarExperience, ...]) -> None:
        self.experiences = experiences
        self.requested_embedding_model: str | None = None

    def find_similar_experiences(
        self,
        task_type: str,
        embedding: list[float],
        embedding_model: str,
        limit: int = 5,
    ) -> tuple[SimilarExperience, ...]:
        del task_type, embedding, limit
        self.requested_embedding_model = embedding_model
        return self.experiences

    def get_historical_stats(self, task_type: str) -> HistoricalStats:
        del task_type
        return HistoricalStats(
            verified_cases=500,
            successes=498,
            failures=1,
            human_overrides=1,
            average_similarity=1.0,
            last_verified_at=datetime.now(timezone.utc),
        )

    def __getattr__(self, name: str) -> Any:
        raise AssertionError(f"Unexpected repository call: {name}")


class ExperienceMemoryTests(unittest.TestCase):
    def test_model_identifier_is_forwarded_to_vector_retrieval(self) -> None:
        repository = FakeMemoryRepository(())
        skill = ExperienceMemorySkill(
            repository,  # type: ignore[arg-type]
            FakeEmbeddingProvider(),
            ReliabilityEngine(),
        )

        skill.retrieve(
            CustomerCase(
                customer_id="C-202",
                task_type="early_product_failure",
                request_text="The product failed after two days.",
                requested_amount=89.0,
            )
        )

        self.assertEqual(repository.requested_embedding_model, "test-embedding-model-v1")

    def test_no_compatible_vectors_is_treated_as_high_novelty(self) -> None:
        repository = FakeMemoryRepository(())
        skill = ExperienceMemorySkill(
            repository,  # type: ignore[arg-type]
            FakeEmbeddingProvider(),
            ReliabilityEngine(),
        )

        experiences, evidence, embedding = skill.retrieve(
            CustomerCase(
                customer_id="C-202",
                task_type="early_product_failure",
                request_text="The product failed after two days.",
                requested_amount=89.0,
            )
        )

        self.assertEqual(experiences, ())
        self.assertEqual(len(embedding), 1_024)
        self.assertEqual(evidence.average_similarity, 0.0)
        self.assertEqual(evidence.novelty, "HIGH")
        self.assertEqual(evidence.evidence_quality, "LOW")


if __name__ == "__main__":
    unittest.main()
