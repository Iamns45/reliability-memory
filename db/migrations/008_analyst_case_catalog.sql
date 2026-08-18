CREATE TABLE IF NOT EXISTS analyst_cases (
  case_id STRING PRIMARY KEY,
  customer_id STRING NOT NULL REFERENCES customers (customer_id),
  title STRING NOT NULL,
  queue_status STRING NOT NULL,
  priority STRING NOT NULL CHECK (priority IN ('LOW', 'NORMAL', 'HIGH', 'URGENT')),
  task_type STRING NOT NULL,
  request_text STRING NOT NULL,
  requested_amount DECIMAL(18, 2) NOT NULL CHECK (requested_amount > 0),
  existing_credit DECIMAL(18, 2) NOT NULL DEFAULT 0 CHECK (existing_credit >= 0),
  fraud_signal BOOL NOT NULL DEFAULT false,
  ground_truth_amount DECIMAL(18, 2),
  expected_mode STRING NOT NULL CHECK (expected_mode IN ('AUTO', 'VERIFY', 'HUMAN', 'DENY')),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  INDEX analyst_queue_idx (queue_status, priority, created_at DESC),
  INDEX analyst_customer_idx (customer_id, created_at DESC)
);

GRANT SELECT ON TABLE analyst_cases TO reliability_runtime;

UPSERT INTO customers (
  customer_id, display_name, account_type, region, contract_type, metadata
) VALUES
  ('C-201', 'Aisha Patel', 'standard', 'US', 'standard', '{"synthetic":true}'),
  ('C-202', 'Liam Wilson', 'premium', 'CA', 'standard', '{"synthetic":true}'),
  ('C-203', 'Olivia Martin', 'standard', 'UK', 'standard', '{"synthetic":true}'),
  ('C-204', 'Ethan Walker', 'standard', 'US', 'standard', '{"synthetic":true}'),
  ('C-205', 'Sophia Nguyen', 'premium', 'AU', 'standard', '{"synthetic":true}'),
  ('C-206', 'Marcus Reed', 'standard', 'US', 'standard', '{"synthetic":true}'),
  ('C-207', 'Priya Shah', 'premium', 'IN', 'standard', '{"synthetic":true}'),
  ('C-208', 'Gabriel Lopez', 'standard', 'MX', 'standard', '{"synthetic":true}'),
  ('C-209', 'Natalie Kim', 'premium', 'KR', 'standard', '{"synthetic":true}'),
  ('C-210', 'Jordan Ellis', 'standard', 'US', 'standard', '{"synthetic":true}'),
  ('C-211', 'Hannah Moore', 'premium', 'US', 'standard', '{"synthetic":true}'),
  ('C-212', 'Amir Hassan', 'standard', 'AE', 'standard', '{"synthetic":true}'),
  ('C-213', 'Chloe Anderson', 'standard', 'US', 'standard', '{"synthetic":true}');

