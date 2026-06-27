import { Routes, Route } from 'react-router-dom'
import { LegatumProvider } from './context/LegatumContext'
import Nav from './components/Nav'
import Landing from './pages/Landing'
import PersonaQuiz from './pages/PersonaQuiz'
import PersonaResult from './pages/PersonaResult'
import StoryMode from './pages/StoryMode'
import NGOMatch from './pages/NGOMatch'
import CredibilityReport from './pages/CredibilityReport'
import ImpactSimulation from './pages/ImpactSimulation'
import ImpactGraph from './pages/ImpactGraph'
import FoundationArc from './pages/FoundationArc'
import ImpactPassport from './pages/ImpactPassport'
import AdvisorDashboard from './pages/AdvisorDashboard'

export default function App() {
  return (
    <LegatumProvider>
      <div className="min-h-screen bg-navy-900 text-white font-sans">
        <Nav />
        <Routes>
          <Route path="/"           element={<Landing />} />
          <Route path="/quiz"       element={<PersonaQuiz />} />
          <Route path="/story"      element={<StoryMode />} />
          <Route path="/persona"    element={<PersonaResult />} />
          <Route path="/ngo-match"  element={<NGOMatch />} />
          <Route path="/credibility"element={<CredibilityReport />} />
          <Route path="/impact"     element={<ImpactSimulation />} />
          <Route path="/graph"      element={<ImpactGraph />} />
          <Route path="/arc"        element={<FoundationArc />} />
          <Route path="/passport"   element={<ImpactPassport />} />
          <Route path="/advisor"    element={<AdvisorDashboard />} />
        </Routes>
      </div>
    </LegatumProvider>
  )
}
