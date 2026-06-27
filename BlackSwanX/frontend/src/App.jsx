import { Routes, Route, Link, useLocation } from 'react-router-dom'
import Dashboard from './pages/Dashboard'
import Simulation from './pages/Simulation'
import BlackSwanXMap from './pages/ResonanceMap'
import Report from './pages/Report'
import Chat from './pages/Chat'
import Accounting from './pages/Accounting'
import NeuralMap from './pages/NeuralMap'
import ImpactPassport from './pages/ImpactPassport'
import LegatumDashboard from './pages/LegatumDashboard'

const navItems = [
  { path: '/', label: 'LEGATUM', icon: '⬡' },
  { path: '/passport', label: 'Impact Passport', icon: '🏅' },
  { path: '/blackswanx', label: 'BlackSwanX Map', icon: '◎' },
  { path: '/simulation', label: 'Simulation', icon: '⟳' },
  { path: '/report', label: 'Report', icon: '▤' },
  { path: '/chat', label: 'Chat', icon: '◈' },
  { path: '/accounting', label: 'Accounting', icon: '₿' },
  { path: '/neural', label: 'Neural Map', icon: '⬢' },
  { path: '/bsx', label: 'BSX Classic', icon: '◉' },
]

export default function App() {
  const location = useLocation()

  return (
    <div className="min-h-screen flex">
      {/* Sidebar */}
      <nav className="w-56 bg-[#111118] border-r border-gray-800 p-4 flex flex-col gap-1">
        <div className="mb-6">
          <div className="text-xl font-bold text-cyan-400 tracking-wider">LEGATUM</div>
          <div className="text-[9px] text-gray-600 mt-0.5 tracking-widest">LBBW · HackXplore 2026</div>
        </div>
        {navItems.map(({ path, label, icon }) => (
          <Link
            key={path}
            to={path}
            className={`px-3 py-2 rounded-lg text-sm flex items-center gap-2 transition-colors ${
              location.pathname === path
                ? 'bg-cyan-500/10 text-cyan-400'
                : 'text-gray-400 hover:text-gray-200 hover:bg-white/5'
            }`}
          >
            <span className="text-base">{icon}</span>
            {label}
          </Link>
        ))}
        <div className="mt-auto text-xs text-gray-600 pt-4 border-t border-gray-800">
          Impact Intelligence Platform
          <br />
          Powered by LBBW
        </div>
      </nav>

      {/* Main content */}
      <main className="flex-1 p-6 overflow-auto">
        <Routes>
          <Route path="/" element={<LegatumDashboard />} />
          <Route path="/passport" element={<ImpactPassport />} />
          <Route path="/blackswanx" element={<BlackSwanXMap />} />
          <Route path="/simulation" element={<Simulation />} />
          <Route path="/report" element={<Report />} />
          <Route path="/chat" element={<Chat />} />
          <Route path="/accounting" element={<Accounting />} />
          <Route path="/neural" element={<NeuralMap />} />
          <Route path="/bsx" element={<Dashboard />} />
        </Routes>
      </main>
    </div>
  )
}
