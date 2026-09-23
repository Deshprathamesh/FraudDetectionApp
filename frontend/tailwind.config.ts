import type { Config } from 'tailwindcss';

const config: Config = {
  content: ['./app/**/*.{js,ts,jsx,tsx,mdx}', './components/**/*.{js,ts,jsx,tsx,mdx}', './services/**/*.{js,ts,jsx,tsx,mdx}'],
  theme: {
    extend: {
      colors: {
        navy: { 950: '#071426', 900: '#0b1d34', 800: '#102946' },
      },
      boxShadow: {
        panel: '0 1px 2px rgba(15, 23, 42, .05), 0 10px 26px rgba(15, 23, 42, .04)',
      },
    },
  },
  plugins: [],
};

export default config;
