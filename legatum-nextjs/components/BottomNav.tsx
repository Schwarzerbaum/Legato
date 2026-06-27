'use client'
import Link from 'next/link'
import { usePathname } from 'next/navigation'

// User Engine: L1 onboarding · L4 persona · L5 impact · L7 foundation · L8 passport · L9 stifter
// Bank Engine: L2 discover · L3 credibility · L6 knowledge-graph
const NAV = [
  { href:'/', icon:'🏠', label:'Home' },
  { href:'/discover', icon:'🔍', label:'Discover' },
  { href:'/impact', icon:'⚡', label:'Impact' },
  { href:'/passport', icon:'🌳', label:'Passport' },
  { href:'/foundation', icon:'🏛', label:'Foundation' },
  { href:'/stifter', icon:'🧠', label:'Strategy' },
  { href:'/credibility', icon:'🛡', label:'Credibility' },
  { href:'/knowledge-graph', icon:'🕸', label:'Graph' },
]

export default function BottomNav() {
  const path = usePathname()
  if (path==='/'||path==='/onboarding'||path==='/persona') return null
  return (
    <nav className="fixed bottom-0 left-0 right-0 z-40 bg-[#0F2040]/95 backdrop-blur-md border-t border-[#162952]">
      <div className="max-w-lg mx-auto flex">
        {NAV.map(n=>(
          <Link key={n.href} href={n.href}
            className={`flex-1 flex flex-col items-center py-3 gap-0.5 transition-colors ${
              path===n.href?'text-[#00C896]':'text-[#475569] hover:text-[#94A3B8]'
            }`}>
            <span className="text-lg">{n.icon}</span>
            <span className="text-[10px]">{n.label}</span>
          </Link>
        ))}
      </div>
    </nav>
  )
}
