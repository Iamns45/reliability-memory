from __future__ import annotations

from datetime import datetime
from typing import Any

from .domain import DuplicatePaymentEvidence, CustomerCase


MATCH_FIELDS = (
    "provider",
    "amount",
    "currency",
    "merchant_reference",
    "subscription_reference",
    "billing_period",
    "payment_method_fingerprint",
)
MAX_DUPLICATE_GAP_SECONDS = 10 * 60
REQUIRED_SAFEGUARDS = (
    "both_charges_settled",
    "no_existing_refund",
    "no_reversal",
    "no_dispute_or_chargeback",
    "captured_within_ten_minutes",
    "requested_amount_matches_duplicate",
)


def assess_duplicate_payment(
    case: CustomerCase,
    customer_context: dict[str, Any],
) -> DuplicatePaymentEvidence | None:
    """Confirm one duplicate from structured provider records, never request text."""

    if case.task_type != "duplicate_charge_refund":
        return None

    raw_payments = customer_context.get("payments", [])
    payments = [dict(payment) for payment in raw_payments if isinstance(payment, dict)]
    if len(payments) < 2:
        return _blocked(len(payments), "Fewer than two payment records were found.")

    complete: list[dict[str, Any]] = []
    for payment in payments:
        if all(payment.get(field) not in {None, ""} for field in MATCH_FIELDS):
            complete.append(payment)
    if len(complete) < 2:
        return _blocked(
            len(payments),
            "Payment records are missing fields required for deterministic matching.",
        )

    groups: dict[tuple[str, ...], list[dict[str, Any]]] = {}
    for payment in complete:
        key = tuple(_normalized(payment[field]) for field in MATCH_FIELDS)
        groups.setdefault(key, []).append(payment)
    candidates = [group for group in groups.values() if len(group) >= 2]
    if not candidates:
        return _blocked(len(payments), "No two payments match the same bill and payment method.")
    if len(candidates) != 1 or len(candidates[0]) != 2:
        return _blocked(
            len(payments),
            "The ledger contains multiple possible duplicates; a reviewer must select the pair.",
        )

    pair = sorted(candidates[0], key=lambda payment: _captured_at(payment))
    original, duplicate = pair
    amount = round(float(duplicate["amount"]), 2)
    currency = str(duplicate["currency"]).upper()
    status_values = {str(payment.get("status", "")).lower() for payment in pair}
    blockers: list[str] = []
    if status_values != {"settled"}:
        blockers.append("Both matching payments must be settled charges.")
    if any(bool(payment.get("refunded")) for payment in pair):
        blockers.append("One of the matching payments already has a refund.")
    if any(bool(payment.get("reversed")) for payment in pair):
        blockers.append("One of the matching payments was reversed.")
    if any(bool(payment.get("disputed")) for payment in pair):
        blockers.append("One of the matching payments is disputed or charged back.")
    gap_seconds = abs((_captured_at(duplicate) - _captured_at(original)).total_seconds())
    if gap_seconds > MAX_DUPLICATE_GAP_SECONDS:
        blockers.append("Matching payments are outside the ten-minute duplicate window.")
    if amount != round(case.requested_amount, 2):
        blockers.append("The requested amount does not equal the duplicated settled payment.")

    return DuplicatePaymentEvidence(
        duplicate_confirmed=not blockers,
        checked_payments=len(payments),
        original_payment_id=str(original.get("payment_id")),
        duplicate_payment_id=str(duplicate.get("payment_id")),
        amount=amount,
        currency=currency,
        subscription_reference=str(duplicate.get("subscription_reference")),
        capture_gap_seconds=round(gap_seconds),
        matched_on=MATCH_FIELDS,
        safeguards=REQUIRED_SAFEGUARDS,
        blocking_reasons=tuple(blockers),
    )


def _blocked(checked_payments: int, reason: str) -> DuplicatePaymentEvidence:
    return DuplicatePaymentEvidence(
        duplicate_confirmed=False,
        checked_payments=checked_payments,
        original_payment_id=None,
        duplicate_payment_id=None,
        amount=None,
        currency=None,
        subscription_reference=None,
        capture_gap_seconds=None,
        matched_on=(),
        safeguards=(),
        blocking_reasons=(reason,),
    )


def _captured_at(payment: dict[str, Any]) -> datetime:
    value = payment.get("captured_at")
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    raise ValueError("Payment record is missing a valid captured_at timestamp")


def _normalized(value: Any) -> str:
    if isinstance(value, float):
        return f"{value:.2f}"
    return str(value).strip().lower()
