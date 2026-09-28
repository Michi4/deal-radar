/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{vue,ts}'],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        acc: {
          DEFAULT: '#10b981',
          dark: '#047857',
          soft: '#d1fae5'
        }
      },
      spacing: {
        // 4/8px enforced scale (FINISH spacing rule)
        '1': '0.25rem', '2': '0.5rem', '3': '0.75rem', '4': '1rem',
        '6': '1.5rem', '8': '2rem'
      }
    }
  },
  plugins: []
}