UPSERT INTO analyst_cases (
  case_id, customer_id, title, queue_status, priority, task_type,
  request_text, requested_amount, existing_credit, fraud_signal,
  ground_truth_amount, expected_mode, created_at
) VALUES
  ('CASE-184-26', 'C-184', 'Reactivation produced a second settled charge', 'AUTO_READY', 'NORMAL', 'duplicate_charge_refund', 'I was charged twice after reactivating my subscription. Please refund the duplicate $79 charge.', 79, 20, false, 79, 'AUTO', '2026-08-16 13:18:00+00:00'),
  ('CASE-201-26', 'C-201', 'Similar amounts came from different payment methods', 'EVIDENCE_BLOCKED', 'NORMAL', 'duplicate_charge_refund', 'I see two $42 charges. Please refund one of them.', 42, 0, false, NULL, 'HUMAN', '2026-08-16 13:17:00+00:00'),
  ('CASE-202-26', 'C-202', 'Premium annual add-on captured twice', 'AUTO_READY', 'NORMAL', 'duplicate_charge_refund', 'The annual analytics add-on was charged twice for $129.', 129, 15, false, 129, 'AUTO', '2026-08-16 13:16:00+00:00'),
  ('CASE-203-26', 'C-203', 'Duplicate was already refunded by the provider', 'EVIDENCE_BLOCKED', 'NORMAL', 'duplicate_charge_refund', 'Please refund the second $89 charge on my account.', 89, 0, false, NULL, 'HUMAN', '2026-08-16 13:15:00+00:00'),
  ('CASE-204-26', 'C-204', 'Second card entry is authorized but not settled', 'EVIDENCE_BLOCKED', 'NORMAL', 'duplicate_charge_refund', 'There are two $64 entries, but one may still be pending.', 64, 0, false, NULL, 'HUMAN', '2026-08-16 13:14:00+00:00'),
  ('CASE-205-26', 'C-205', 'Matching charges fall outside the duplicate window', 'EVIDENCE_BLOCKED', 'NORMAL', 'duplicate_charge_refund', 'Two $119 charges appeared about twenty minutes apart.', 119, 0, false, NULL, 'HUMAN', '2026-08-16 13:13:00+00:00'),
  ('CASE-206-26', 'C-206', 'A bank dispute already exists on the second charge', 'EVIDENCE_BLOCKED', 'HIGH', 'duplicate_charge_refund', 'I disputed one $55 charge and also want a refund here.', 55, 0, false, NULL, 'HUMAN', '2026-08-16 13:12:00+00:00'),
  ('CASE-207-26', 'C-207', 'Three identical captures make the duplicate ambiguous', 'EVIDENCE_BLOCKED', 'HIGH', 'duplicate_charge_refund', 'I was charged $145 three times. Please fix the duplicates.', 145, 0, false, NULL, 'HUMAN', '2026-08-16 13:11:00+00:00'),
  ('CASE-208-26', 'C-208', 'Confirmed duplicate exceeds the standard-account envelope', 'VERIFY_REQUIRED', 'NORMAL', 'duplicate_charge_refund', 'A $240 team subscription payment was captured twice.', 240, 0, false, 240, 'VERIFY', '2026-08-16 13:10:00+00:00'),
  ('CASE-209-26', 'C-209', 'Confirmed premium duplicate exceeds the delegated cap', 'VERIFY_REQUIRED', 'NORMAL', 'duplicate_charge_refund', 'The $315 professional bundle posted twice.', 315, 25, false, 315, 'VERIFY', '2026-08-16 13:09:00+00:00'),
  ('CASE-210-26', 'C-210', 'Customer claim has only one provider payment', 'EVIDENCE_BLOCKED', 'NORMAL', 'duplicate_charge_refund', 'My bank app shows two $73 charges.', 73, 0, false, NULL, 'HUMAN', '2026-08-16 13:08:00+00:00'),
  ('CASE-211-26', 'C-211', 'Exact duplicate is paired with an account abuse signal', 'RISK_REVIEW', 'URGENT', 'duplicate_charge_refund', 'Refund one of the two $120 charges immediately.', 120, 0, true, 120, 'HUMAN', '2026-08-16 13:07:00+00:00'),
  ('CASE-044-26', 'C-044', 'Enterprise SLA credit under a custom addendum', 'RISK_REVIEW', 'HIGH', 'enterprise_sla_credit', 'Apply the $8,000 service-level credit under our custom availability addendum.', 8000, 0, false, 8000, 'HUMAN', '2026-08-16 13:06:00+00:00'),
  ('CASE-771-26', 'C-771', 'Novel EU education contract exception', 'NOVEL_CONTEXT', 'NORMAL', 'education_contract_exception', 'Refund the unused $310 portion of our educational service agreement.', 310, 0, false, 155, 'HUMAN', '2026-08-16 13:05:00+00:00'),
  ('CASE-841-26', 'C-841', 'Reviewer can teach the education credit exception', 'LEARNING_REVIEW', 'NORMAL', 'education_contract_exception', 'We ended the program early. Refund the remaining $310 service balance.', 310, 0, false, 155, 'HUMAN', '2026-08-16 13:04:00+00:00'),
  ('CASE-992-26', 'C-992', 'Future education case can replay a verified correction', 'LEARNING_REPLAY', 'NORMAL', 'education_contract_exception', 'We ended our program with $280 unused. Please return the balance.', 280, 0, false, 140, 'HUMAN', '2026-08-16 13:03:00+00:00'),
  ('CASE-212-26', 'C-212', 'Billing error supported by invoice adjustment history', 'VERIFY_REQUIRED', 'NORMAL', 'billing_error_refund', 'The invoice retained a $186 seat charge after the seat was removed.', 186, 0, false, 186, 'VERIFY', '2026-08-16 13:02:00+00:00'),
  ('CASE-213-26', 'C-213', 'Low-impact billing correction with supervised evidence', 'VERIFY_REQUIRED', 'LOW', 'billing_error_refund', 'A removed workspace was still billed for $85 this month.', 85, 0, false, 85, 'VERIFY', '2026-08-16 13:01:00+00:00');

