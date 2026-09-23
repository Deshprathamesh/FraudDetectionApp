import type { CaseStatus } from '@/types';

const styles: Record<CaseStatus, string> = {
  TRIGGERED: 'bg-slate-100 text-slate-600',
  INVESTIGATING: 'bg-blue-50 text-blue-700',
  GATHERING_EVIDENCE: 'bg-amber-50 text-amber-700',
  ASSESSING: 'bg-violet-50 text-violet-700',
  WAITING_FOR_EVIDENCE: 'bg-amber-50 text-amber-700',
  ACTION_READY: 'bg-orange-50 text-orange-700',
  AWAITING_APPROVAL: 'bg-red-50 text-red-700',
  EXECUTING: 'bg-blue-50 text-blue-700',
  RESOLVED: 'bg-emerald-50 text-emerald-700',
  ESCALATED: 'bg-red-50 text-red-700',
};

export function StatusBadge({ status }: { status: CaseStatus }) {
  return <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[10px] font-bold tracking-[0.05em] ${styles[status]}`}><span className="h-1.5 w-1.5 rounded-full bg-current opacity-70" />{status.replaceAll('_', ' ')}</span>;
}
