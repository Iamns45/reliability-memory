from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.domain import CustomerCase
from app.payment_evidence import assess_duplicate_payment


class DuplicatePaymentEvidenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.case = CustomerCase(
            "C-184",
            "duplicate_charge_refund",
            "I was charged twice.",
            79,
            existing_credit=20,
        )
        self.payments = [
            self.payment("pay_original", "2026-08-15T14:02:00+00:00"),
            self.payment("pay_duplicate", "2026-08-15T14:03:27+00:00"),
        ]

    def test_exact_settled_pair_confirms_full_duplicate_amount(self) -> None:
        evidence = assess_duplicate_payment(self.case, {"payments": self.payments})
        self.assertIsNotNone(evidence)
        assert evidence is not None
        self.assertTrue(evidence.duplicate_confirmed)
        self.assertEqual(evidence.amount, 79)
        self.assertEqual(evidence.capture_gap_seconds, 87)

    def test_existing_refund_blocks_automatic_eligibility(self) -> None:
        self.payments[1]["refunded"] = True
        evidence = assess_duplicate_payment(self.case, {"payments": self.payments})
        self.assertIsNotNone(evidence)
        assert evidence is not None
        self.assertFalse(evidence.duplicate_confirmed)
        self.assertIn("already has a refund", " ".join(evidence.blocking_reasons))

    def test_requested_amount_must_equal_duplicate_payment(self) -> None:
        case = CustomerCase("C-184", "duplicate_charge_refund", "charged twice", 59)
        evidence = assess_duplicate_payment(case, {"payments": self.payments})
        self.assertIsNotNone(evidence)
        assert evidence is not None
        self.assertFalse(evidence.duplicate_confirmed)
        self.assertIn("requested amount", " ".join(evidence.blocking_reasons).lower())

    def test_request_text_without_payment_pair_is_not_evidence(self) -> None:
        evidence = assess_duplicate_payment(self.case, {"payments": []})
        self.assertIsNotNone(evidence)
        assert evidence is not None
        self.assertFalse(evidence.duplicate_confirmed)

    def test_different_payment_method_is_not_a_duplicate_pair(self) -> None:
        self.payments[1]["payment_method_fingerprint"] = "pm_different"
        evidence = assess_duplicate_payment(self.case, {"payments": self.payments})
        self.assertIsNotNone(evidence)
        assert evidence is not None
        self.assertFalse(evidence.duplicate_confirmed)
        self.assertIn("No two payments match", " ".join(evidence.blocking_reasons))

    def test_different_provider_is_not_an_automatic_duplicate_pair(self) -> None:
        self.payments[1]["provider"] = "different-provider"
        evidence = assess_duplicate_payment(self.case, {"payments": self.payments})
        self.assertIsNotNone(evidence)
        assert evidence is not None
        self.assertFalse(evidence.duplicate_confirmed)

    def test_non_settled_payment_blocks_eligibility(self) -> None:
        self.payments[1]["status"] = "authorized"
        evidence = assess_duplicate_payment(self.case, {"payments": self.payments})
        self.assertIsNotNone(evidence)
        assert evidence is not None
        self.assertFalse(evidence.duplicate_confirmed)
        self.assertIn("must be settled", " ".join(evidence.blocking_reasons))

    def test_payment_outside_duplicate_window_blocks_eligibility(self) -> None:
        self.payments[1]["captured_at"] = "2026-08-15T14:20:00+00:00"
        evidence = assess_duplicate_payment(self.case, {"payments": self.payments})
        self.assertIsNotNone(evidence)
        assert evidence is not None
        self.assertFalse(evidence.duplicate_confirmed)
        self.assertIn("ten-minute", " ".join(evidence.blocking_reasons))

    def test_dispute_blocks_eligibility(self) -> None:
        self.payments[1]["disputed"] = True
        evidence = assess_duplicate_payment(self.case, {"payments": self.payments})
        self.assertIsNotNone(evidence)
        assert evidence is not None
        self.assertFalse(evidence.duplicate_confirmed)
        self.assertIn("disputed", " ".join(evidence.blocking_reasons))

    def test_multiple_possible_pairs_require_human_selection(self) -> None:
        second_pair = [
            {
                **self.payment("pay_other_original", "2026-08-15T15:02:00+00:00"),
                "amount": 45.0,
                "billing_period": "2026-09",
            },
            {
                **self.payment("pay_other_duplicate", "2026-08-15T15:03:00+00:00"),
                "amount": 45.0,
                "billing_period": "2026-09",
            },
        ]
        evidence = assess_duplicate_payment(
            self.case,
            {"payments": [*self.payments, *second_pair]},
        )
        self.assertIsNotNone(evidence)
        assert evidence is not None
        self.assertFalse(evidence.duplicate_confirmed)
        self.assertIn("multiple possible duplicates", " ".join(evidence.blocking_reasons))

    @staticmethod
    def payment(payment_id: str, captured_at: str) -> dict[str, object]:
        return {
            "payment_id": payment_id,
            "provider": "payment-simulator",
            "merchant_reference": "invoice_C184_2026_08",
            "subscription_reference": "sub_C184_premium",
            "billing_period": "2026-08",
            "payment_method_fingerprint": "pm_demo_184",
            "amount": 79.0,
            "currency": "USD",
            "status": "settled",
            "captured_at": captured_at,
            "refunded": False,
            "reversed": False,
            "disputed": False,
        }


if __name__ == "__main__":
    unittest.main()
