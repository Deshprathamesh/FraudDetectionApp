import type { Metadata } from 'next';
import './globals.css';
import '@xyflow/react/dist/style.css';
import { AppShell } from '@/components/layout/AppShell';

export const metadata: Metadata = {
  title: 'FraudGraph AI · Investigation Cockpit',
  description: 'Agentic fraud investigation cockpit for analysts',
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body><AppShell>{children}</AppShell></body>
    </html>
  );
}
