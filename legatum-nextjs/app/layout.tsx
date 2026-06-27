import type { Metadata } from 'next'
import './globals.css'

export const metadata: Metadata = {
  title: 'Legato · LBBW Bank Intelligence',
  description: 'AI-powered philanthropic advisory for LBBW advisors',
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="h-full">
      <body className="min-h-full" style={{ background:'#F4F1EA' }}>
        {children}
      </body>
    </html>
  )
}
