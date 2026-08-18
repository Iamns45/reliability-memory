from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from .domain import ReliabilityEvidence


@dataclass(frozen=True)
class HistoricalStats:
    verified_cases: int
    successes: int
    failures: int
    human_overrides: int
    average_similarity: float = 1.0
    last_verified_at: datetime | None = None


class ReliabilityEngine:
    """Compute empirical reliability from verified history, never model confidence."""

    def evaluate(
        self,
        stats: HistoricalStats,
        novelty: str = "LOW",
        relevant_corrections: int = 0,
        memory_enabled: bool = True,
    ) -> ReliabilityEvidence:
        counts = (
            stats.verified_cases,
            stats.successes,
            stats.failures,
            stats.human_overrides,
        )
        if any(count < 0 for count in counts):
            raise ValueError("outcome counts cannot be negative")

        if stats.verified_cases <= 0:
            return ReliabilityEvidence(
                reliability=0.0,
                verified_cases=0,
                successes=0,
                failures=0,
                human_overrides=0,
                average_similarity=0.0,
                evidence_quality="NONE",
                novelty="HIGH",
                relevant_corrections=relevant_corrections,
                memory_enabled=memory_enabled,
            )

        if stats.successes + stats.failures + stats.human_overrides > stats.verified_cases:
            raise ValueError("outcome counts cannot exceed verified cases")

        observed_rate = stats.successes / stats.verified_cases
        override_penalty = (stats.human_overrides / stats.verified_cases) * 0.25
        evidence_factor = min(1.0, stats.verified_cases / 100.0)
        similarity = max(0.0, min(1.0, stats.average_similarity))
        recency_factor = self._recency_factor(stats.last_verified_at)
        novelty_penalty = {"LOW": 0.0, "MEDIUM": 0.03, "HIGH": 0.12}.get(
            novelty,
            0.12,
        )

        # Each penalty is inspectable in an audit trace. Similarity is evidence
        # relevance, not a permission signal, so it is intentionally capped.
        score = (
            observed_rate
            - override_penalty
            - ((1.0 - similarity) * 0.05)
            - ((1.0 - recency_factor) * 0.10)
            - ((1.0 - evidence_factor) * 0.02)
            - novelty_penalty
        )

        if stats.verified_cases >= 100 and stats.average_similarity >= 0.85:
            quality = "HIGH"
        elif stats.verified_cases >= 20 and stats.average_similarity >= 0.70:
            quality = "MEDIUM"
        else:
            quality = "LOW"

        return ReliabilityEvidence(
            reliability=round(max(0.0, min(1.0, score)), 4),
            verified_cases=stats.verified_cases,
            successes=stats.successes,
            failures=stats.failures,
            human_overrides=stats.human_overrides,
            average_similarity=round(stats.average_similarity, 4),
            evidence_quality=quality,
            novelty=novelty,
            relevant_corrections=relevant_corrections,
            memory_enabled=memory_enabled,
            last_verified_at=stats.last_verified_at,
        )

    @staticmethod
    def _recency_factor(last_verified_at: datetime | None) -> float:
        if last_verified_at is None:
            return 0.85
        now = datetime.now(timezone.utc)
        candidate = (
            last_verified_at
            if last_verified_at.tzinfo
            else last_verified_at.replace(tzinfo=timezone.utc)
        )
        days = max(0, (now - candidate).days)
        if days <= 30:
            return 1.0
        if days <= 90:
            return 0.97
        if days <= 180:
            return 0.92
        return 0.85
