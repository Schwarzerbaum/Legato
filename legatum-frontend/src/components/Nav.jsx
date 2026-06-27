import { Link, useLocation } from 'react-router-dom'

const LINKS = [
  { to: '/',            label: 'Home' },
  { to: '/story',       label: '▶ Story Mode' },
  { to: '/quiz',        label: 'Quick Quiz' },
  { to: '/ngo-match',   label: 'NGO Match' },
  { to: '/impact',      label: 'Impact Sim' },
  { to: '/graph',       label: 'Impact Graph' },
  { to: '/arc',         label: 'Foundation Arc' },
  { to: '/passport',    label: 'My Passport' },
  { to: '/advisor',     label: 'LBBW Advisor' },
]

export default function Nav() {
  const { pathname } = useLocation()

  return (
    <nav className="fixed top-0 left-0 right-0 z-50 bg-navy-900/95 backdrop-blur border-b border-white/10">
      <div className="max-w-7xl mx-auto px-4 flex items-center justify-between h-14">
        <Link to="/" className="flex items-center gap-2">
          <span className="text-lbbw-teal font-bold tracking-widest text-sm">LEGATUM</span>
          <span className="text-white/30 text-xs hidden sm:block">· by LBBW</span>
        </Link>
        <div className="flex items-center gap-1 overflow-x-auto scrollbar-none">
          {LINKS.map(l => (
            <Link
              key={l.to}
              to={l.to}
              className={`px-3 py-1.5 rounded text-xs font-medium whitespace-nowrap transition-colors ${
                pathname === l.to
                  ? 'bg-lbbw-teal/20 text-lbbw-teal'
                  : 'text-white/50 hover:text-white/80'
              }`}
            >
              {l.label}
            </Link>
          ))}
        </div>
      </div>
    </nav>
  )
}
