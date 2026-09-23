import type {
  ActionRequest,
  DashboardCase,
  EvidenceRequestResponse,
  EvidenceSubmission,
  InvestigationCase,
  InvestigationStartRequest,
  InvestigationStartResponse,
  Recommendation,
} from '@/types';
import {
  mockAddEvidence,
  mockGetCase,
  mockGetDashboardCases,
  mockGetInvestigation,
  mockGetRecommendation,
  mockRequestEvidence,
  mockStartInvestigation,
  mockTakeAction,
} from './mockApi';

const useMock = process.env.NEXT_PUBLIC_USE_MOCK_API !== 'false';
const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? 'http://localhost:8000';

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${baseUrl}${path}`, { ...init, headers: { 'Content-Type': 'application/json', ...(init?.headers ?? {}) } });
  if (!response.ok) throw new Error(`API_${response.status}`);
  return response.json() as Promise<T>;
}

export const api = {
  startInvestigation: (payload: InvestigationStartRequest): Promise<InvestigationStartResponse> => useMock ? mockStartInvestigation(payload) : request('/api/investigations', { method: 'POST', body: JSON.stringify(payload) }),
  getCase: (caseId: string): Promise<InvestigationCase> => useMock ? mockGetCase(caseId) : request(`/api/cases/${caseId}`),
  getInvestigation: (caseId: string): Promise<InvestigationCase> => useMock ? mockGetInvestigation(caseId) : request(`/api/cases/${caseId}/investigation`),
  requestEvidence: (caseId: string): Promise<EvidenceRequestResponse> => useMock ? mockRequestEvidence(caseId) : request(`/api/cases/${caseId}/evidence-request`, { method: 'POST', body: JSON.stringify({ evidence_type: 'CUSTOMER_TRANSACTION_CONFIRMATION' }) }),
  addEvidence: (caseId: string, payload: EvidenceSubmission): Promise<InvestigationCase> => useMock ? mockAddEvidence(caseId, payload) : request(`/api/cases/${caseId}/evidence`, { method: 'POST', body: JSON.stringify(payload) }),
  getRecommendation: (caseId: string): Promise<Recommendation> => useMock ? mockGetRecommendation(caseId) : request(`/api/cases/${caseId}/recommendation`),
  takeAction: (caseId: string, payload: ActionRequest): Promise<InvestigationCase> => useMock ? mockTakeAction(caseId, payload) : request(`/api/cases/${caseId}/action`, { method: 'POST', body: JSON.stringify(payload) }),
  // The shared contract has no list-cases endpoint; real mode stays within the documented case route.
  getDashboardCases: (): Promise<DashboardCase[]> => useMock ? mockGetDashboardCases() : request<InvestigationCase>('/api/cases/CASE-1024').then((item) => [{ case_id: item.case_id, transaction_id: item.transaction_id, customer_id: item.customer_id, amount: item.amount, risk_score: item.risk_score, confidence: item.confidence, status: item.status, updated_at: item.updated_at }]),
};
