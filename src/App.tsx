import { AnimatePresence, motion } from 'framer-motion'
import { useAppStore } from './store/useAppStore'
import { OnboardingPage } from './pages/OnboardingPage'
import { GraphPage } from './pages/GraphPage'

function App() {
  const currentView = useAppStore(s => s.currentView)

  return (
    <AnimatePresence mode="wait">
      {currentView === 'onboarding' ? (
        <motion.div
          key="onboarding"
          initial={{ opacity: 0, scale: 1.02 }}
          animate={{ opacity: 1, scale: 1 }}
          exit={{ opacity: 0, scale: 0.97 }}
          transition={{ duration: 0.3, ease: [0.25, 0.46, 0.45, 0.94] }}
          className="min-h-screen"
        >
          <OnboardingPage />
        </motion.div>
      ) : (
        <motion.div
          key="graph"
          initial={{ opacity: 0, scale: 1.02 }}
          animate={{ opacity: 1, scale: 1 }}
          exit={{ opacity: 0, scale: 0.97 }}
          transition={{ duration: 0.3, ease: [0.25, 0.46, 0.45, 0.94] }}
          className="h-screen"
        >
          <GraphPage />
        </motion.div>
      )}
    </AnimatePresence>
  )
}

export default App
