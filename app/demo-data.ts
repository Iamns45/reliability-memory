export type DecisionMode = "AUTO" | "VERIFY" | "HUMAN" | "DENY";
export type RiskLevel = "LOW" | "MEDIUM" | "HIGH";

export type MemorySignal = {
  label: string;
  value: string;
  detail: string;
  tone?: "positive" | "warning" | "neutral";
};

export type SimilarCase = {
  id: string;
  summary: string;
  similarity: number;
  outcome: "verified" | "corrected" | "failed";
};

export type EvidenceSource = {
  key: string;
  label: string;
  status: "verified" | "warning" | "blocked";
  summary: string;
  facts: string[];
};

export type ResolutionOption = {
  action: string;
  customerValue: number;
  companyCost: number;
  label: string;
};

export type DemoCase = {
  id: string;
  caseId: string;
  eyebrow: string;
  tabLabel: string;
  title: string;
  customer: string;
  customerId: string;
  account: string;
  request: string;
  reason: string;
  amount: number;
  proposedAmount: number;
  actionType: string;
  companyCost: number;
  customerValue: number;
  customerGoal: string;
  businessGuardrail: string;
  evidenceSources: EvidenceSource[];
  resolutionOptions: ResolutionOption[];
  risk: RiskLevel;
  decision: DecisionMode;
  reliability: number;
  verifiedCases: number;
  successes: number;
  failures: number;
  overrides: number;
  evidenceQuality: "HIGH" | "MEDIUM" | "LOW";
  novelty: "LOW" | "MEDIUM" | "HIGH";
  policy: string;
  rationale: string[];
  memory: MemorySignal[];
  similar: SimilarCase[];
  taskType: string;
  contractType: string;
  fraudSignal?: boolean;
  existingCredit?: number;
  expectedActionAmount: number;
  priority: "LOW" | "NORMAL" | "HIGH" | "URGENT";
  queueStatus: string;
  customerSegment: "consumer" | "enterprise";
  timeline?: Array<{ event: string; at: string; detail: string }>;
  payments?: Array<{
    id: string;
    amount: number;
    status: string;
    capturedAt: string;
    invoice: string;
    paymentMethod: string;
    remediation?: string;
  }>;
  learned?: {
    correction: string;
    lesson: string;
    nextCustomer: string;
    nextCustomerId: string;
    nextCaseId: string;
    nextRequest: string;
    nextAmount: number;
    nextProposedAmount: number;
  };
};

type CaseInput = Omit<
  DemoCase,
  | "eyebrow"
  | "tabLabel"
  | "reason"
  | "reliability"
  | "verifiedCases"
  | "successes"
  | "failures"
  | "overrides"
  | "evidenceQuality"
  | "novelty"
  | "policy"
  | "rationale"
  | "memory"
  | "similar"
  | "contractType"
  | "expectedActionAmount"
  | "customerSegment"
> & {
  issue: string;
  contractType?: string;
  customerSegment?: "consumer" | "enterprise";
};

function source(
  key: string,
  label: string,
  summary: string,
  facts: string[],
  status: EvidenceSource["status"] = "verified",
): EvidenceSource {
  return { key, label, summary, facts, status };
}

function resolutionCase(input: CaseInput): DemoCase {
  const reliable = input.decision === "AUTO" ? 99.2 : input.decision === "DENY" ? 98.4 : 96.8;
  const evidenceCount = input.decision === "AUTO" ? 500 : input.decision === "HUMAN" ? 76 : 164;
  return {
    ...input,
    eyebrow: input.queueStatus.replaceAll("_", " "),
    tabLabel: input.title,
    reason: input.issue,
    contractType: input.contractType ?? "retail_standard",
    customerSegment: input.customerSegment ?? "consumer",
    expectedActionAmount: input.proposedAmount,
    reliability: reliable,
    verifiedCases: evidenceCount,
    successes: Math.max(0, evidenceCount - 3),
    failures: 1,
    overrides: 2,
    evidenceQuality: "HIGH",
    novelty:
      input.decision === "HUMAN" && input.taskType === "warranty_grace_exception"
        ? "MEDIUM"
        : "LOW",
    policy:
      input.decision === "AUTO"
        ? "Complete issue-specific proof, verified history, and bounded company cost permit execution."
        : input.decision === "VERIFY"
          ? "Evidence supports the plan, but customer choice or an exception must be confirmed."
          : input.decision === "DENY"
            ? "Current identity evidence blocks the requested value; provide an appeal path."
            : "Safety, ambiguity, novelty, or financial exposure requires a human owner.",
    rationale: [
      input.evidenceSources[0]?.summary ?? "Current case evidence loaded",
      input.businessGuardrail,
      `${input.customerValue} customer value at ${input.companyCost} estimated company cost`,
    ],
    memory: input.evidenceSources.slice(0, 4).map((item) => ({
      label: item.label,
      value: item.status === "verified" ? "Verified" : "Review",
      detail: item.summary,
      tone: item.status === "verified" ? "positive" : "warning",
    })),
    similar: [
      {
        id: `EP-${input.customerId.replace("C-", "")}01`,
        summary: `Comparable ${input.issue.toLowerCase()} with verified downstream outcome`,
        similarity: 96,
        outcome: "verified",
      },
      {
        id: `EP-${input.customerId.replace("C-", "")}02`,
        summary: "Evidence-specific resolution stayed inside its business guardrail",
        similarity: 91,
        outcome: "verified",
      },
    ],
  };
}

