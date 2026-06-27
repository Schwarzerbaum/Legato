import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import './App.css'
import App from './App.tsx'
import { AdvisorBookingPage } from './pages/AdvisorBookingPage.tsx'
import { BookingSuccessPage } from './pages/BookingSuccessPage.tsx'
import { ResearchPage } from './pages/ResearchPage.tsx'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<App />} />
        <Route path="/schedule/:advisorId" element={<AdvisorBookingPage />} />
        <Route path="/booking-success" element={<BookingSuccessPage />} />
        <Route path="/research" element={<ResearchPage />} />
      </Routes>
    </BrowserRouter>
  </StrictMode>,
)
