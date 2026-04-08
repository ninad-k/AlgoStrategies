/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        navy: {
          900: '#0F1E35',
          800: '#1B2A4A',
          700: '#243658',
        },
        teal: {
          500: '#0D7377',
          400: '#14A085',
        },
      },
    },
  },
  plugins: [],
}