export const cases: DemoCase[] = [
  resolutionCase({
    id: "damaged",
    caseId: "CASE-184-26",
    title: "Damaged but functional: offer a choice",
    customer: "Srinivas",
    customerId: "C-184",
    account: "Premium · US",
    request:
      "My espresso machine arrived dented. It works, but I should not pay full price for damage.",
    issue: "Cosmetic transit damage",
    amount: 249,
    proposedAmount: 60,
    actionType: "partial_refund",
    companyCost: 60,
    customerValue: 95,
    customerGoal: "Receive fair value without waiting for a replacement.",
    businessGuardrail:
      "Ask before applying a keep-item discount and keep cost below return plus refurbishment.",
    evidenceSources: [
      source("order", "Order", "$249 espresso machine delivered yesterday", [
        "ORD-18421",
        "Premium customer",
      ]),
      source("damage_photo", "Damage inspection", "Cosmetic dent; power-on video passes", [
        "98.2% confidence",
        "No water-path damage",
      ]),
      source("customer_history", "Customer history", "18 orders and one prior return", [
        "Lifetime value $2,840",
        "No abuse flags",
      ]),
      source(
        "product_quality",
        "Product reviews",
        "11.8% return rate versus 4.2% category baseline",
        ["312 verified reviews", "Transit dents recur"],
      ),
      source("economics", "Economics", "$60 keep offer beats $152 replacement path", [
        "Replacement landed cost $128",
        "Reverse logistics $24",
      ]),
    ],
    resolutionOptions: [
      {
        action: "partial_refund",
        customerValue: 95,
        companyCost: 60,
        label: "$60 back + extended warranty; keep item",
      },
      {
        action: "replacement",
        customerValue: 249,
        companyCost: 152,
        label: "Replacement and damaged-unit recovery",
      },
      { action: "refund", customerValue: 249, companyCost: 191, label: "Full return and refund" },
    ],
    risk: "LOW",
    decision: "VERIFY",
    taskType: "damaged_item_keep_offer",
    priority: "NORMAL",
    queueStatus: "CUSTOMER_CHOICE",
  }),
  resolutionCase({
    id: "not-found",
    caseId: "CASE-201-26",
    title: "Delivered scan, missing package",
    customer: "Aisha Patel",
    customerId: "C-201",
    account: "Standard · US",
    request: "The carrier says delivered, but there is no package at my door or mailroom.",
    issue: "Delivery not found",
    amount: 72,
    proposedAmount: 72,
    actionType: "reship",
    companyCost: 41,
    customerValue: 72,
    customerGoal: "Receive the item quickly.",
    businessGuardrail: "Open a recoverable carrier claim before reshipping.",
    evidenceSources: [
      source(
        "carrier",
        "Carrier proof",
        "Scan is 310m from address; no photo",
        ["No signature", "Low GPS confidence"],
        "warning",
      ),
      source("address", "Address", "Six successful deliveries to unchanged address", [
        "Mailroom log has no parcel",
      ]),
      source("customer_history", "Claim history", "Zero prior non-delivery claims", [
        "Account age 31 months",
      ]),
      source("inventory", "Inventory", "Replacement available for one-day dispatch", [
        "Landed cost $41",
      ]),
    ],
    resolutionOptions: [
      {
        action: "reship",
        customerValue: 72,
        companyCost: 41,
        label: "Reship and file carrier claim",
      },
      { action: "refund", customerValue: 72, companyCost: 72, label: "Refund after trace" },
    ],
    risk: "MEDIUM",
    decision: "VERIFY",
    taskType: "delivery_not_found",
    priority: "HIGH",
    queueStatus: "CARRIER_REVIEW",
  }),
  resolutionCase({
    id: "early-failure",
    caseId: "CASE-202-26",
    title: "Motor failed after two days",
    customer: "Liam Wilson",
    customerId: "C-202",
    account: "Premium · CA",
    request: "The blender stopped on day two and shows motor error E17.",
    issue: "Early product failure",
    amount: 89,
    proposedAmount: 89,
    actionType: "replacement",
    companyCost: 48,
    customerValue: 89,
    customerGoal: "Get a working product without repeating basic troubleshooting.",
    businessGuardrail:
      "Replace from an unaffected batch only after telemetry proves hardware failure.",
    evidenceSources: [
      source("diagnostics", "Diagnostics", "E17 motor controller failure reproduced", [
        "Firmware current",
        "Thermal reset failed",
      ]),
      source("warranty", "Warranty", "363 days remain", ["No accidental-damage exclusion"]),
      source("product_quality", "Batch quality", "8.6% defect rate versus 1.3% baseline", [
        "Batch B4-26A held",
      ]),
      source("inventory", "Inventory", "Unaffected batch B4-26C available", ["Landed cost $48"]),
    ],
    resolutionOptions: [
      {
        action: "replacement",
        customerValue: 89,
        companyCost: 48,
        label: "Replace from unaffected batch",
      },
      {
        action: "warranty_repair",
        customerValue: 62,
        companyCost: 35,
        label: "Repair in 7–10 days",
      },
    ],
    risk: "LOW",
    decision: "AUTO",
    taskType: "early_product_failure",
    priority: "HIGH",
    queueStatus: "REPLACEMENT_READY",
  }),
  resolutionCase({
    id: "freight-damage",
    caseId: "CASE-203-26",
    title: "High-value freight damage",
    customer: "Olivia Martin",
    customerId: "C-203",
    account: "Premium · UK",
    request: "The television was cracked when the installers opened the box.",
    issue: "Freight damage",
    amount: 799,
    proposedAmount: 799,
    actionType: "replacement",
    companyCost: 486,
    customerValue: 799,
    customerGoal: "Receive an undamaged television with installation rescheduled.",
    businessGuardrail: "Supervisor assigns carrier recovery and safe disposal.",
    evidenceSources: [
      source("installer", "Installer report", "Damage documented before installation", [
        "Packaging retained",
      ]),
      source("carrier", "Freight telemetry", "Final-depot impact exceeded threshold", [
        "Pallet corner crushed",
      ]),
      source("quality", "Product quality", "Model defect rate normal", [
        "Transit pattern confirmed",
      ]),
      source("economics", "Economics", "Carrier recovery expected but exposure is high", [
        "Net company cost $486",
      ]),
    ],
    resolutionOptions: [
      {
        action: "replacement",
        customerValue: 799,
        companyCost: 486,
        label: "Replace and recover from carrier",
      },
      {
        action: "warranty_repair",
        customerValue: 650,
        companyCost: 320,
        label: "In-home panel replacement",
      },
    ],
    risk: "HIGH",
    decision: "HUMAN",
    taskType: "freight_damage_high_value",
    priority: "URGENT",
    queueStatus: "HIGH_VALUE_REVIEW",
  }),
  resolutionCase({
    id: "wrong-variant",
    caseId: "CASE-204-26",
    title: "Wrong color confirmed by barcode",
    customer: "Ethan Walker",
    customerId: "C-204",
    account: "Standard · US",
    request: "I ordered navy but received black. The box barcode says black.",
    issue: "Wrong variant",
    amount: 64,
    proposedAmount: 64,
    actionType: "exchange",
    companyCost: 12,
    customerValue: 64,
    customerGoal: "Receive the ordered color without paying shipping.",
    businessGuardrail: "Require order-line and packed-barcode mismatch.",
    evidenceSources: [
      source("order", "Order line", "Navy SKU ordered", ["SKU-BAG-NVY"]),
      source("warehouse", "Pick record", "Black SKU packed", [
        "SKU-BAG-BLK",
        "Station image matches",
      ]),
      source("photo", "Customer photo", "Box barcode confirms black variant", ["Metadata current"]),
      source("inventory", "Inventory", "Navy replacement in stock", ["Return label $12"]),
    ],
    resolutionOptions: [
      { action: "exchange", customerValue: 64, companyCost: 12, label: "Prepaid navy exchange" },
      {
        action: "partial_refund",
        customerValue: 30,
        companyCost: 18,
        label: "Keep black with an $18 adjustment",
      },
    ],
    risk: "LOW",
    decision: "AUTO",
    taskType: "wrong_variant_exchange",
    priority: "NORMAL",
    queueStatus: "EXCHANGE_READY",
  }),
  resolutionCase({
    id: "missing-part",
    caseId: "CASE-205-26",
    title: "Laptop bundle missing charger",
    customer: "Sophia Nguyen",
    customerId: "C-205",
    account: "Premium · AU",
    request: "The laptop is here, but the USB-C charger was missing.",
    issue: "Missing component",
    amount: 1299,
    proposedAmount: 49,
    actionType: "ship_missing_part",
    companyCost: 29,
    customerValue: 49,
    customerGoal: "Receive the charger without returning the laptop.",
    businessGuardrail: "Ship only the component proven missing by weight and bill of materials.",
    evidenceSources: [
      source("warehouse", "Pack station", "Outbound weight 310g below expected", [
        "Charger scan absent",
      ]),
      source("bom", "Bill of materials", "65W charger is included", ["SKU CHG-65W"]),
      source("history", "Customer history", "Twelve orders; no missing-part claims", [
        "Claim rate 0%",
      ]),
      source("inventory", "Parts inventory", "Charger available today", ["Landed cost $29"]),
    ],
    resolutionOptions: [
      {
        action: "ship_missing_part",
        customerValue: 49,
        companyCost: 29,
        label: "Ship charger only",
      },
      {
        action: "replacement",
        customerValue: 1299,
        companyCost: 910,
        label: "Replace entire bundle",
      },
    ],
    risk: "LOW",
    decision: "AUTO",
    taskType: "missing_component",
    priority: "HIGH",
    queueStatus: "PART_SHIPMENT_READY",
  }),
  resolutionCase({
    id: "late-delivery",
    caseId: "CASE-206-26",
    title: "Late gift, item still wanted",
    customer: "Marcus Reed",
    customerId: "C-206",
    account: "Standard · US",
    request: "The gift arrived four days late. I still want to keep it.",
    issue: "Late-delivery recovery",
    amount: 118,
    proposedAmount: 25,
    actionType: "store_credit",
    companyCost: 17,
    customerValue: 25,
    customerGoal: "Be recognized for the missed occasion while keeping the item.",
    businessGuardrail: "Compensate service failure without refunding kept merchandise.",
    evidenceSources: [
      source("promise", "Delivery promise", "Promised Aug 10; delivered Aug 14", [
        "Gift flag present",
      ]),
      source("carrier", "Carrier events", "Three-day depot miss plus one weather day", [
        "No customer delay",
      ]),
      source("history", "Customer history", "Five prior deliveries were on time", [
        "No prior credits",
      ]),
      source("economics", "Recovery policy", "Four-day miss maps to $25 credit", [
        "Expected cost $17",
      ]),
    ],
    resolutionOptions: [
      { action: "store_credit", customerValue: 25, companyCost: 17, label: "$25 apology credit" },
      {
        action: "partial_refund",
        customerValue: 18,
        companyCost: 18,
        label: "$18 payment-method refund",
      },
    ],
    risk: "LOW",
    decision: "AUTO",
    taskType: "late_delivery_recovery",
    priority: "NORMAL",
    queueStatus: "SERVICE_RECOVERY",
  }),
  resolutionCase({
    id: "safety",
    caseId: "CASE-207-26",
    title: "Smoke on first use",
    customer: "Priya Shah",
    customerId: "C-207",
    account: "Standard · IN",
    request: "The food processor smoked and tripped the breaker on first use.",
    issue: "Product safety incident",
    amount: 159,
    proposedAmount: 159,
    actionType: "safety_escalation",
    companyCost: 159,
    customerValue: 159,
    customerGoal: "Get safe instructions and a complete resolution.",
    businessGuardrail: "Never offer a keep-item discount for a potential safety defect.",
    evidenceSources: [
      source("media", "Incident evidence", "Video shows smoke from motor housing", [
        "Breaker trip",
        "No-use instruction sent",
      ]),
      source(
        "quality",
        "Safety signals",
        "Three similar batch incidents in 48 hours",
        ["Safety threshold exceeded"],
        "warning",
      ),
      source("serial", "Serial", "Device is linked to the order", ["Batch X2-44"]),
      source("history", "Customer history", "No prior safety claims", ["Seven orders"]),
    ],
    resolutionOptions: [
      {
        action: "safety_escalation",
        customerValue: 159,
        companyCost: 159,
        label: "Refund, pickup, no-use notice, batch review",
      },
    ],
    risk: "HIGH",
    decision: "HUMAN",
    taskType: "product_safety_incident",
    priority: "URGENT",
    queueStatus: "SAFETY_ESCALATION",
  }),
  resolutionCase({
    id: "theft-review",
    caseId: "CASE-208-26",
    title: "Repeat theft claim, conflicting proof",
    customer: "Gabriel Lopez",
    customerId: "C-208",
    account: "Standard · MX",
    request: "The delivery photo is not my porch. This is the second missing package this month.",
    issue: "Delivery theft review",
    amount: 130,
    proposedAmount: 130,
    actionType: "reship",
    companyCost: 78,
    customerValue: 130,
    customerGoal: "Receive the order fairly and securely.",
    businessGuardrail: "Claim frequency is context, not guilt; reconcile geo and photo evidence.",
    evidenceSources: [
      source(
        "carrier",
        "Delivery proof",
        "Photo mismatches facade; GPS 42m away",
        ["No signature"],
        "warning",
      ),
      source("history", "Claim history", "Two claims across 21 orders", [
        "Prior carrier-confirmed misdelivery",
      ]),
      source("address", "Address intelligence", "Multi-unit entrance has repeated exceptions", [
        "Safe drop disabled",
      ]),
      source("inventory", "Inventory", "Replacement available", ["Secure pickup supported"]),
    ],
    resolutionOptions: [
      { action: "reship", customerValue: 130, companyCost: 78, label: "Reship to secure pickup" },
      { action: "refund", customerValue: 130, companyCost: 130, label: "Refund after trace" },
    ],
    risk: "MEDIUM",
    decision: "HUMAN",
    taskType: "delivery_theft_review",
    priority: "HIGH",
    queueStatus: "CLAIM_REVIEW",
  }),
  resolutionCase({
    id: "worn-fit",
    caseId: "CASE-209-26",
    title: "Worn shoes, loyal customer",
    customer: "Natalie Kim",
    customerId: "C-209",
    account: "Premium · KR",
    request: "I wore the shoes twice, but they hurt. Can I return them for something else?",
    issue: "Fit dissatisfaction",
    amount: 110,
    proposedAmount: 110,
    actionType: "store_credit",
    companyCost: 38,
    customerValue: 110,
    customerGoal: "Move to a better fit without losing purchase value.",
    businessGuardrail: "Use loyalty, fit reviews, and resale recovery for worn-item exceptions.",
    evidenceSources: [
      source("history", "Customer history", "27 orders; lifetime value $4,920", [
        "Two returns",
        "No abuse",
      ]),
      source("reviews", "Product reviews", "22% report narrow fit", ["14.1% return rate"]),
      source("recovery", "Resale recovery", "Light wear qualifies for outlet", [
        "Expected recovery $72",
      ]),
      source("order", "Order", "Delivered seven days ago", ["Prior size match"]),
    ],
    resolutionOptions: [
      {
        action: "store_credit",
        customerValue: 110,
        companyCost: 38,
        label: "Full credit after inspected return",
      },
      { action: "deny", customerValue: 0, companyCost: 0, label: "Apply worn-item exclusion" },
    ],
    risk: "LOW",
    decision: "VERIFY",
    taskType: "fit_dissatisfaction",
    priority: "NORMAL",
    queueStatus: "FLEX_RETURN_REVIEW",
  }),
  resolutionCase({
    id: "serial-mismatch",
    caseId: "CASE-210-26",
    title: "Returned serial does not match",
    customer: "Jordan Ellis",
    customerId: "C-210",
    account: "Standard · US",
    request: "This phone is defective. I want the $699 refund today.",
    issue: "Serialized-item mismatch",
    amount: 699,
    proposedAmount: 0,
    actionType: "deny",
    companyCost: 0,
    customerValue: 0,
    customerGoal: "Receive a refund for the device presented.",
    businessGuardrail:
      "Do not refund a serialized item that cannot be linked to the order; offer appeal.",
    evidenceSources: [
      source("order", "Order serial", "Order serial PH-77-A91", ["$699"]),
      source("return", "Return scan", "Presented serial PH-12-Q44", ["IMEI also mismatches"]),
      source("activation", "Activation", "Presented device belongs to a different account", [
        "Order device remains active",
      ]),
      source("history", "Customer history", "No prior return issues", [
        "Identity still unresolved",
      ]),
    ],
    resolutionOptions: [
      {
        action: "deny",
        customerValue: 0,
        companyCost: 0,
        label: "Deny current refund; open evidence appeal",
      },
    ],
    risk: "HIGH",
    decision: "DENY",
    taskType: "serial_mismatch_return",
    priority: "URGENT",
    queueStatus: "IDENTITY_MISMATCH",
  }),
  resolutionCase({
    id: "empty-box",
    caseId: "CASE-211-26",
    title: "Empty box proven by weight chain",
    customer: "Hannah Moore",
    customerId: "C-211",
    account: "Standard · US",
    request: "The sealed box arrived without the camera inside.",
    issue: "Empty-box claim",
    amount: 140,
    proposedAmount: 140,
    actionType: "replacement",
    companyCost: 82,
    customerValue: 140,
    customerGoal: "Receive the missing camera quickly.",
    businessGuardrail: "Require weight-chain or pack-station proof.",
    evidenceSources: [
      source("warehouse", "Pack station", "0.39kg recorded versus 1.24kg expected", [
        "Weight gate failed open",
      ]),
      source("carrier", "Weight chain", "0.39kg through delivery", ["No tamper event"]),
      source("media", "Unboxing video", "Intact seal and empty insert", [
        "Metadata matches delivery",
      ]),
      source("history", "Customer history", "Eleven orders; no empty-box claims", [
        "No abuse flags",
      ]),
    ],
    resolutionOptions: [
      {
        action: "replacement",
        customerValue: 140,
        companyCost: 82,
        label: "Replace and investigate warehouse shrink",
      },
      {
        action: "refund",
        customerValue: 140,
        companyCost: 140,
        label: "Refund after preserving loss evidence",
      },
    ],
    risk: "LOW",
    decision: "AUTO",
    taskType: "empty_box_claim",
    priority: "HIGH",
    queueStatus: "REPLACEMENT_READY",
  }),
  resolutionCase({
    id: "counterfeit",
    caseId: "CASE-044-26",
    title: "Counterfeit signal affects other buyers",
    customer: "Maya Carter",
    customerId: "C-044",
    account: "Premium · US",
    request: "The authentication tag fails and stitching differs from the brand photos.",
    issue: "Marketplace authenticity",
    amount: 480,
    proposedAmount: 480,
    actionType: "seller_investigation",
    companyCost: 480,
    customerValue: 480,
    customerGoal: "Receive a refund and keep questionable stock out of circulation.",
    businessGuardrail:
      "Coordinate refund, evidence preservation, payout hold, and seller controls.",
    evidenceSources: [
      source("auth", "Authentication", "Tag signature invalid; serial unknown", [
        "Photo differences exceed threshold",
      ]),
      source(
        "seller",
        "Seller risk",
        "Seven authenticity complaints in 14 days",
        ["Complaint rate up 5.2×"],
        "warning",
      ),
      source("order", "Marketplace order", "Third-party seller LuxeLane-41", ["$480"]),
      source("history", "Customer history", "Sixteen orders; no authenticity claims", [
        "Premium account",
      ]),
    ],
    resolutionOptions: [
      {
        action: "seller_investigation",
        customerValue: 480,
        companyCost: 480,
        label: "Refund, preserve item, hold payout, investigate",
      },
      {
        action: "refund",
        customerValue: 440,
        companyCost: 480,
        label: "Refund without coordinated seller containment",
      },
    ],
    risk: "HIGH",
    decision: "HUMAN",
    taskType: "counterfeit_marketplace_claim",
    priority: "URGENT",
    queueStatus: "TRUST_AND_SAFETY",
  }),
  resolutionCase({
    id: "learning",
    caseId: "CASE-771-26",
    title: "Teach a fair warranty-grace rule",
    customer: "Elena Torres",
    customerId: "C-771",
    account: "Standard · US",
    request: "My headphones failed two days after warranty; this batch has a known battery issue.",
    issue: "Warranty grace exception",
    amount: 170,
    proposedAmount: 170,
    actionType: "warranty_repair",
    companyCost: 54,
    customerValue: 170,
    customerGoal: "Receive coverage for a documented known defect.",
    businessGuardrail: "Require a reviewer to teach the narrow exception before replay.",
    evidenceSources: [
      source("diagnostics", "Diagnostics", "Battery controller failure; no customer damage", [
        "Serial verified",
      ]),
      source("quality", "Service bulletin", "SB-H9-17 covers this batch", ["9.2% failure rate"]),
      source("warranty", "Warranty", "Expired two days ago", ["Inside proposed 14-day grace"]),
      source("economics", "Economics", "Repair $54 versus replacement $106", [
        "Restores $170 value",
      ]),
    ],
    resolutionOptions: [
      {
        action: "warranty_repair",
        customerValue: 170,
        companyCost: 54,
        label: "Honor repair under grace exception",
      },
      {
        action: "store_credit",
        customerValue: 40,
        companyCost: 29,
        label: "Generic goodwill credit",
      },
    ],
    risk: "MEDIUM",
    decision: "HUMAN",
    taskType: "warranty_grace_exception",
    priority: "NORMAL",
    queueStatus: "LEARNING_REVIEW",
    learned: {
      correction: "Approve the $170 warranty repair instead of a generic $40 credit.",
      lesson:
        "Within 14 days after warranty, repair a service-bulletin defect when diagnostics exclude customer damage.",
      nextCustomer: "Noah Bennett",
      nextCustomerId: "C-841",
      nextCaseId: "CASE-841-26",
      nextRequest:
        "My speaker battery failed three days after warranty and matches service bulletin SB-P6-08.",
      nextAmount: 130,
      nextProposedAmount: 130,
    },
  }),
  resolutionCase({
    id: "warranty-replay",
    caseId: "CASE-841-26",
    title: "Comparable grace case awaits replay",
    customer: "Noah Bennett",
    customerId: "C-841",
    account: "Standard · US",
    request: "My speaker battery failed three days after warranty and matches SB-P6-08.",
    issue: "Warranty correction replay",
    amount: 130,
    proposedAmount: 130,
    actionType: "warranty_repair",
    companyCost: 42,
    customerValue: 130,
    customerGoal: "Receive the same evidence-matched grace treatment.",
    businessGuardrail: "Replay only matching bulletin, diagnostics, and time window.",
    evidenceSources: [
      source("diagnostics", "Diagnostics", "Battery failure reproduced; no damage", [
        "Serial verified",
      ]),
      source("quality", "Service bulletin", "SB-P6-08 covers serial", ["7.4% failure rate"]),
      source("warranty", "Warranty", "Expired three days ago", ["Inside 14-day grace"]),
      source("economics", "Economics", "Repair $42 versus replacement $79", [
        "Restores $130 value",
      ]),
    ],
    resolutionOptions: [
      {
        action: "warranty_repair",
        customerValue: 130,
        companyCost: 42,
        label: "Replay verified repair exception",
      },
    ],
    risk: "MEDIUM",
    decision: "HUMAN",
    taskType: "warranty_grace_exception",
    priority: "NORMAL",
    queueStatus: "LEARNING_REPLAY",
  }),
  resolutionCase({
    id: "partial-shipment",
    caseId: "CASE-992-26",
    title: "One chair missing from four",
    customer: "Amir Hassan",
    customerId: "C-992",
    account: "Standard · AE",
    request: "Only three of four chairs arrived. I need the missing chair, not a full return.",
    issue: "Partial shipment",
    amount: 380,
    proposedAmount: 95,
    actionType: "reship",
    companyCost: 61,
    customerValue: 95,
    customerGoal: "Receive one matching chair.",
    businessGuardrail: "Resolve at missing-unit level after quantity and tracking proof.",
    evidenceSources: [
      source("order", "Order quantity", "Four chairs at $95 each", ["One coordinated set"]),
      source("warehouse", "Carton manifest", "Only three cartons closed", [
        "Fourth never inducted",
      ]),
      source("carrier", "Carrier scans", "Three cartons delivered", ["No fourth acceptance"]),
      source("inventory", "Inventory", "Matching lot available", ["One-chair cost $61"]),
    ],
    resolutionOptions: [
      { action: "reship", customerValue: 95, companyCost: 61, label: "Ship one matching chair" },
      { action: "refund", customerValue: 380, companyCost: 380, label: "Return full set" },
    ],
    risk: "LOW",
    decision: "AUTO",
    taskType: "partial_shipment",
    priority: "HIGH",
    queueStatus: "PART_SHIPMENT_READY",
  }),
  resolutionCase({
    id: "remote-fix",
    caseId: "CASE-212-26",
    title: "Telemetry proves a remote fix",
    customer: "Chloe Anderson",
    customerId: "C-212",
    account: "Standard · US",
    request: "The smart lock stopped responding two days after setup.",
    issue: "Guided product recovery",
    amount: 186,
    proposedAmount: 0,
    actionType: "guided_troubleshooting",
    companyCost: 4,
    customerValue: 186,
    customerGoal: "Restore the product now.",
    businessGuardrail: "Remote recovery only when hardware tests pass and no safety signal exists.",
    evidenceSources: [
      source("telemetry", "Device telemetry", "Hardware passes; pairing token expired", [
        "Battery 91%",
      ]),
      source("knowledge", "Recovery success", "Firmware 3.1.2 resolves 96%", [
        "Seven-minute average",
      ]),
      source("quality", "Product quality", "Hardware defect rate normal", ["No safety signals"]),
      source("order", "Order", "Delivered four days ago", ["Serial linked"]),
    ],
    resolutionOptions: [
      {
        action: "guided_troubleshooting",
        customerValue: 186,
        companyCost: 4,
        label: "Push firmware and re-pair",
      },
      {
        action: "replacement",
        customerValue: 186,
        companyCost: 109,
        label: "Replace before diagnosing",
      },
    ],
    risk: "LOW",
    decision: "AUTO",
    taskType: "guided_product_recovery",
    priority: "HIGH",
    queueStatus: "REMOTE_FIX_READY",
  }),
  resolutionCase({
    id: "repeat-claim",
    caseId: "CASE-213-26",
    title: "Frequent returns, genuine known defect",
    customer: "Daniel Brooks",
    customerId: "C-213",
    account: "Standard · US",
    request:
      "The backpack zipper split after three days. I know I return a lot, but this is broken.",
    issue: "Repeat claimant with current defect proof",
    amount: 85,
    proposedAmount: 25,
    actionType: "partial_refund",
    companyCost: 25,
    customerValue: 45,
    customerGoal: "Receive a fair remedy without being dismissed for prior returns.",
    businessGuardrail:
      "Return frequency raises review but never replaces current product evidence.",
    evidenceSources: [
      source(
        "history",
        "Return history",
        "Eight returns across ten orders",
        ["Six fit/style", "No chargebacks"],
        "warning",
      ),
      source("photo", "Defect inspection", "Factory-seam zipper failure", ["96.4% confidence"]),
      source("quality", "Product reviews", "7.9% zipper defect rate versus 1.6%", [
        "38 recent complaints",
      ]),
      source("economics", "Repair economics", "$20 local repair versus $67 return loss", [
        "Customer willing to keep",
      ]),
    ],
    resolutionOptions: [
      {
        action: "partial_refund",
        customerValue: 45,
        companyCost: 25,
        label: "$25 repair allowance; keep item",
      },
      {
        action: "replacement",
        customerValue: 85,
        companyCost: 58,
        label: "Replace from revised batch",
      },
    ],
    risk: "MEDIUM",
    decision: "VERIFY",
    taskType: "repeat_claim_known_defect",
    priority: "NORMAL",
    queueStatus: "BALANCED_REVIEW",
  }),
  resolutionCase({
    id: "enterprise-cost",
    caseId: "CASE-301-26",
    title: "Unexpected infrastructure bill after migration",
    customer: "Billing Operations Team",
    customerId: "E-301",
    account: "Enterprise · US",
    request:
      "Our monthly infrastructure estimate increased by $2,140 after a migration. Find the cause and stop avoidable spend without interrupting production.",
    issue: "Enterprise cost anomaly",
    amount: 2140,
    proposedAmount: 0,
    actionType: "cost_containment",
    companyCost: 12,
    customerValue: 480,
    customerGoal: "Stop provably avoidable spend without production impact.",
    businessGuardrail:
      "Require ownership approval, zero dependencies, sustained idle telemetry, and a recovery snapshot.",
    evidenceSources: [
      source("billing_export", "Billing ledger", "$480 avoidable spend isolated", [
        "Correlated resource IDs",
      ]),
      source("resource_inventory", "Resource inventory", "Legacy pool remains after migration", [
        "Non-production classification",
      ]),
      source("dependency_graph", "Dependency graph", "No production dependency exists", [
        "Requests, queues, databases checked",
      ]),
      source("utilization", "Telemetry", "Below 1% CPU and zero requests for 21 days", [
        "Continuous observation",
      ]),
      source("change_record", "Change management", "Approved plan retires the legacy pool", [
        "Owner acknowledged",
      ]),
    ],
    resolutionOptions: [
      {
        action: "cost_containment",
        customerValue: 480,
        companyCost: 12,
        label: "Snapshot, schedule shutdown, and monitor",
      },
      {
        action: "guided_troubleshooting",
        customerValue: 80,
        companyCost: 4,
        label: "Explain cost without stopping waste",
      },
    ],
    risk: "MEDIUM",
    decision: "VERIFY",
    taskType: "enterprise_billing_anomaly",
    contractType: "business_standard",
    priority: "HIGH",
    queueStatus: "OWNER_CONFIRMATION",
    customerSegment: "enterprise",
  }),
  resolutionCase({
    id: "enterprise-deploy",
    caseId: "CASE-302-26",
    title: "Production deployment failed health checks",
    customer: "Application Platform Team",
    customerId: "E-302",
    account: "Premium · US",
    request:
      "The new release is returning errors. Restore the last healthy version and prove recovery.",
    issue: "Failed production deployment",
    amount: 950,
    proposedAmount: 0,
    actionType: "rollback_deployment",
    companyCost: 18,
    customerValue: 950,
    customerGoal: "Restore the last healthy release and prove service recovery.",
    businessGuardrail:
      "Rollback only to a signed artifact with schema compatibility inside the tested window.",
    evidenceSources: [
      source("deployment", "Deployment controller", "Release 7.18.0 failed three health gates", [
        "Failure started after rollout",
      ]),
      source("previous_release", "Artifact registry", "Release 7.17.4 is signed and immutable", [
        "Previously healthy",
      ]),
      source("schema_compatibility", "Schema registry", "Rollback is backward compatible", [
        "No destructive migration",
      ]),
      source("service_health", "Service telemetry", "Errors began within two minutes", [
        "Baseline was healthy",
      ]),
      source("runbook", "Change policy", "Rollback is pre-authorized for 30 minutes", [
        "Recovery test current",
      ]),
    ],
    resolutionOptions: [
      {
        action: "rollback_deployment",
        customerValue: 950,
        companyCost: 18,
        label: "Restore signed release and verify health",
      },
      {
        action: "guided_troubleshooting",
        customerValue: 240,
        companyCost: 45,
        label: "Diagnose while errors continue",
      },
    ],
    risk: "LOW",
    decision: "AUTO",
    taskType: "enterprise_failed_deployment",
    contractType: "business_standard",
    priority: "URGENT",
    queueStatus: "RECOVERY_READY",
    customerSegment: "enterprise",
  }),
  resolutionCase({
    id: "enterprise-access",
    caseId: "CASE-303-26",
    title: "Service account denied after policy cleanup",
    customer: "Identity Administration Team",
    customerId: "E-303",
    account: "Enterprise · US",
    request: "A reporting job cannot read its approved dataset. Restore only the access it needs.",
    issue: "Least-privilege access recovery",
    amount: 420,
    proposedAmount: 0,
    actionType: "least_privilege_fix",
    companyCost: 9,
    customerValue: 420,
    customerGoal: "Restore the reporting job without broadening privilege.",
    businessGuardrail: "Apply only the exact simulated resource grant after owner confirmation.",
    evidenceSources: [
      source(
        "authorization_trace",
        "Authorization evaluator",
        "One required read permission was removed",
        ["Denied operation reproduced"],
      ),
      source("audit_log", "Audit log", "Job previously read only the approved dataset", [
        "No write activity",
      ]),
      source("identity_owner", "Identity registry", "Workload binding is current", [
        "Owner identified",
      ]),
      source("data_classification", "Data catalog", "Reporting purpose is allowed", [
        "Dataset scope exact",
      ]),
      source("policy_diff", "Policy simulator", "Single-resource read passes", [
        "Wildcard rejected",
      ]),
    ],
    resolutionOptions: [
      {
        action: "least_privilege_fix",
        customerValue: 420,
        companyCost: 9,
        label: "Apply exact read grant after confirmation",
      },
      { action: "deny", customerValue: 0, companyCost: 0, label: "Leave reporting unavailable" },
    ],
    risk: "MEDIUM",
    decision: "VERIFY",
    taskType: "enterprise_access_denied",
    contractType: "business_standard",
    priority: "HIGH",
    queueStatus: "OWNER_CONFIRMATION",
    customerSegment: "enterprise",
  }),
  resolutionCase({
    id: "enterprise-database",
    caseId: "CASE-304-26",
    title: "Database latency from exhausted read capacity",
    customer: "Data Services Team",
    customerId: "E-304",
    account: "Premium · US",
    request: "Checkout reads are timing out. Recover capacity without a destructive schema change.",
    issue: "Database capacity recovery",
    amount: 780,
    proposedAmount: 0,
    actionType: "database_capacity_recovery",
    companyCost: 64,
    customerValue: 780,
    customerGoal: "Recover read latency with a bounded reversible change.",
    businessGuardrail:
      "Exclude locks and regressions, cap cost, and expire temporary capacity automatically.",
    evidenceSources: [
      source("database_metrics", "Database telemetry", "Read capacity saturated at 98%", [
        "Latency threshold breached",
      ]),
      source("query_analysis", "Query analyzer", "Query plans unchanged", ["No new hot query"]),
      source("lock_analysis", "Transaction diagnostics", "No lock chain or deadlock surge", [
        "Concurrency normal",
      ]),
      source("change_history", "Change history", "No incident-window configuration change", [
        "Schema stable",
      ]),
      source("capacity_plan", "Capacity controller", "One replica restores 45% headroom", [
        "24-hour expiry",
      ]),
    ],
    resolutionOptions: [
      {
        action: "database_capacity_recovery",
        customerValue: 780,
        companyCost: 64,
        label: "Add temporary replica and verify latency",
      },
      {
        action: "guided_troubleshooting",
        customerValue: 160,
        companyCost: 20,
        label: "Continue diagnosis while timeouts persist",
      },
    ],
    risk: "LOW",
    decision: "AUTO",
    taskType: "enterprise_database_latency",
    contractType: "business_standard",
    priority: "URGENT",
    queueStatus: "CAPACITY_RECOVERY",
    customerSegment: "enterprise",
  }),
  resolutionCase({
    id: "enterprise-api",
    caseId: "CASE-305-26",
    title: "Retry storm amplifying API throttling",
    customer: "API Reliability Team",
    customerId: "E-305",
    account: "Premium · US",
    request:
      "Clients are retrying too aggressively. Stabilize traffic without losing accepted requests.",
    issue: "API retry amplification",
    amount: 360,
    proposedAmount: 0,
    actionType: "traffic_stabilization",
    companyCost: 8,
    customerValue: 360,
    customerGoal: "Restore completion rate while preserving idempotent requests.",
    businessGuardrail:
      "Require trace-confirmed amplification, successful load simulation, and rollback thresholds.",
    evidenceSources: [
      source("request_metrics", "API telemetry", "Retries rose 640% while base traffic rose 8%", [
        "Throttling correlated",
      ]),
      source("client_trace", "Distributed trace", "Three clients retry without jitter", [
        "Request IDs preserved",
      ]),
      source("capacity", "Capacity service", "Normal traffic fits healthy capacity", [
        "No quota deficit",
      ]),
      source(
        "load_simulation",
        "Traffic simulator",
        "Backoff plus jitter restores 99.4% completion",
        ["No accepted request lost"],
      ),
      source("runbook", "Reliability runbook", "Retry mitigation is pre-authorized", [
        "Rollback threshold defined",
      ]),
    ],
    resolutionOptions: [
      {
        action: "traffic_stabilization",
        customerValue: 360,
        companyCost: 8,
        label: "Apply jitter, backoff, and queue protection",
      },
      {
        action: "quota_adjustment",
        customerValue: 120,
        companyCost: 95,
        label: "Increase quota without stopping retries",
      },
    ],
    risk: "LOW",
    decision: "AUTO",
    taskType: "enterprise_api_throttling",
    contractType: "business_standard",
    priority: "URGENT",
    queueStatus: "MITIGATION_READY",
    customerSegment: "enterprise",
  }),
  resolutionCase({
    id: "enterprise-security",
    caseId: "CASE-306-26",
    title: "Credential used from impossible travel locations",
    customer: "Security Operations Team",
    customerId: "E-306",
    account: "Enterprise · US",
    request:
      "A privileged credential appears compromised. Contain access and preserve evidence immediately.",
    issue: "Privileged credential compromise",
    amount: 5000,
    proposedAmount: 0,
    actionType: "security_containment",
    companyCost: 85,
    customerValue: 5000,
    customerGoal: "Contain the credential while preserving forensic evidence and continuity.",
    businessGuardrail:
      "Keep privileged containment human-owned; prebuild only the scoped verified plan.",
    evidenceSources: [
      source("identity_events", "Identity telemetry", "8,100 km travel in 14 minutes", [
        "Same credential",
      ]),
      source("audit_log", "Security audit log", "Second session enumerated secrets", [
        "Immutable trail",
      ]),
      source("asset_scope", "Asset inventory", "Credential administers three services", [
        "Blast radius known",
      ]),
      source("forensic_snapshot", "Forensic service", "Session evidence preserved immutably", [
        "Chain of custody recorded",
      ]),
      source("response_plan", "Incident response", "Scoped revoke and rotation validated", [
        "Continuity owner required",
      ]),
    ],
    resolutionOptions: [
      {
        action: "security_containment",
        customerValue: 5000,
        companyCost: 85,
        label: "Approve revoke, rotate, isolate, and notify",
      },
    ],
    risk: "HIGH",
    decision: "HUMAN",
    taskType: "enterprise_credential_compromise",
    contractType: "custom_sla",
    priority: "URGENT",
    queueStatus: "INCIDENT_COMMANDER",
    customerSegment: "enterprise",
  }),
  resolutionCase({
    id: "enterprise-restore",
    caseId: "CASE-307-26",
    title: "Restore after accidental dataset deletion",
    customer: "Business Continuity Team",
    customerId: "E-307",
    account: "Enterprise · US",
    request:
      "A dataset was deleted. Restore the latest valid point without overwriting production.",
    issue: "Isolated data recovery",
    amount: 3500,
    proposedAmount: 0,
    actionType: "isolated_restore",
    companyCost: 140,
    customerValue: 3500,
    customerGoal: "Recover verified data without overwriting current production state.",
    businessGuardrail:
      "Restore only into isolation and require the accountable owner to approve promotion.",
    evidenceSources: [
      source("deletion_audit", "Audit log", "Dataset deleted at 17:42 UTC", [
        "Operator command identified",
      ]),
      source("backup_catalog", "Backup catalog", "17:30 recovery point is complete and immutable", [
        "Checksum valid",
      ]),
      source("dependency_graph", "Data lineage", "Four reports depend on the dataset", [
        "Consumers identified",
      ]),
      source("restore_simulation", "Recovery verifier", "Row, schema, and relation checks pass", [
        "Isolated target",
      ]),
      source("ownership", "Data ownership", "Accountable owner is available", [
        "Promotion approval required",
      ]),
    ],
    resolutionOptions: [
      {
        action: "isolated_restore",
        customerValue: 3500,
        companyCost: 140,
        label: "Restore in isolation, validate, request promotion",
      },
    ],
    risk: "HIGH",
    decision: "HUMAN",
    taskType: "enterprise_backup_restore",
    contractType: "custom_sla",
    priority: "URGENT",
    queueStatus: "OWNER_APPROVAL",
    customerSegment: "enterprise",
  }),
  resolutionCase({
    id: "enterprise-quota",
    caseId: "CASE-308-26",
    title: "Regional quota blocks an approved launch",
    customer: "Capacity Planning Team",
    customerId: "E-308",
    account: "Enterprise · US",
    request: "An approved launch needs temporary quota. Validate capacity, cost, and abuse risk.",
    issue: "Bounded quota adjustment",
    amount: 1200,
    proposedAmount: 0,
    actionType: "quota_adjustment",
    companyCost: 35,
    customerValue: 1200,
    customerGoal: "Enable the approved launch with a cost-capped temporary quota.",
    businessGuardrail:
      "Calculate from demand, verify posture, alert budget, and expire after launch.",
    evidenceSources: [
      source("launch_plan", "Change management", "Launch approved for 72 hours", ["Owner signed"]),
      source("usage_history", "Capacity telemetry", "Sustained use is 480 units", [
        "Demand profile predictable",
      ]),
      source("quota_model", "Quota calculator", "820 covers peak plus 10% headroom", [
        "Current quota 600",
      ]),
      source("budget", "Budget control", "Incremental cost capped at $35", ["Alerts configured"]),
      source("risk", "Abuse prevention", "Account and workload posture verified", [
        "No active abuse signal",
      ]),
    ],
    resolutionOptions: [
      {
        action: "quota_adjustment",
        customerValue: 1200,
        companyCost: 35,
        label: "Request temporary quota with expiry",
      },
      { action: "deny", customerValue: 0, companyCost: 0, label: "Block the approved launch" },
    ],
    risk: "MEDIUM",
    decision: "VERIFY",
    taskType: "enterprise_quota_request",
    contractType: "business_standard",
    priority: "HIGH",
    queueStatus: "CAPACITY_APPROVAL",
    customerSegment: "enterprise",
  }),
];

export const traceSteps = [
  {
    name: "Customer + order context",
    tool: "customer-context",
    latency: "18 ms",
    detail: "Orders, claim history, loyalty, and contracts",
  },
  {
    name: "Issue evidence",
    tool: "case-evidence",
    latency: "24 ms",
    detail: "Scenario-specific source checklist and blockers",
  },
  {
    name: "Experience retrieval",
    tool: "experience-memory",
    latency: "31 ms",
    detail: "Exact SQL + distributed vector search",
  },
  {
    name: "Resolution proposal",
    tool: "Amazon Bedrock",
    latency: "412 ms",
    detail: "Customer value and bounded company cost",
  },
  {
    name: "Permission gate",
    tool: "policy-risk",
    latency: "<1 ms",
    detail: "Deterministic AUTO / VERIFY / HUMAN / DENY",
  },
  {
    name: "Outcome record",
    tool: "outcome-learning",
    latency: "21 ms",
    detail: "Independent verification + atomic episode write",
  },
];
