/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx,ts,tsx}'],
  theme: {
    extend: {
      colors: {
        navy: {
          DEFAULT: '#0F2A44',
          mid: '#173D60',
          light: '#2E5B8A',
        },
        cream: {
          DEFAULT: '#FAF3E8',
          dark: '#F0E6D3',
        },
        orange: {
          DEFAULT: '#F26522',
          soft: '#F47B50',
          light: '#FDE8DF',
        },
        gray: {
          page: '#F3F6F9',
          border: '#DBE3EA',
          mid: '#627484',
          text: '#172B3A',
        },
        status: {
          paid: '#1FAD6F',
          paidbg: '#E6F7F0',
          cancelled: '#E84040',
          cancelledbg: '#FDE8E8',
          pending: '#D97706',
          pendingbg: '#FEF3C7',
        },
      },
      fontFamily: {
        sans: ['Montserrat', 'system-ui', 'sans-serif'],
      },
      fontSize: {
        hero: ['56px', { lineHeight: '1.1', fontWeight: '700' }],
        h1: ['36px', { lineHeight: '1.2', fontWeight: '700' }],
        h2: ['24px', { lineHeight: '1.3', fontWeight: '600' }],
        h3: ['18px', { lineHeight: '1.4', fontWeight: '600' }],
        label: ['12px', { lineHeight: '1', fontWeight: '500', letterSpacing: '0.08em' }],
      },
      borderRadius: {
        xl: '12px',
        '2xl': '16px',
      },
      boxShadow: {
        card: '0 1px 3px rgba(0,0,0,0.08), 0 1px 2px rgba(0,0,0,0.04)',
        'card-hover': '0 4px 12px rgba(0,0,0,0.12)',
      },
    },
  },
  plugins: [],
};
