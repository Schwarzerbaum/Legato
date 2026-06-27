/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ['./app/**/*.{js,ts,jsx,tsx}', './components/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        bg: '#0A1628',
        surface: '#0F2040',
        elevated: '#162952',
        teal: { DEFAULT: '#00C896', glow: 'rgba(0,200,150,0.25)' },
        catalyst: '#F59E0B',
        guardian: '#059669',
        explorer: '#0EA5E9',
        architect: '#7C3AED',
        warn: '#EF4444',
        verified: '#10B981',
        onchain: '#8B5CF6',
        primary: '#F8FAFC',
        secondary: '#94A3B8',
        muted: '#475569',
      },
      fontFamily: {
        display: ['Clash Display', 'Inter', 'sans-serif'],
        sans: ['Inter', 'sans-serif'],
        mono: ['JetBrains Mono', 'monospace'],
      },
      animation: {
        'breathe': 'breathe 4s ease-in-out infinite',
        'float': 'float 6s ease-in-out infinite',
        'pulse-ring': 'pulse-ring 2s ease-out infinite',
      },
    },
  },
  plugins: [],
}
