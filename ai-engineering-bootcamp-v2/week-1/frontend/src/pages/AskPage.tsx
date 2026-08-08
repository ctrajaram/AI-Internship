// CODE FLOW:
// 1. App renders <AskPage /> — this is the whole screen the user sees.
// 2. useMutation wires the askQuestion function into TanStack Query and hands back an object
//    describing the request's current state: isPending, isError, error, data.
// 3. <AskForm> collects the question and model, then calls ask.mutate with them.
// 4. React re-renders automatically each time the mutation's state changes.
// 5. While pending, the form disables itself. On failure we show the error. On success we
//    hand the response to <ResultCard>.
//
// The page owns the request; the form owns the inputs; the card owns the display. Each piece
// has one job, which is why none of them is complicated.

import { useMutation } from '@tanstack/react-query'
import { askQuestion } from '../lib/askApi'
import AskForm from '../components/ask/AskForm'
import ResultCard from '../components/ask/ResultCard'

function AskPage() {
  // useMutation is for CHANGING something (a POST), not for reading. The alternative,
  // useQuery, runs automatically and re-runs on things like window focus — which for a paid
  // endpoint would fire OpenAI calls behind your back. A mutation only runs when you say so.
  const ask = useMutation({ mutationFn: askQuestion })

  return (
    <main className="min-h-screen bg-slate-50 text-slate-900">
      <div className="mx-auto max-w-2xl px-6 py-16">
        <h1 className="text-3xl font-semibold tracking-tight">Week 1 — /ask</h1>

        <p className="mt-2 text-slate-600">
          A React front end for the FastAPI endpoint, alongside the Streamlit page.
        </p>

        {/* mutate takes exactly the argument askQuestion expects — an AskRequest — so the
            form's onSubmit can be handed straight to it with no glue code. */}
        <AskForm onSubmit={ask.mutate} isPending={ask.isPending} />

        {ask.isError && (
          <div className="mt-6 rounded-lg border border-red-200 bg-red-50 p-4">
            <p className="text-sm font-medium text-red-800">Request failed</p>
            <p className="mt-1 text-sm text-red-700">{ask.error.message}</p>
            <p className="mt-2 text-xs text-red-600">
              If this says “Failed to fetch”, the FastAPI server on port 8000 is not running.
            </p>
          </div>
        )}

        {ask.data && <ResultCard result={ask.data} />}
      </div>
    </main>
  )
}

export default AskPage

// TAKEAWAYS:
// 1. useMutation replaces the usual trio of useState calls — loading, error, and data are
//    all handed to you, already kept in sync.
// 2. Passing ask.mutate directly as onSubmit works because the types line up exactly. When
//    they do, resist writing a wrapper function that only forwards its argument.
// 3. `{condition && <jsx/>}` renders the JSX only when the condition is true.
// 4. Note what this file does NOT contain: no fetch, no useState, no try/catch. Each of
//    those lives in the one place responsible for it.
