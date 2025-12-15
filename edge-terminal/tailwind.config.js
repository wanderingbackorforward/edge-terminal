/** @type {import('tailwindcss').Config} */
export default {
    content: [
        "./index.html",
        "./src/**/*.{js,ts,jsx,tsx}",
    ],
    theme: {
        extend: {
            colors: {
                // Dark theme palette
                background: '#0d1117',
                surface: '#161b22',
                border: '#30363d',
                primary: {
                    DEFAULT: '#58a6ff',
                    hover: '#79c0ff',
                    active: '#1f6feb',
                },
                success: '#3fb950',
                warning: '#d29922',
                error: '#f85149',
                text: {
                    primary: '#c9d1d9',
                    secondary: '#8b949e',
                    muted: '#6e7681',
                },
            },
            fontFamily: {
                sans: ['Inter', 'system-ui', 'sans-serif'],
                mono: ['JetBrains Mono', 'monospace'],
            },
            animation: {
                'pulse-fast': 'pulse 1.5s cubic-bezier(0.4, 0, 0.6, 1) infinite',
            },
        },
    },
    plugins: [],
}
