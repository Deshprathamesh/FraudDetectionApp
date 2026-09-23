import type {
  ActionRequest,
  DashboardCase,
  EvidenceRequestResponse,
  EvidenceSubmission,
  InvestigationCase,
  InvestigationStartRequest,
  InvestigationStartResponse,
} from '@/types';

const now = new Date('2026-09-23T18:30:00.000Z');
const iso = (minutes: number) => new Date(now.getTime() + minutes * 60_000).toISOString();

const demoCase: InvestigationCase = {
  case_id: 'CASE-1024',
  transaction_id: 'TXN-104829',
  customer_id: 'C-45821',
  status: 'INVESTIGATING',
  risk_score: 0.87,
  confidence: 0.58,
  amount: 8420,
  currency: 'USD',
  created_at: iso(-42),
  updated_at: iso(-2),
  transaction_summary: 'High-value card-not-present transaction to a new beneficiary.',
  approval_required: false,
  fraud_patterns: [
    {
      pattern_id: 'PAT-ATO-01',
      name: 'Suspected Account Takeover',
      description: 'A new beneficiary and unusual activity are connected to a device shared by multiple accounts.',
      evidence_refs: ['EV-001', 'EV-002', 'EV-004'],
      confidence: 0.76,
      indicators: ['Shared device across 4 accounts', 'New beneficiary', 'Unusual transaction behavior'],
    },
  ],
  evidence: [
    {
      evidence_id: 'EV-001',
      type: 'DEVICE_NETWORK',
      source: 'TigerGraph · shared-device traversal',
      summary: 'Device D-421 is linked to 4 customer accounts with overlapping transaction activity.',
      confidence: 0.93,
      timestamp: iso(-28),
      related_entities: ['D-421', 'C-45821', 'A-7712'],
    },
    {
      evidence_id: 'EV-002',
      type: 'TRANSACTION_BEHAVIOR',
      source: 'Transaction history',
      summary: 'The amount is 6.4× above the customer baseline and falls outside the usual merchant pattern.',
      confidence: 0.81,
      timestamp: iso(-24),
      related_entities: ['TXN-104829', 'C-45821', 'M-908'],
    },
    {
      evidence_id: 'EV-003',
      type: 'BENEFICIARY_CHANGE',
      source: 'Account activity ledger',
      summary: 'Beneficiary M-908 was first seen 11 minutes before the high-value transaction.',
      confidence: 0.88,
      timestamp: iso(-19),
      related_entities: ['A-7712', 'M-908', 'TXN-104829'],
    },
    {
      evidence_id: 'EV-004',
      type: 'CASE_MEMORY',
      source: 'Similar resolved cases',
      summary: 'Two resolved cases share the same device and new-beneficiary sequence.',
      confidence: 0.71,
      timestamp: iso(-12),
      related_entities: ['D-421', 'CASE-0987', 'CASE-1002'],
    },
  ],
  recommendation: {
    action: 'REQUEST_STEP_UP_AUTH',
    reason: 'Risk is high, but customer intent is not yet verified. Request controlled confirmation before restricting the account.',
    confidence: 0.58,
    approval_required: false,
    policy_basis: 'POL-FRD-07 · Step-up verification for high-risk new-beneficiary activity',
  },
  missing_evidence: [
    {
      evidence_id: 'REQ-001',
      title: 'Customer Transaction Confirmation',
      reason: 'Customer intent is the highest-value unresolved signal in the current assessment.',
      action: 'REQUEST_CUSTOMER_VERIFICATION',
    },
    {
      evidence_id: 'REQ-002',
      title: 'Device Ownership Verification',
      reason: 'Ownership of D-421 is not established for the current customer session.',
      action: 'REQUEST_DEVICE_VERIFICATION',
    },
  ],
  graph_entities: [
    { id: 'C-45821', type: 'Customer', label: 'C-45821', subtitle: 'Customer · 3 active accounts', risk_score: 0.62 },
    { id: 'A-7712', type: 'Account', label: 'A-7712', subtitle: 'Primary account · USD', risk_score: 0.74 },
    { id: 'TXN-104829', type: 'Transaction', label: 'TXN-104829', subtitle: '$8,420 · new beneficiary', risk_score: 0.87, flagged: true },
    { id: 'D-421', type: 'Device', label: 'D-421', subtitle: 'Shared by 4 accounts', risk_score: 0.81, flagged: true },
    { id: 'M-908', type: 'Merchant', label: 'M-908', subtitle: 'New beneficiary', risk_score: 0.77, flagged: true },
    { id: 'IP-771', type: 'IP', label: 'IP-771', subtitle: 'Unseen network', risk_score: 0.69 },
    { id: 'CASE-1024', type: 'Case', label: 'CASE-1024', subtitle: 'Active investigation', risk_score: 0.87, flagged: true },
  ],
  graph_relationships: [
    { id: 'e1', source: 'C-45821', target: 'A-7712', label: 'owns' },
    { id: 'e2', source: 'A-7712', target: 'TXN-104829', label: 'initiated' },
    { id: 'e3', source: 'TXN-104829', target: 'M-908', label: 'paid_to', suspicious: true },
    { id: 'e4', source: 'TXN-104829', target: 'D-421', label: 'originated_on', suspicious: true },
    { id: 'e5', source: 'D-421', target: 'IP-771', label: 'used_with' },
    { id: 'e6', source: 'D-421', target: 'CASE-1024', label: 'linked_to', suspicious: true },
    { id: 'e7', source: 'C-45821', target: 'CASE-1024', label: 'subject_of' },
  ],
  timeline: [
    { event_id: 'TL-001', timestamp: iso(-42), type: 'Investigation triggered', summary: 'High-risk signal created an investigation for TXN-104829.', actor: 'Agent', related_ids: ['TXN-104829'] },
    { event_id: 'TL-002', timestamp: iso(-40), type: 'Transaction retrieved', summary: 'Transaction, customer and account context loaded.', actor: 'System', related_ids: ['TXN-104829', 'C-45821'] },
    { event_id: 'TL-003', timestamp: iso(-35), type: 'Graph traversal completed', summary: 'Connected devices, accounts and beneficiary relationships returned.', actor: 'TigerGraph', related_ids: ['D-421', 'A-7712', 'M-908'] },
    { event_id: 'TL-004', timestamp: iso(-28), type: 'Shared device detected', summary: 'D-421 is shared across four linked accounts.', actor: 'TigerGraph', related_ids: ['D-421'] },
    { event_id: 'TL-005', timestamp: iso(-19), type: 'Fraud pattern identified', summary: 'Possible Account Takeover identified with 76% pattern confidence.', actor: 'Agent', related_ids: ['PAT-ATO-01'] },
    { event_id: 'TL-006', timestamp: iso(-12), type: 'Action recommended', summary: 'Step-up authentication recommended while customer intent remains unresolved.', actor: 'Agent', related_ids: ['TXN-104829'] },
  ],
};

