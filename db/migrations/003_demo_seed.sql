UPSERT INTO customers (customer_id, display_name, account_type, region, contract_type, metadata) VALUES
  ('C-184', 'Srinivas', 'premium', 'US', 'standard', '{"synthetic": true}'),
  ('C-044', 'Maya Carter', 'enterprise', 'Global', 'custom_sla', '{"synthetic": true}'),
  ('C-771', 'Daniel Brooks', 'education', 'EU', 'education_custom', '{"synthetic": true}'),
  ('C-841', 'Elena Torres', 'education', 'US', 'education_custom', '{"synthetic": true}'),
  ('C-992', 'Noah Bennett', 'education', 'US', 'education_custom', '{"synthetic": true}');

UPSERT INTO customer_events (event_id, customer_id, event_type, event_at, data) VALUES
  ('00000000-0000-4000-8000-000000000184', 'C-184', 'joined', now() - INTERVAL '10 months', '{"plan":"premium"}'),
  ('00000000-0000-4000-8000-000000000185', 'C-184', 'plan_upgrade', now() - INTERVAL '4 months', '{"from":"standard","to":"premium"}'),
  ('00000000-0000-4000-8000-000000000186', 'C-184', 'duplicate_charge', now() - INTERVAL '3 months', '{"amount":79,"verified":true}'),
  ('00000000-0000-4000-8000-000000000187', 'C-184', 'goodwill_credit', now() - INTERVAL '2 months', '{"amount":20}'),
  ('00000000-0000-4000-8000-000000000044', 'C-044', 'contract_exception', now() - INTERVAL '8 months', '{"approval_required":true}'),
  ('00000000-0000-4000-8000-000000000771', 'C-771', 'joined', now() - INTERVAL '1 month', '{"plan":"education"}');

UPSERT INTO policies (task_type, version, rules, valid_from) VALUES
  ('duplicate_charge_refund', 'refund-policy-v4.3', '{"eligibility":{"source":"payment_ledger","required_status":"settled","exact_fields":["provider","amount","currency","merchant_reference","subscription_reference","billing_period","payment_method_fingerprint"],"maximum_capture_gap_seconds":600,"block_if":["existing_refund","reversal","dispute","chargeback","ambiguous_pair","amount_mismatch"]},"autonomy":{"premium_limit":250,"standard_limit":100,"min_reliability":0.98,"min_verified_cases":100,"required_risk":"LOW"},"human":{"amount_over":1000,"custom_contract":true}}', now() - INTERVAL '1 day');
