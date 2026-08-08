// CODE FLOW:
// 1. AskPage renders <AskForm onSubmit={...} isPending={...} />.
// 2. This component owns the two things the user is editing: the question text and the
//    chosen model. Neither of those belongs to the page, so the state lives here.
// 3. Typing in the textarea calls setQuestion, which re-renders with the new value.
// 4. Submitting the form calls the onSubmit prop, handing the values UP to the page.
// 5. The page runs the mutation. This component never touches the network.
//
// This is the same split as ChatInput.tsx in agentic-ai: the input owns what is being typed,
// the parent owns what happens when it is sent.

import { useState } from 'react'
import type { AskRequest } from '../../types'

// The values this component expects to be given. Declaring them means the page cannot
// forget one, or pass the wrong type, without TypeScript objecting.
interface AskFormProps {
  onSubmit: (request: AskRequest) => void
  isPending: boolean
}

// The models main.py knows how to price (see MODEL_PRICES_PER_1K there). Keep in step.
const MODELS = ['gpt-4o-mini', 'gpt-4o', 'o3-mini']

function AskForm({ onSubmit, isPending }: AskFormProps) {
  const [question, setQuestion] = useState('What is RAG in one sentence?')
  const [model, setModel] = useState('gpt-4o-mini')

  const handleSubmit = (event: React.FormEvent) => {
    // A <form> reloads the whole page when submitted — that is the browser's 1995 default.
    // preventDefault stops it, so React can handle the submit instead.
    event.preventDefault()

    const trimmed = question.trim()
    if (!trimmed) return // nothing to ask; don't spend a request on empty input

    onSubmit({ question: trimmed, model })
  }

  return (
    <form onSubmit={handleSubmit} className="mt-8 space-y-4">
      <div>
        <label htmlFor="question" className="block text-sm font-medium text-slate-700">
          Question
        </label>
        <textarea
          id="question"
          rows={3}
          value={question}
          onChange={(event) => setQuestion(event.target.value)}
          disabled={isPending}
          className="mt-1 w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm
                     shadow-sm outline-none focus:border-slate-500 disabled:bg-slate-100"
        />
      </div>

      <div className="flex items-end gap-3">
        <div className="flex-1">
          <label htmlFor="model" className="block text-sm font-medium text-slate-700">
            Model
          </label>
          <select
            id="model"
            value={model}
            onChange={(event) => setModel(event.target.value)}
            disabled={isPending}
            className="mt-1 w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm
                       shadow-sm outline-none focus:border-slate-500 disabled:bg-slate-100"
          >
            {MODELS.map((name) => (
              <option key={name} value={name}>
                {name}
              </option>
            ))}
          </select>
        </div>

        <button
          type="submit"
          disabled={isPending || !question.trim()}
          className="rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white
                     hover:bg-slate-700 disabled:cursor-not-allowed disabled:bg-slate-400"
        >
          {isPending ? 'Asking…' : 'Ask'}
        </button>
      </div>
    </form>
  )
}

export default AskForm

// TAKEAWAYS:
// 1. A "controlled input" means React holds the value: value={question} plus onChange to
//    update it. The state is the single source of truth, not the DOM element.
// 2. Props flow DOWN (isPending), events flow UP (onSubmit). That one rule explains most
//    React component design.
// 3. event.preventDefault() on a form submit is required in React apps, every time.
// 4. .map() over an array to render a list; each item needs a unique `key` so React can
//    tell them apart between renders.
// 5. Disabling inputs while isPending is true stops the user editing mid-flight and stops
//    a second paid request being sent.
