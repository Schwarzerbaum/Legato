/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        navy: { 900: '#0a0d14', 800: '#0f1420', 700: '#141c2e' },
        lbbw: { teal: '#00a896', cyan: '#06b6d4', amber: '#f59e0b' },
      },
    },
  },
  plugins: [],
}
