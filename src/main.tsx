import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import './App.css'
import App from './App.tsx'
import { AdvisorBookingPage } from './pages/AdvisorBookingPage.tsx'
import { BookingSuccessPage } from './pages/BookingSuccessPage.tsx'
import { ResearchPage } from './pages/ResearchPage.tsx'
import { BankLayout } from './pages/bank/BankLayout.tsx'
import { DiscoverPage } from './pages/bank/DiscoverPage.tsx'
import { AssessPage } from './pages/bank/AssessPage.tsx'
import { PortfolioPage } from './pages/bank/PortfolioPage.tsx'
import { BankFoundationPage } from './pages/bank/BankFoundationPage.tsx'
import { KnowledgeGraphPage } from './pages/bank/KnowledgeGraphPage.tsx'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<App />} />
        <Route path="/schedule/:advisorId" element={<AdvisorBookingPage />} />
        <Route path="/booking-success" element={<BookingSuccessPage />} />
        <Route path="/research" element={<ResearchPage />} />

        {/* Bank / advisor side */}
        <Route path="/bank" element={<BankLayout />}>
          <Route index element={<Navigate to="/bank/discover" replace />} />
          <Route path="discover" element={<DiscoverPage />} />
          <Route path="assess" element={<AssessPage />} />
          <Route path="portfolio" element={<PortfolioPage />} />
          <Route path="foundation" element={<BankFoundationPage />} />
          <Route path="intelligence" element={<KnowledgeGraphPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  </StrictMode>,
)
