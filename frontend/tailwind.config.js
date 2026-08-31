/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        brand: {
          50: "#f5f0ff",
          100: "#ece1ff",
          200: "#dcafff",
          300: "#be82ff",
          400: "#a100ff",
          500: "#7500c0",
          600: "#5f009c",
          700: "#460073",
          900: "#2b0047",
        },
      },
    },
  },
  plugins: [],
};
