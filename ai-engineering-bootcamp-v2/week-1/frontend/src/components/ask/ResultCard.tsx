// CODE FLOW:
// 1. AskPage renders <ResultCard result={ask.data} /> once a response has arrived.
// 2. This component holds NO state of its own. It is given a result and draws it.
// 3. If a new request returns, the page passes a new result and this re-renders.
//
// A component with no state, whose output depends only on its props, is the easiest kind to
// reason about and to reuse. Aim for these wherever you can.

import type { AskResponse } from '../../types'

interface ResultCardProps {
  result: AskResponse
}

// Small helper so the metric rows below stay readable.
function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-xs uppercase tracking-wide text-slate-500">{label}</dt>
      <dd className="mt-0.5 font-mono text-sm text-slate-900">{value}</dd>
    </div>
  )
}

function ResultCard({ result }: ResultCardProps) {
  return (
    <div className="mt-6 rounded-lg border border-slate-200 bg-white p-6 shadow-sm">
      {/* NOTE the double .answer — the API returns an OBJECT called answer, and the text
          sits inside it. This is the structured-output shape from stage 2 of the demo. */}
      <p className="text-slate-900">{result.answer.answer}</p>

      <div className="mt-4 flex flex-wrap gap-2 text-xs">
        <span className="rounded-full bg-slate-100 px-2 py-1 text-slate-700">
          confidence {result.answer.confidence}
        </span>
        <span className="rounded-full bg-slate-100 px-2 py-1 text-slate-700">
          sources_needed {String(result.answer.sources_needed)}
        </span>
      </div>

      <dl className="mt-6 grid grid-cols-2 gap-4 border-t border-slate-100 pt-4 sm:grid-cols-4">
        <Metric label="model" value={result.model} />
        <Metric label="tokens" value={String(result.tokens_used)} />
        <Metric label="latency" value={`${result.latency_ms} ms`} />
        {/* toFixed(6) because the real numbers are around $0.00004 — default formatting
            would show 4e-5, which is correct but unreadable. */}
        <Metric label="cost" value={`$${result.cost_usd.toFixed(6)}`} />
      </dl>
    </div>
  )
}

export default ResultCard

// TAKEAWAYS:
// 1. A component that takes props and returns JSX, with no useState, is called a
//    "presentational" component. Prefer them — they are trivial to test and reuse.
// 2. You can define a small helper component (Metric) in the same file when it is only used
//    here. Split it into its own file only once something else needs it.
// 3. React will not render a boolean, so String(result.answer.sources_needed) is needed to
//    show true/false. Numbers and strings render directly; booleans and null render nothing.
// 4. Template literals with backticks let you build strings inline: `${value} ms`.