UPSERT INTO customer_events (event_id, customer_id, event_type, event_at, data) VALUES
  ('00000000-0000-4000-9000-000000000201', 'C-201', 'support_contact', '2026-08-15 15:10:00+00:00', '{"channel":"chat","bank_screenshot":true}'),
  ('00000000-0000-4000-9000-000000000202', 'C-202', 'addon_purchase', '2026-08-14 10:14:00+00:00', '{"sku":"analytics-annual"}'),
  ('00000000-0000-4000-9000-000000000203', 'C-203', 'provider_refund', '2026-08-15 11:04:00+00:00', '{"amount":89}'),
  ('00000000-0000-4000-9000-000000000204', 'C-204', 'authorization_pending', '2026-08-16 08:05:00+00:00', '{"amount":64}'),
  ('00000000-0000-4000-9000-000000000205', 'C-205', 'plan_change', '2026-08-15 09:00:00+00:00', '{"from":"monthly","to":"annual"}'),
  ('00000000-0000-4000-9000-000000000206', 'C-206', 'bank_dispute_opened', '2026-08-16 12:00:00+00:00', '{"amount":55}'),
  ('00000000-0000-4000-9000-000000000207', 'C-207', 'triple_capture_alert', '2026-08-16 07:10:00+00:00', '{"count":3}'),
  ('00000000-0000-4000-9000-000000000208', 'C-208', 'team_plan_purchase', '2026-08-15 16:01:00+00:00', '{"seats":8}'),
  ('00000000-0000-4000-9000-000000000209', 'C-209', 'bundle_upgrade', '2026-08-15 18:00:00+00:00', '{"bundle":"professional"}'),
  ('00000000-0000-4000-9000-000000000210', 'C-210', 'bank_screenshot_received', '2026-08-16 10:00:00+00:00', '{"verified":false}'),
  ('00000000-0000-4000-9000-000000000211', 'C-211', 'abuse_signal', '2026-08-16 06:55:00+00:00', '{"rule":"refund_velocity"}'),
  ('00000000-0000-4000-9000-000000000212', 'C-212', 'seat_removed', '2026-08-01 11:00:00+00:00', '{"seat_count_delta":-1}'),
  ('00000000-0000-4000-9000-000000000213', 'C-213', 'workspace_removed', '2026-08-01 10:00:00+00:00', '{"workspace":"archive-team"}');

