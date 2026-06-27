import { NavLink, Outlet, Link } from 'react-router-dom'
import { Search, ShieldCheck, Briefcase, Landmark, Network, ArrowLeft } from 'lucide-react'
import { cn } from '@/lib/utils'

const LBBW = '#003B6F' // bank identity accent

const TABS = [
  { to: '/bank/discover',     label: 'Discover',     icon: Search },
  { to: '/bank/assess',       label: 'Assess',       icon: ShieldCheck },
  { to: '/bank/portfolio',    label: 'Portfolio',    icon: Briefcase },
  { to: '/bank/foundation',   label: 'Foundation',   icon: Landmark },
  { to: '/bank/intelligence', label: 'Intelligence', icon: Network },
]

// Shared chrome for the bank/advisor side: a floating bottom pill nav (mirrors
// the giver app's PhasesBar) + a link back to the giver app. Pages render in the
// Outlet and scroll themselves (with pb-28 to clear the nav).
export function BankLayout() {
  return (
    <div className="relative h-screen overflow-hidden bg-background">
      <Outlet />

      <div className="pointer-events-none absolute bottom-0 left-0 right-0 flex justify-center pb-3">
        <div className="pointer-events-auto flex items-center gap-1 rounded-full border border-border/60 bg-background/80 px-2 py-1.5 shadow-lg backdrop-blur-md">
          <Link
            to="/"
            className="flex items-center gap-1.5 rounded-full px-3 py-1.5 ds-caption font-medium text-muted-foreground transition-colors hover:text-foreground"
          >
            <ArrowLeft className="size-3.5" />
            Giver app
          </Link>
          <div className="mx-1 h-4 w-px bg-border" />
          {TABS.map(t => {
            const Icon = t.icon
            return (
              <NavLink
                key={t.to}
                to={t.to}
                className={({ isActive }) =>
                  cn(
                    'flex items-center gap-1.5 rounded-full px-3 py-1.5 ds-caption font-medium transition-all',
                    isActive ? 'text-white' : 'text-muted-foreground hover:text-foreground',
                  )
                }
                style={({ isActive }) => (isActive ? { backgroundColor: LBBW } : undefined)}
              >
                <Icon className="size-3.5" />
                {t.label}
              </NavLink>
            )
          })}
        </div>
      </div>
    </div>
  )
}
