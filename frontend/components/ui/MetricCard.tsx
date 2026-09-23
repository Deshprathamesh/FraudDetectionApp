import { ArrowDownRight, ArrowUpRight, LucideIcon } from 'lucide-react';

export function MetricCard({ label, value, detail, tone = 'blue', trend, icon: Icon }: { label: string; value: string; detail: string; tone?: 'blue' | 'red' | 'amber' | 'green'; trend?: string; icon: LucideIcon }) {
  const tones = { blue: 'bg-blue-50 text-blue-600', red: 'bg-red-50 text-red-600', amber: 'bg-amber-50 text-amber-600', green: 'bg-emerald-50 text-emerald-600' };
  return <div className="panel flex min-h-[126px] flex-col justify-between p-5"><div className="flex items-start justify-between"><div><div className="label mb-2">{label}</div><div className="text-[28px] font-bold tracking-[-0.05em] text-slate-800">{value}</div></div><div className={`flex h-9 w-9 items-center justify-center rounded-xl ${tones[tone]}`}><Icon size={17} /></div></div><div className="flex items-center justify-between text-xs"><span className="text-slate-400">{detail}</span>{trend && <span className={`flex items-center gap-0.5 font-semibold ${tone === 'red' ? 'text-red-500' : 'text-emerald-600'}`}>{tone === 'red' ? <ArrowUpRight size={13} /> : <ArrowDownRight size={13} />}{trend}</span>}</div></div>;
}
