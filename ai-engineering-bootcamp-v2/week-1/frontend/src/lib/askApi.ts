// CODE FLOW:
// 1. A component calls askQuestion({ question: "..." }).
// 2. fetch sends a POST to /ask — a RELATIVE path, so it goes to whatever host is serving
//    the page. In dev that is localhost:5173, and Vite's proxy forwards it to FastAPI.
// 3. If the server replies with an error status, we throw so the caller can handle it.
// 4. Otherwise we parse the JSON and return it, typed as AskResponse.
//
// This file knows nothing about React. Keeping the network call separate from components
// means you can read it, test it, or reuse it without any UI involved.

import type { AskRequest, AskResponse } from '../types'

export async function askQuestion(request: AskRequest): Promise<AskResponse> {
  const response = await fetch('/ask', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  })

  // IMPORTANT: fetch does NOT throw on 404, 422 or 502. It only rejects when the network
  // itself fails (server down, DNS failure). A 502 is a *successful* fetch of an error page,
  // so we have to check response.ok ourselves and throw deliberately.
  if (!response.ok) {
    // FastAPI puts its error text in a "detail" field. Try to surface that rather than a
    // bare status code, so the UI can show something a human can act on.
    let detail = `Request failed with status ${response.status}`
    try {
      const body = await response.json()
      if (body?.detail) detail = String(body.detail)
    } catch {
      // The error body was not JSON — keep the status-code message we already have.
    }
    throw new Error(detail)
  }

  return (await response.json()) as AskResponse
}

// TAKEAWAYS:
// 1. `await` pauses until the promise settles; the function returns a Promise to its caller.
// 2. response.ok is true only for statuses 200-299 — always check it, because fetch will
//    happily hand you a 500 without complaining.
// 3. Throwing on failure is what lets TanStack Query populate its `isError` and `error`
//    states for us. If we returned the error instead, Query would treat it as success.
// 4. `as AskResponse` is a promise to TypeScript, not a check. The server could send
//    anything; we are trusting main.py's response_model to hold up its end.
