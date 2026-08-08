// CODE FLOW:
// 1. `npm run dev` starts Vite, and Vite reads this file first.
// 2. The react() plugin teaches Vite how to turn JSX into JavaScript the browser understands.
// 3. The tailwindcss() plugin scans our files for class names and generates the matching CSS.
// 4. Vite then serves the app at http://localhost:5173.
// 5. When our code calls fetch('/ask'), the browser sends it to localhost:5173 like any other
//    request. Vite sees the /ask path, matches the proxy rule below, and forwards the request
//    to the FastAPI server on port 8000 — then hands the reply back.
//
// WHY THE PROXY EXISTS:
// The browser refuses to let a page from localhost:5173 read a response from localhost:8000 —
// a different port counts as a different site, so it is blocked by the same-origin policy.
// (The Streamlit page never hits this because its network call happens in Python on the
// server, where no browser is involved.)
// The usual fix is CORS: make FastAPI send headers saying "5173 is allowed". The proxy is a
// better fix here — the browser only ever talks to 5173, so it is same-origin and there is
// nothing to permit. That means zero changes to any .py file, and nothing to misconfigure.

import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      // Any request whose path starts with /ask goes to FastAPI, unchanged.
      // Use 127.0.0.1 rather than 'localhost': on Windows, Node may resolve 'localhost' to
      // the IPv6 address ::1, while uvicorn is listening on IPv4 — which fails to connect.
      '/ask': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
})

// TAKEAWAYS:
// 1. Vite is two things: a fast dev server now, and a bundler when you run `npm run build`.
// 2. Plugins are how Vite learns new tricks — JSX and Tailwind are both plugins here.
// 3. defineConfig does nothing at runtime; it exists so your editor can autocomplete the options.
// 4. The proxy is a DEV-SERVER feature only. `npm run build` produces plain static files with
//    no proxy in them. In production the same effect is achieved by having FastAPI serve those
//    built files itself, so the app and the API share one origin again (that is Step 5).
// 5. Because our code says fetch('/ask') — a relative path, no hostname — the exact same line
//    works in dev and in production. Nothing to swap at deploy time.
