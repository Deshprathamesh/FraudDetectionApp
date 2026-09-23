'use client';

import { Bell, ChevronDown, CircleHelp, Search, ShieldCheck } from 'lucide-react';
import { usePathname } from 'next/navigation';

export function Topbar() {
  const pathname = usePathname();
  const isCase = pathname?.startsWith('/cases/') ?? false;
  return <header className="flex h-[68px] items-center justify-between border-b border-slate-200/80 bg-white/85 px-8 backdrop-blur">
    <div className="flex items-center gap-3 text-sm"><span className="font-semibold text-slate-700">{isCase ? 'Investigation workspace' : pathname === '/investigate' ? 'Start investigation' : 'Operations overview'}</span><span className="text-slate-300">/</span><span className="text-slate-400">{isCase ? 'CASE-1024' : 'FraudGraph AI'}</span></div>
    <div className="flex items-center gap-5"><div className="relative hidden w-64 md:block"><Search size={15} className="absolute left-3 top-2.5 text-slate-400" /><input className="h-9 w-full rounded-lg border border-slate-200 bg-slate-50 pl-9 pr-3 text-xs outline-none transition focus:border-blue-300 focus:bg-white" placeholder="Search cases, transactions…" /></div><div className="flex items-center gap-2 text-[11px] font-semibold text-slate-500"><span className="h-2 w-2 rounded-full bg-emerald-500 shadow-[0_0_0_3px_rgba(16,185,129,.12)]" />Mock API active</div><CircleHelp size={17} className="text-slate-400" /><Bell size={17} className="text-slate-400" /><div className="flex items-center gap-2 border-l border-slate-200 pl-5"><div className="flex h-8 w-8 items-center justify-center rounded-lg bg-[#e9f1fb] text-[#1d5b96]"><ShieldCheck size={16} /></div><div className="hidden text-left lg:block"><div className="text-xs font-bold text-slate-700">Analyst workspace</div><div className="text-[10px] text-slate-400">Demo access</div></div><ChevronDown size={14} className="text-slate-400" /></div></div>
  </header>;
}
