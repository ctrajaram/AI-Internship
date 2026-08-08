// WHAT THIS FILE DOES:
// It describes the exact shape of the data we send to /ask and the shape we get back.
// TypeScript uses these to catch mistakes before the app runs — misspell `tokens_used` and
// your editor complains immediately, instead of the value being `undefined` at runtime.
//
// These mirror the Pydantic models in main.py. Keep the two in step: if AskResponse gains a
// field there, add it here too.

// The structured object the model is forced to return (Answer in main.py).
export interface Answer {
  answer: string          // the actual text
  confidence: number      // 0.0 to 1.0, the model scoring itself
  sources_needed: boolean // whether the model thinks it should cite sources
}

// What we POST to /ask (AskRequest in main.py).
export interface AskRequest {
  question: string
  model?: string      // optional — the server falls back to gpt-4o
  force_bad?: boolean // optional — the stage 3 demo knob
}

// What /ask sends back (AskResponse in main.py).
export interface AskResponse {
  answer: Answer   // note: an OBJECT, not a string — the text is at answer.answer
  tokens_used: number
  model: string
  latency_ms: number
  cost_usd: number
}

// ACTUAL DATA example:
// {
//   answer: { answer: "RAG stands for...", confidence: 0.9, sources_needed: false },
//   tokens_used: 136,
//   model: "gpt-4o-mini",
//   latency_ms: 1662,
//   cost_usd: 0.000039
// }

// TAKEAWAYS:
// 1. An interface describes the shape of an object; it disappears at build time and costs
//    nothing at runtime.
// 2. A `?` after a field name means optional — you may leave it out entirely.
// 3. Nesting matters: `answer` is an object, so the text lives at `response.answer.answer`.
//    That trips people up constantly — the types are what stop you getting it wrong.