UPSERT INTO payment_transactions (
  payment_id, customer_id, provider, merchant_reference,
  subscription_reference, billing_period, payment_method_fingerprint,
  amount, currency, status, captured_at, refunded_at, reversed_at,
  disputed_at, metadata
) VALUES
  ('pay_201_original', 'C-201', 'stripe-simulator', 'invoice_201_2026_08', 'sub_201', '2026-08', 'pm_201_primary', 42, 'USD', 'settled', '2026-08-15 14:02:00+00:00', NULL, NULL, NULL, '{"synthetic":true}'),
  ('pay_201_duplicate', 'C-201', 'stripe-simulator', 'invoice_201_2026_08', 'sub_201', '2026-08', 'pm_201_secondary', 42, 'USD', 'settled', '2026-08-15 14:03:00+00:00', NULL, NULL, NULL, '{"synthetic":true}'),
  ('pay_202_original', 'C-202', 'stripe-simulator', 'invoice_202_2026_08', 'sub_202', '2026-08', 'pm_202_primary', 129, 'USD', 'settled', '2026-08-14 10:14:05+00:00', NULL, NULL, NULL, '{"synthetic":true}'),
  ('pay_202_duplicate', 'C-202', 'stripe-simulator', 'invoice_202_2026_08', 'sub_202', '2026-08', 'pm_202_primary', 129, 'USD', 'settled', '2026-08-14 10:15:11+00:00', NULL, NULL, NULL, '{"synthetic":true}'),
  ('pay_203_original', 'C-203', 'stripe-simulator', 'invoice_203_2026_08', 'sub_203', '2026-08', 'pm_203_primary', 89, 'USD', 'settled', '2026-08-15 10:02:00+00:00', NULL, NULL, NULL, '{"synthetic":true}'),
  ('pay_203_duplicate', 'C-203', 'stripe-simulator', 'invoice_203_2026_08', 'sub_203', '2026-08', 'pm_203_primary', 89, 'USD', 'settled', '2026-08-15 10:03:10+00:00', '2026-08-15 11:04:00+00:00', NULL, NULL, '{"synthetic":true}'),
  ('pay_204_original', 'C-204', 'stripe-simulator', 'invoice_204_2026_08', 'sub_204', '2026-08', 'pm_204_primary', 64, 'USD', 'settled', '2026-08-16 08:02:00+00:00', NULL, NULL, NULL, '{"synthetic":true}'),
  ('pay_204_duplicate', 'C-204', 'stripe-simulator', 'invoice_204_2026_08', 'sub_204', '2026-08', 'pm_204_primary', 64, 'USD', 'authorized', '2026-08-16 08:03:00+00:00', NULL, NULL, NULL, '{"synthetic":true}'),
  ('pay_205_original', 'C-205', 'stripe-simulator', 'invoice_205_2026_08', 'sub_205', '2026-08', 'pm_205_primary', 119, 'USD', 'settled', '2026-08-15 09:02:00+00:00', NULL, NULL, NULL, '{"synthetic":true}'),
  ('pay_205_duplicate', 'C-205', 'stripe-simulator', 'invoice_205_2026_08', 'sub_205', '2026-08', 'pm_205_primary', 119, 'USD', 'settled', '2026-08-15 09:23:00+00:00', NULL, NULL, NULL, '{"synthetic":true}'),
  ('pay_206_original', 'C-206', 'stripe-simulator', 'invoice_206_2026_08', 'sub_206', '2026-08', 'pm_206_primary', 55, 'USD', 'settled', '2026-08-15 12:02:00+00:00', NULL, NULL, NULL, '{"synthetic":true}'),
  ('pay_206_duplicate', 'C-206', 'stripe-simulator', 'invoice_206_2026_08', 'sub_206', '2026-08', 'pm_206_primary', 55, 'USD', 'settled', '2026-08-15 12:03:00+00:00', NULL, NULL, '2026-08-16 12:00:00+00:00', '{"synthetic":true}'),
  ('pay_207_original', 'C-207', 'stripe-simulator', 'invoice_207_2026_08', 'sub_207', '2026-08', 'pm_207_primary', 145, 'USD', 'settled', '2026-08-16 07:02:00+00:00', NULL, NULL, NULL, '{"synthetic":true}'),
  ('pay_207_duplicate', 'C-207', 'stripe-simulator', 'invoice_207_2026_08', 'sub_207', '2026-08', 'pm_207_primary', 145, 'USD', 'settled', '2026-08-16 07:03:00+00:00', NULL, NULL, NULL, '{"synthetic":true}'),
  ('pay_207_third', 'C-207', 'stripe-simulator', 'invoice_207_2026_08', 'sub_207', '2026-08', 'pm_207_primary', 145, 'USD', 'settled', '2026-08-16 07:04:00+00:00', NULL, NULL, NULL, '{"synthetic":true}'),
  ('pay_208_original', 'C-208', 'stripe-simulator', 'invoice_208_2026_08', 'sub_208', '2026-08', 'pm_208_primary', 240, 'USD', 'settled', '2026-08-15 16:02:00+00:00', NULL, NULL, NULL, '{"synthetic":true}'),
  ('pay_208_duplicate', 'C-208', 'stripe-simulator', 'invoice_208_2026_08', 'sub_208', '2026-08', 'pm_208_primary', 240, 'USD', 'settled', '2026-08-15 16:03:20+00:00', NULL, NULL, NULL, '{"synthetic":true}'),
  ('pay_209_original', 'C-209', 'stripe-simulator', 'invoice_209_2026_08', 'sub_209', '2026-08', 'pm_209_primary', 315, 'USD', 'settled', '2026-08-15 18:02:00+00:00', NULL, NULL, NULL, '{"synthetic":true}'),
  ('pay_209_duplicate', 'C-209', 'stripe-simulator', 'invoice_209_2026_08', 'sub_209', '2026-08', 'pm_209_primary', 315, 'USD', 'settled', '2026-08-15 18:04:00+00:00', NULL, NULL, NULL, '{"synthetic":true}'),
  ('pay_210_only', 'C-210', 'stripe-simulator', 'invoice_210_2026_08', 'sub_210', '2026-08', 'pm_210_primary', 73, 'USD', 'settled', '2026-08-16 09:02:00+00:00', NULL, NULL, NULL, '{"synthetic":true}'),
  ('pay_211_original', 'C-211', 'stripe-simulator', 'invoice_211_2026_08', 'sub_211', '2026-08', 'pm_211_primary', 120, 'USD', 'settled', '2026-08-16 07:02:00+00:00', NULL, NULL, NULL, '{"synthetic":true}'),
  ('pay_211_duplicate', 'C-211', 'stripe-simulator', 'invoice_211_2026_08', 'sub_211', '2026-08', 'pm_211_primary', 120, 'USD', 'settled', '2026-08-16 07:03:00+00:00', NULL, NULL, NULL, '{"synthetic":true}');
