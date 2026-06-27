import type { Metadata } from 'next'
import './globals.css'
import BottomNav from '../components/BottomNav'

export const metadata: Metadata = {
  title: 'LEGATUM · by LBBW',
  description: 'Intelligence-first philanthropic banking',
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="h-full">
      <body className="min-h-full bg-[#0A1628] text-[#F8FAFC] antialiased pb-16">
        {children}
        <BottomNav />
      </body>
    </html>
  )
}
