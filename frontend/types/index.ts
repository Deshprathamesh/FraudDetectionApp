export const CASE_STATUSES = [
  'TRIGGERED',
  'INVESTIGATING',
  'GATHERING_EVIDENCE',
  'ASSESSING',
  'WAITING_FOR_EVIDENCE',
  'ACTION_READY',
  'AWAITING_APPROVAL',
  'EXECUTING',
  'RESOLVED',
  'ESCALATED',
] as const;

export type CaseStatus = (typeof CASE_STATUSES)[number];
export type TriggerType = 'HIGH_RISK' | 'CUSTOMER_REPORT' | 'ANALYST_REQUEST';
export type Actor = 'Agent' | 'TigerGraph' | 'Analyst' | 'Customer' | 'System';

export interface GraphEntity {
  id: string;
  type: 'Customer' | 'Account' | 'Transaction' | 'Device' | 'Merchant' | 'IP' | 'Case';
  label: string;
  subtitle?: string;
  risk_score?: number;
  flagged?: boolean;
}

export interface GraphRelationship {
  id: string;
  source: string;
  target: string;
  label: string;
  suspicious?: boolean;
}

export interface Evidence {
  evidence_id: string;
  type: string;
  source: string;
  summary: string;
  confidence: number;
  timestamp: string;
  related_entities: string[];
}

export interface FraudPattern {
  pattern_id: string;
  name: string;
  description: string;
  evidence_refs: string[];
  confidence: number;
  indicators: string[];
}

export interface Recommendation {
  action: string;
  reason: string;
  confidence: number;
  approval_required: boolean;
  policy_basis: string;
}

export interface TimelineEvent {
  event_id: string;
  timestamp: string;
  type: string;
  summary: string;
  actor: Actor;
  related_ids: string[];
}

export interface MissingEvidence {
  evidence_id: string;
  title: string;
  reason: string;
  action: string;
}

export interface InvestigationCase {
  case_id: string;
  transaction_id: string;
  customer_id: string;
  status: CaseStatus;
  risk_score: number;
  confidence: number;
  fraud_patterns: FraudPattern[];
  evidence: Evidence[];
  recommendation: Recommendation;
  approval_required: boolean;
  timeline: TimelineEvent[];
  amount: number;
  currency: string;
  created_at: string;
  updated_at: string;
  transaction_summary: string;
  graph_entities: GraphEntity[];
  graph_relationships: GraphRelationship[];
  missing_evidence: MissingEvidence[];
  customer_response?: string;
  case_memory?: string;
}

export interface InvestigationStartRequest {
  transaction_id: string;
  trigger: TriggerType;
}

export interface InvestigationStartResponse {
  case_id: string;
  status: CaseStatus;
  risk_score: number;
}

export interface EvidenceRequestResponse {
  case_id: string;
  status: CaseStatus;
  requested: MissingEvidence[];
}

export interface EvidenceSubmission {
  type: string;
  source: string;
  summary: string;
  related_entities: string[];
}

export interface ActionRequest {
  action: string;
  approved: boolean;
}

export interface DashboardCase {
  case_id: string;
  transaction_id: string;
  customer_id: string;
  amount: number;
  risk_score: number;
  confidence: number;
  status: CaseStatus;
  updated_at: string;
}
