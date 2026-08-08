// CODE FLOW:
// 1. main.tsx renders <App /> — this is the top of the component tree.
// 2. App's only job is to decide which page the user sees.
// 3. Today there is exactly one page, so it always renders <AskPage />.
//
// Keeping App this thin is deliberate. When a second page appears later, routing logic goes
// here and nothing else has to change.

import AskPage from './pages/AskPage'

function App() {
  return <AskPage />
}

export default App

// TAKEAWAYS:
// 1. A component is just a function that returns JSX (HTML-like markup).
// 2. Component names must start with a capital letter — that is how React tells <AskPage />
//    (your component) apart from <div> (a real HTML tag).
// 3. `export default` means other files import it without curly braces: import AskPage from ...
