CREATE TABLE IF NOT EXISTS payment_transactions (
  payment_id STRING PRIMARY KEY,
  customer_id STRING NOT NULL REFERENCES customers (customer_id),
  provider STRING NOT NULL,
  merchant_reference STRING NOT NULL,
  subscription_reference STRING NOT NULL,
  billing_period STRING NOT NULL,
  payment_method_fingerprint STRING NOT NULL,
  amount DECIMAL(18, 2) NOT NULL CHECK (amount > 0),
  currency STRING NOT NULL CHECK (length(currency) = 3),
  status STRING NOT NULL CHECK (status IN ('authorized', 'settled', 'reversed', 'refunded', 'disputed')),
  captured_at TIMESTAMPTZ NOT NULL,
  refunded_at TIMESTAMPTZ,
  reversed_at TIMESTAMPTZ,
  disputed_at TIMESTAMPTZ,
  metadata JSONB NOT NULL DEFAULT '{}'::JSONB,
  INDEX payment_customer_time_idx (customer_id, captured_at DESC),
  INDEX payment_bill_match_idx (
    customer_id,
    subscription_reference,
    billing_period,
    amount,
    currency,
    captured_at
  )
);

GRANT SELECT ON TABLE payment_transactions TO reliability_runtime;

UPSERT INTO payment_transactions (
  payment_id,
  customer_id,
  provider,
  merchant_reference,
  subscription_reference,
  billing_period,
  payment_method_fingerprint,
  amount,
  currency,
  status,
  captured_at,
  metadata
) VALUES
  (
    'pay_demo_184_original',
    'C-184',
    'payment-simulator',
    'invoice_C184_2026_08',
    'sub_C184_premium',
    '2026-08',
    'pm_demo_184',
    79.00,
    'USD',
    'settled',
    '2026-08-15 14:02:00+00:00',
    '{"synthetic":true,"ledger_role":"original"}'
  ),
  (
    'pay_demo_184_duplicate',
    'C-184',
    'payment-simulator',
    'invoice_C184_2026_08',
    'sub_C184_premium',
    '2026-08',
    'pm_demo_184',
    79.00,
    'USD',
    'settled',
    '2026-08-15 14:03:27+00:00',
    '{"synthetic":true,"ledger_role":"duplicate"}'
  );