let currentCase: InvestigationCase = structuredClone(demoCase);

const clone = <T,>(value: T): T => structuredClone(value);

export async function mockStartInvestigation(request: InvestigationStartRequest): Promise<InvestigationStartResponse> {
  await delay(650);
  currentCase = clone(demoCase);
  currentCase.transaction_id = request.transaction_id;
  currentCase.status = 'INVESTIGATING';
  return { case_id: currentCase.case_id, status: currentCase.status, risk_score: currentCase.risk_score };
}

export async function mockGetCase(caseId: string): Promise<InvestigationCase> {
  await delay(220);
  if (caseId !== currentCase.case_id) throw new Error('CASE_NOT_FOUND');
  return clone(currentCase);
}

export async function mockGetInvestigation(caseId: string): Promise<InvestigationCase> {
  return mockGetCase(caseId);
}

export async function mockRequestEvidence(caseId: string): Promise<EvidenceRequestResponse> {
  await delay(550);
  currentCase.status = 'WAITING_FOR_EVIDENCE';
  currentCase.updated_at = iso(2);
  currentCase.timeline.push({ event_id: `TL-${currentCase.timeline.length + 1}`, timestamp: iso(2), type: 'Verification requested', summary: 'Customer confirmation and device ownership verification requested under policy.', actor: 'Agent', related_ids: ['REQ-001', 'REQ-002'] });
  return { case_id: caseId, status: currentCase.status, requested: clone(currentCase.missing_evidence) };
}

