import { useState } from 'react'
import './App.css'

const API_URL = 'http://localhost:8000/query'

const exampleQuestions = [
  'How long did the route leak incident last?',
  'What caused the major Cloudflare outage?',
  'How did Cloudflare mitigate the incident?',
]

function App() {
  const [question, setQuestion] = useState('')
  const [answer, setAnswer] = useState('')
  const [citations, setCitations] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  async function submitQuestion(questionToAsk) {
    const trimmedQuestion = questionToAsk.trim()

    if (!trimmedQuestion || loading) return

    setQuestion(trimmedQuestion)
    setLoading(true)
    setError('')
    setAnswer('')
    setCitations([])

    try {
      const response = await fetch(API_URL, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          question: trimmedQuestion,
        }),
      })

      if (!response.ok) {
        throw new Error(`Server responded with status ${response.status}`)
      }

      const data = await response.json()

      setAnswer(data.answer)
      setCitations(data.citations || [])
    } catch (err) {
      setError(
        'Unable to reach the RAG backend. Make sure the FastAPI server is running.'
      )
      console.error(err)
    } finally {
      setLoading(false)
    }
  }

  async function handleSubmit(e) {
    e.preventDefault()
    await submitQuestion(question)
  }

  function handleExampleClick(example) {
    submitQuestion(example)
  }

  return (
    <div className="app-shell">
      <nav className="navbar">
        <div className="nav-content">
          <div className="brand">
            <div className="brand-icon">CF</div>

            <div>
              <div className="brand-name">Incident Intelligence</div>
              <div className="brand-label"> Knowledge System</div>
            </div>
          </div>


        </div>
      </nav>

      <main className="main-content">
        <section className="hero">
          <div className="hero-badge">
            <span className="hero-badge-dot"></span>
            Cloudflare Incident Knowledge Base
          </div>

          <h1>
            Ask questions about
            <span> Cloudflare incidents</span>
          </h1>

          <p className="hero-description">
            Search technical incident reports 
          </p>
        </section>

        <section className="search-section">
          <form onSubmit={handleSubmit} className="search-box">
            <div className="search-input-wrapper">
              <svg
                className="search-icon"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
              >
                <circle cx="11" cy="11" r="7" />
                <path d="m20 20-3.5-3.5" />
              </svg>

              <input
                type="text"
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
                placeholder="Ask a question about an incident..."
                disabled={loading}
              />
            </div>

            <button
              type="submit"
              className="ask-button"
              disabled={loading || !question.trim()}
            >
              {loading ? (
                <>
                  <span className="button-spinner"></span>
                  Searching
                </>
              ) : (
                <>
                  Ask
                  <span className="arrow">→</span>
                </>
              )}
            </button>
          </form>

          {!answer && !loading && (
            <div className="examples">
              <span className="examples-label">Try asking:</span>

              <div className="example-list">
                {exampleQuestions.map((example) => (
                  <button
                    key={example}
                    type="button"
                    className="example-chip"
                    onClick={() => handleExampleClick(example)}
                  >
                    {example}
                  </button>
                ))}
              </div>
            </div>
          )}
        </section>

        {error && (
          <div className="error-card">
            <div className="error-icon">!</div>

            <div>
              <strong>Connection error</strong>
              <p>{error}</p>
            </div>
          </div>
        )}

        {loading && (
          <section className="loading-card">
            <div className="loader"></div>

            <div className="loading-content">
              <h3>Searching the knowledge base</h3>

              <p>
                Retrieving relevant chunks, reranking results, and generating
                a grounded answer...
              </p>
            </div>
          </section>
        )}

        {answer && !loading && (
          <section className="results">
            <article className="answer-card">
              <div className="card-header">
                <div>
                  <span className="card-eyebrow">Generated response</span>
                  <h2>Answer</h2>
                </div>

                <div className="grounded-badge">
                  <span>✓</span>
                  Grounded
                </div>
              </div>

              <div className="answer-content">
                <p>{answer}</p>
              </div>

              {citations.length > 0 && (
                <div className="answer-footer">
                  <span>
                    Based on {citations.length}{' '}
                    {citations.length === 1 ? 'source' : 'sources'}
                  </span>

                  <div className="citation-badges">
                    {citations.map((citation) => (
                      <span
                        key={citation.number}
                        className="mini-citation"
                      >
                        {citation.number}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </article>

            {citations.length > 0 && (
              <section className="sources-section">
                <div className="section-heading">
                  <div>
                    <span className="card-eyebrow">Retrieved evidence</span>
                    <h2>Sources</h2>
                  </div>

                  <span className="source-count">
                    {citations.length}{' '}
                    {citations.length === 1 ? 'source' : 'sources'}
                  </span>
                </div>

                <div className="source-list">
                  {citations.map((citation) => (
                    <a
                      key={citation.number}
                      href={citation.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="source-card"
                    >
                      <div className="source-number">
                        {citation.number}
                      </div>

                      <div className="source-content">
                        <h3>{citation.title}</h3>

                        {citation.section && (
                          <p>{citation.section}</p>
                        )}

                        <span className="source-link">
                          View incident report
                          <span>↗</span>
                        </span>
                      </div>
                    </a>
                  ))}
                </div>
              </section>
            )}
          </section>
        )}
      </main>

      <footer>
        <p>
          Powered by Cloudflare
        </p>
      </footer>
    </div>
  )
}

export default App