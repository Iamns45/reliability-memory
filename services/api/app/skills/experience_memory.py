from __future__ import annotations

from ..bedrock import EmbeddingProvider
from ..domain import CustomerCase, ReliabilityEvidence, SimilarExperience
from ..reliability import ReliabilityEngine
from ..repository import MemoryRepository


class ExperienceMemorySkill:
    def __init__(
        self,
        repository: MemoryRepository,
        embeddings: EmbeddingProvider,
        reliability: ReliabilityEngine,
    ) -> None:
        self.repository = repository
        self.embeddings = embeddings
        self.reliability = reliability

    def retrieve(
        self,
        case: CustomerCase,
    ) -> tuple[tuple[SimilarExperience, ...], ReliabilityEvidence, list[float]]:
        embedding = self.embeddings.embed(self._semantic_text(case))
        if not case.memory_enabled:
            evidence = self.reliability.evaluate(
                self.repository.get_historical_stats("__memory_ablation_disabled__"),
                novelty="HIGH",
                memory_enabled=False,
            )
            return (), evidence, embedding

        experiences = self.repository.find_similar_experiences(
            case.task_type,
            embedding,
            self.embeddings.model_id,
            limit=5,
        )
        stats = self.repository.get_historical_stats(case.task_type)
        if experiences:
            average_similarity = sum(item.similarity for item in experiences) / len(experiences)
            stats = type(stats)(
                verified_cases=stats.verified_cases,
                successes=stats.successes,
                failures=stats.failures,
                human_overrides=stats.human_overrides,
                average_similarity=average_similarity,
                last_verified_at=stats.last_verified_at,
            )
        else:
            stats = type(stats)(
                verified_cases=stats.verified_cases,
                successes=stats.successes,
                failures=stats.failures,
                human_overrides=stats.human_overrides,
                average_similarity=0.0,
                last_verified_at=stats.last_verified_at,
            )
        novelty = (
            "HIGH"
            if stats.verified_cases < 20 or not experiences
            else "LOW" if stats.average_similarity >= 0.85 else "MEDIUM"
        )
        relevant_corrections = sum(
            experience.correction_lesson is not None for experience in experiences
        )
        evidence = self.reliability.evaluate(
            stats,
            novelty=novelty,
            relevant_corrections=relevant_corrections,
        )
        return experiences, evidence, embedding

    @staticmethod
    def _semantic_text(case: CustomerCase) -> str:
        return " | ".join(
            [
                case.task_type,
                case.request_text,
                case.account_type,
                case.region,
                case.contract_type,
                f"amount:{case.requested_amount:.2f}",
            ]
        )
