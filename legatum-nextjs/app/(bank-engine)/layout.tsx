import type { Metadata } from 'next'
import BankNav from '../../components/BankNav'

export const metadata: Metadata = { title: 'Legato · Bank Intelligence' }

export default function BankEngineLayout({ children }: { children: React.ReactNode }) {
  return (
    <div style={{ minHeight: '100vh', background: '#ffffff', color: '#0f172a', fontFamily: "Inter, system-ui, -apple-system, sans-serif" }}>
      <div style={{ maxWidth: 1100, margin: '0 auto', padding: '0 32px', paddingBottom: 120 }}>
        {children}
      </div>
      <BankNav />
    </div>
  )
}
