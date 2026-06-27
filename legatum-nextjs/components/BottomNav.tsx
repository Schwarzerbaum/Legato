'use client'
import Link from 'next/link'
import { usePathname } from 'next/navigation'

const NAV = [
  { href:'/', icon:'🏠', label:'Home' },
  { href:'/discover', icon:'🔍', label:'Discover' },
  { href:'/impact', icon:'⚡', label:'Impact' },
  { href:'/passport', icon:'🌳', label:'Passport' },
  { href:'/foundation', icon:'🏛', label:'Foundation' },
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
