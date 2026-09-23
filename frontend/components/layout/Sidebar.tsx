'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { Activity, ArrowUpRight, BarChart3, BookOpen, BriefcaseBusiness, ChevronRight, GitBranch, LayoutDashboard, Plus, ShieldCheck, Sparkles } from 'lucide-react';

const nav = [
  { label: 'Overview', href: '/', icon: LayoutDashboard },
  { label: 'Investigations', href: '/cases/CASE-1024', icon: BriefcaseBusiness, badge: '4' },
  { label: 'New investigation', href: '/investigate', icon: Plus },
];

export function Sidebar() {
  const pathname = usePathname();
  return (
    <aside className="fixed inset-y-0 left-0 z-20 flex w-[248px] flex-col bg-[#091a30] px-4 py-5 text-white">
      <div className="flex items-center gap-3 px-3 pb-8">
        <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-blue-400 to-cyan-300 text-navy-950 shadow-lg shadow-cyan-500/20"><ShieldCheck size={20} strokeWidth={2.5} /></div>
        <div><div className="text-[15px] font-bold tracking-tight">FraudGraph<span className="text-cyan-300"> AI</span></div><div className="mt-0.5 text-[10px] uppercase tracking-[0.18em] text-slate-400">Investigation cockpit</div></div>
      </div>

      <div className="mb-3 px-3 text-[10px] font-bold uppercase tracking-[0.18em] text-slate-500">Workspace</div>
      <nav className="space-y-1">
        {nav.map((item) => {
          const Icon = item.icon;
          const active =
              item.href === "/"
                ? pathname === "/"
                : pathname?.startsWith(item.href) ?? false;
          return <Link key={item.href} href={item.href} className={`group flex items-center gap-3 rounded-xl px-3 py-2.5 text-[13px] font-medium transition ${active ? 'bg-white/10 text-white shadow-inner' : 'text-slate-400 hover:bg-white/5 hover:text-slate-200'}`}><Icon size={17} className={active ? 'text-cyan-300' : 'text-slate-500 group-hover:text-slate-300'} /><span className="flex-1">{item.label}</span>{item.badge && <span className="rounded-md bg-red-400/15 px-1.5 py-0.5 text-[10px] font-bold text-red-300">{item.badge}</span>}{active && !item.badge && <ChevronRight size={14} className="text-slate-500" />}</Link>;
        })}
      </nav>

      <div className="mb-3 mt-9 px-3 text-[10px] font-bold uppercase tracking-[0.18em] text-slate-500">Intelligence</div>
      <div className="space-y-1 text-[13px] font-medium text-slate-400">
        <div className="flex items-center gap-3 rounded-xl px-3 py-2.5"><GitBranch size={17} className="text-slate-500" />Graph network</div>
        <div className="flex items-center gap-3 rounded-xl px-3 py-2.5"><BookOpen size={17} className="text-slate-500" />Case memory</div>
        <div className="flex items-center gap-3 rounded-xl px-3 py-2.5"><BarChart3 size={17} className="text-slate-500" />Benchmark view</div>
      </div>

      <div className="mt-auto rounded-2xl border border-white/10 bg-white/[0.045] p-4">
        <div className="mb-3 flex items-center gap-2"><div className="flex h-7 w-7 items-center justify-center rounded-lg bg-emerald-400/10 text-emerald-300"><Activity size={15} /></div><span className="text-xs font-semibold">System healthy</span></div>
        <div className="mb-2 flex items-center justify-between text-[11px] text-slate-500"><span>Agent orchestration</span><span className="text-emerald-300">Online</span></div>
        <div className="mb-2 flex items-center justify-between text-[11px] text-slate-500"><span>TigerGraph</span><span className="text-emerald-300">Connected</span></div>
        <div className="mt-3 flex items-center gap-1 text-[10px] text-slate-500"><Sparkles size={12} className="text-cyan-300" /> Demo environment <ArrowUpRight size={11} /></div>
      </div>
    </aside>
  );
}