export async function mockAddEvidence(caseId: string, submission: EvidenceSubmission): Promise<InvestigationCase> {
  await delay(600);
  currentCase.status = 'ASSESSING';
  currentCase.customer_response = submission.summary;
  currentCase.evidence.push({ evidence_id: 'EV-005', type: submission.type, source: submission.source, summary: submission.summary, confidence: 0.99, timestamp: iso(5), related_entities: submission.related_entities });
  currentCase.confidence = 0.96;
  currentCase.recommendation = { action: 'BLOCK_TRANSACTION · FREEZE_ACCOUNT', reason: 'Customer denied the transaction. Combined with the shared-device and beneficiary signals, the evidence supports immediate protective action.', confidence: 0.96, approval_required: true, policy_basis: 'POL-FRD-12 · Confirmed unauthorized transaction with high-risk connected entities' };
  currentCase.approval_required = true;
  currentCase.status = 'ACTION_READY';
  currentCase.missing_evidence = [];
  currentCase.updated_at = iso(5);
  currentCase.timeline.push(
    { event_id: `TL-${currentCase.timeline.length + 1}`, timestamp: iso(4), type: 'Customer response received', summary: 'Customer stated: “I did not recognize this transaction.”', actor: 'Customer', related_ids: ['EV-005', 'TXN-104829'] },
    { event_id: `TL-${currentCase.timeline.length + 2}`, timestamp: iso(5), type: 'Risk updated', summary: 'Confidence increased from 58% to 96% after customer denial.', actor: 'Agent', related_ids: ['EV-005'] },
    { event_id: `TL-${currentCase.timeline.length + 3}`, timestamp: iso(5), type: 'Action recommended', summary: 'Block transaction and freeze account; analyst approval is required.', actor: 'Agent', related_ids: ['TXN-104829', 'A-7712'] },
  );
  return clone(currentCase);
}

export async function mockGetRecommendation(caseId: string): Promise<InvestigationCase['recommendation']> {
  const item = await mockGetCase(caseId);
  return clone(item.recommendation);
}

export async function mockTakeAction(caseId: string, request: ActionRequest): Promise<InvestigationCase> {
  await delay(800);
  if (!request.approved) throw new Error('APPROVAL_REQUIRED');
  currentCase.status = 'RESOLVED';
  currentCase.approval_required = false;
  currentCase.updated_at = iso(8);
  currentCase.timeline.push(
    { event_id: `TL-${currentCase.timeline.length + 1}`, timestamp: iso(6), type: 'Analyst approved', summary: 'Analyst approved protective action after reviewing policy and supporting evidence.', actor: 'Analyst', related_ids: ['EV-001', 'EV-005'] },
    { event_id: `TL-${currentCase.timeline.length + 2}`, timestamp: iso(7), type: 'Action executed', summary: 'Transaction blocked and account freeze simulated successfully.', actor: 'System', related_ids: ['TXN-104829', 'A-7712'] },
    { event_id: `TL-${currentCase.timeline.length + 3}`, timestamp: iso(8), type: 'Case memory updated', summary: 'Outcome stored for future investigations involving shared device D-421.', actor: 'System', related_ids: ['CASE-1024', 'D-421'] },
  );
  currentCase.case_memory = 'Resolved pattern stored: shared device + new beneficiary + customer denial → protective action.';
  return clone(currentCase);
}

export async function mockGetDashboardCases(): Promise<DashboardCase[]> {
  await delay(180);
  return [
    { case_id: 'CASE-1024', transaction_id: 'TXN-104829', customer_id: 'C-45821', amount: 8420, risk_score: currentCase.risk_score, confidence: currentCase.confidence, status: currentCase.status, updated_at: currentCase.updated_at },
    { case_id: 'CASE-1021', transaction_id: 'TXN-104811', customer_id: 'C-71904', amount: 1290, risk_score: 0.73, confidence: 0.82, status: 'AWAITING_APPROVAL', updated_at: iso(-54) },
    { case_id: 'CASE-1018', transaction_id: 'TXN-104765', customer_id: 'C-11208', amount: 548, risk_score: 0.61, confidence: 0.91, status: 'RESOLVED', updated_at: iso(-112) },
    { case_id: 'CASE-1014', transaction_id: 'TXN-104702', customer_id: 'C-22087', amount: 18900, risk_score: 0.92, confidence: 0.68, status: 'GATHERING_EVIDENCE', updated_at: iso(-140) },
  ];
}

function delay(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}
