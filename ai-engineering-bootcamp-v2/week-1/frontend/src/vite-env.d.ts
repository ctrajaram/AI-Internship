/// <reference types="vite/client" />

// WHAT THIS FILE DOES:
// TypeScript only understands .ts and .tsx files. On its own it has no idea what
// `import './index.css'` means, and reports "cannot find module './index.css'".
//
// The single reference line above pulls in Vite's own type declarations, which tell
// TypeScript that importing .css, .svg, .png and friends is legal and what each one returns.
// It also types `import.meta.env`, which is how Vite exposes environment variables.
//
// The `///` syntax is a triple-slash directive — an old TypeScript feature that means
// "load these type declarations here". It must stay at the very top of the file to work.

// TAKEAWAYS:
// 1. A .d.ts file contains only type information; it produces no JavaScript at all.
// 2. Every Vite + TypeScript project needs this file. It is easy to forget, and the symptom
//    is a confusing "cannot find module" error on a CSS import that plainly exists.
// 3. agentic-ai/frontend/src/vite-env.d.ts is the same file, for the same reason.
