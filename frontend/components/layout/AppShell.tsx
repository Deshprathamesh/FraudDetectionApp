'use client';

import type { ReactNode } from 'react';
import { Sidebar } from './Sidebar';
import { Topbar } from './Topbar';

export function AppShell({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-screen bg-[#f4f7fb]">
      <Sidebar />
      <div className="pl-[248px]">
        <Topbar />
        <main className="min-h-[calc(100vh-68px)] px-8 py-7">{children}</main>
      </div>
    </div>
  );
}
