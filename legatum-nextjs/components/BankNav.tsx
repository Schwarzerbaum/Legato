'use client'
import Link from 'next/link'
import { usePathname } from 'next/navigation'

const STEPS = [
  { n: 1, label: 'Discover',     href: '/discover' },
  { n: 2, label: 'Assess',       href: '/credibility' },
  { n: 3, label: 'Portfolio',    href: '/manage' },
  { n: 4, label: 'Foundation',   href: '/foundation-intelligence' },
  { n: 5, label: 'Intelligence', href: '/knowledge-graph' },
]

export default function BankNav() {
  const path = usePathname() ?? ''
  const activeStep = STEPS.find(s => path === s.href || path.startsWith(s.href + '/'))

  return (
    <nav style={{
      position: 'fixed', bottom: 24, left: 0, right: 0, zIndex: 50,
      display: 'flex', justifyContent: 'center',
      pointerEvents: 'none',
    }}>
      <div style={{
        display: 'flex', alignItems: 'center',
        background: '#ffffff',
        borderRadius: 999,
        border: '1px solid #e2e8f0',
        boxShadow: '0 4px 24px rgba(0,0,0,0.08), 0 1px 4px rgba(0,0,0,0.04)',
        padding: '4px 5px',
        gap: 2,
        pointerEvents: 'auto',
      }}>
        {/* Logo */}
        <div style={{ padding: '6px 14px 6px 10px', borderRight: '1px solid #e2e8f0', marginRight: 4 }}>
          <span style={{ fontWeight: 600, fontSize: 13, color: '#0f172a', letterSpacing: '-0.02em' }}>
            LBBW <span style={{ background: 'linear-gradient(90deg,#7c3aed,#2563eb)', WebkitBackgroundClip:'text', WebkitTextFillColor:'transparent', backgroundClip:'text' }}>·</span>
          </span>
        </div>

        {STEPS.map((step) => {
          const isActive = activeStep?.n === step.n
          return (
            <Link key={step.href} href={step.href} style={{ textDecoration: 'none' }}>
              <div style={{
                display: 'flex', alignItems: 'center', gap: 6,
                padding: isActive ? '7px 18px' : '7px 14px',
                borderRadius: 999,
                background: isActive
                  ? 'linear-gradient(135deg, #7c3aed, #2563eb)'
                  : 'transparent',
                transition: 'all 0.18s',
                cursor: 'pointer',
              }}>
                <span style={{
                  fontSize: 11, fontWeight: isActive ? 600 : 400,
                  color: isActive ? '#ffffff' : '#64748b',
                  letterSpacing: '-0.01em',
                  userSelect: 'none',
                  whiteSpace: 'nowrap',
                }}>
                  {step.n}. {step.label}
                </span>
              </div>
            </Link>
          )
        })}

        {/* Link to the giver-facing app (set NEXT_PUBLIC_GIVER_URL at deploy) */}
        {process.env.NEXT_PUBLIC_GIVER_URL && (
          <a
            href={process.env.NEXT_PUBLIC_GIVER_URL}
            target="_blank"
            rel="noopener noreferrer"
            style={{ textDecoration: 'none', marginLeft: 4, paddingLeft: 10, borderLeft: '1px solid #e2e8f0' }}
          >
            <div style={{ display: 'flex', alignItems: 'center', padding: '7px 12px', borderRadius: 999, cursor: 'pointer' }}>
              <span style={{ fontSize: 11, fontWeight: 400, color: '#64748b', letterSpacing: '-0.01em', whiteSpace: 'nowrap' }}>
                Giver app ↗
              </span>
            </div>
          </a>
        )}
      </div>
    </nav>
  )
}
