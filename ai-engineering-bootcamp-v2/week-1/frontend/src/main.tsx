// CODE FLOW:
// 1. The browser loads index.html, which loads this file.
// 2. We create one QueryClient — the object that holds all request state for the whole app.
// 3. createRoot finds the <div id="root"></div> that index.html left empty.
// 4. QueryClientProvider makes that client available to every component below it, so any
//    component can call useMutation without us passing anything down by hand.
// 5. <App /> renders inside, and decides which page to show.
//
// This is the entry point: every other file in src/ is reached because something here,
// or below here, imports it.

import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ReactQueryDevtools } from '@tanstack/react-query-devtools'
import App from './App'
import './index.css'

// Created ONCE, outside the component tree. If this lived inside a component it would be
// rebuilt on every render and lose all its state.
const queryClient = new QueryClient({
  defaultOptions: {
    mutations: {
      // Do NOT retry failed mutations. TanStack Query can retry automatically, but every
      // /ask call spends real money at OpenAI — a silent retry would double the bill and,
      // worse, could send the same question twice. Failures here should surface, not hide.
      retry: false,
    },
  },
})

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <App />
      {/* Dev-only panel — click the icon in the corner to watch requests as they happen.
          It is excluded automatically from a production build. */}
      <ReactQueryDevtools initialIsOpen={false} />
    </QueryClientProvider>
  </StrictMode>,
)

// TAKEAWAYS:
// 1. createRoot is the modern way to start a React app (React 18 onwards).
// 2. A Provider is React's way of sharing something with every component beneath it, without
//    passing it through each layer as a prop. Here it shares the QueryClient.
// 3. StrictMode deliberately runs some code twice in development to surface bugs — don't be
//    surprised to see a console message logged twice.
// 4. Turning off mutation retries is a deliberate choice for a paid API, not a default you
//    should copy blindly. For a free, read-only endpoint you would usually leave retries on.
