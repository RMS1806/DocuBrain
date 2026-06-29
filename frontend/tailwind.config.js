/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx,ts,tsx}'],
  theme: {
    extend: {
      colors: {
        terracotta: {
          50:  '#fdf5f2',
          100: '#fae8e2',
          200: '#f4cfc5',
          300: '#eaab9d',
          400: '#dc7e6a',
          500: '#c9604a',
          600: '#b54736',
          700: '#963a2c',
          800: '#7c3228',
          900: '#692d25',
          950: '#2C1A10',
        },
        olive: {
          50:  '#f5f6ee',
          100: '#e8ebcf',
          200: '#d3d8a3',
          300: '#b7be70',
          400: '#9aa348',
          500: '#7a8433',
          600: '#5f6728',
          700: '#4a5020',
          800: '#3d4220',
          900: '#343820',
          950: '#1c1f0a',
        },
        mustard: {
          50:  '#fdf9eb',
          100: '#faf0c7',
          200: '#f4df8a',
          300: '#eec94d',
          400: '#e8b521',
          500: '#d19710',
          600: '#a6750c',
          700: '#7e570b',
          800: '#694811',
          900: '#593b12',
        },
      },
    },
  },
  plugins: [],
}
