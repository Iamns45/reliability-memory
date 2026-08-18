# Demo script — 2:58 target

> Status: Current
>
> Audience: Presenters and hackathon judges
>
> Owner: Reliability Memory submission maintainers
>
> Last reviewed: 2026-08-16

Use the [readiness checklist](../operations/RUNBOOK.md#demo-readiness-checklist) before presenting.

## 0:00–0:18 — The consumer-resolution problem

“Customer-support automation still treats damage, delivery, warranty, safety, and identity cases as amount thresholds. Reliability Memory investigates the exact issue, computes the best eligible remedy, and grants only the autonomy earned in that context.”

Open the **Consumer** queue. Do not tour all 26 cases.

## 0:18–1:03 — Case 1: computed remedy plus required confirmation

Open Srinivas's **Cosmetic transit damage** case.

“The $249 espresso machine works but arrived dented. Five current records prove the order, cosmetic condition, customer history, elevated product return rate, and reverse-logistics economics.”

Show the three candidate cards and run the case.

“There is no preferred remedy stored in this case. The runtime validates all three options and calculates goal fit times customer value divided by company cost. The $95 value is not invented: it is a $60 adjustment plus $35 expected two-year warranty coverage. That keep offer scores above replacement and return because it directly fits Srinivas's request to keep the working machine.”

Point to the selection formula and value breakdown.

“Selection is not permission. Because keeping damaged merchandise is a customer choice, policy returns VERIFY and sends the complete packet for confirmation.”

## 1:03–1:37 — Case 2: similar value, different evidence, automatic execution

Open **Blender motor failed after two days** and run it.

“This is not another discount. Serial-linked diagnostics reproduce E17, warranty is active, the batch defect rate is 8.6% versus 1.3%, and unaffected inventory is ready. The resolver selects replacement. Exact evidence plus 500 verified comparable outcomes earns AUTO.”

Show the workflow receipts, containment proof, and persisted episode ID.

“The first case was $60 and required confirmation. This $89 case executes automatically. Amount is not the rule; evidence, customer choice, economics, risk, and verified history are.”

## 1:37–2:18 — Case 3: a human correction changes future behavior

Run `CASE-771-26`, the known defect just after warranty expiry.

“The case is outside normal warranty, so the one typed graph node interrupts only after completing the investigation. The reviewer receives the evidence, alternatives, economics, policy reasons, and suggested repair.”

Click **Verify & teach**, show the correction ID, then run `CASE-841-26`.

“The later case retrieves the verified 14-day grace-period lesson and changes to warranty repair. It remains VERIFY: one lesson changes behavior but does not instantly earn autonomy.”

## 2:18–2:43 — Why evidence-first policy matters

On Srinivas's case, run **Policy v4.9 ↔ v5.0**.

“Legacy v4.9 sees a $60 action and strong history, so it would auto-execute. Version 5.0 sees that accepting cosmetic damage is the customer's decision and correctly requires confirmation. The same comparison can show incomplete current evidence blocking an action that the old amount-first rule would have allowed.”

Mention, but do not run, the retry, memory-ablation, delayed-outcome, and downloadable-receipt controls.

## 2:43–2:58 — Close and generalization proof

“The provider connectors here are deterministic simulations, while the selection, streaming, persistence, idempotency, review, correction replay, and verification are real. CockroachDB keeps the evidence and memory consistent; Bedrock proposes; deterministic code selects and authorizes. The eight enterprise incident cases prove the same engine generalizes without a second graph.”
