import { useState } from 'react'
import './App.css'

const API_URL = "http://127.0.0.1:8000/query"

const exampleQuestions = [
  'How long did the route leak incident last?',
  'What caused the major Cloudflare outage?',
  'How did Cloudflare mitigate the incident?',
]

function App() {
  const [question, setQuestion] = useState('')
  const [answer, setAnswer] = useState('')
  const [citations, setCitations] = useState([])
  const [conversation, setConversation] = useState([])
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
    let answerText = ''
    let citationList = []

    try {
      const response = await fetch(API_URL, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          question: trimmedQuestion,
          history: conversation.slice(-3).flatMap((turn) => [
            { role: 'user', content: turn.question },
            { role: 'assistant', content: turn.answer },
          ]),
        }),
      })

      if (!response.ok) {
        throw new Error(`Server responded with status ${response.status}`)
      }

      const reader = response.body.getReader()
      const decoder = new TextDecoder('utf-8')
      let done = false
      let buffer = ''

      while (!done) {
        const { value, done: readerDone } = await reader.read()
        done = readerDone
        if (value) {
          buffer += decoder.decode(value, { stream: true })
          const lines = buffer.split('\n')
          buffer = lines.pop() || ''

          for (const line of lines) {
            if (line.startsWith('data: ')) {
              const dataStr = line.slice(6)
              try {
                const parsed = JSON.parse(dataStr)
                if (parsed.type === 'content') {
                  answerText += parsed.text
                  setAnswer(answerText)
                } else if (parsed.type === 'citations') {
                  citationList = parsed.citations || []
                  setCitations(citationList)
                }
              } catch (e) {
                console.error('Error parsing SSE data', e)
              }
            }
          }
        }
      }

      setConversation((previous) => [
        ...previous,
        {
          question: trimmedQuestion,
          answer: answerText,
          citations: citationList,
        },
      ])
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

  function startNewConversation() {
    setQuestion('')
    setAnswer('')
    setCitations([])
    setConversation([])
    setError('')
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

          <button
            type="button"
            className="new-conversation-button"
            onClick={startNewConversation}
            disabled={loading || conversation.length === 0}
          >
            New conversation
          </button>
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

        {loading && !answer && (
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

        {conversation.length > 1 && (
          <section className="conversation-history" aria-label="Conversation history">
            <div className="history-heading">
              <div>
                <span className="card-eyebrow">Earlier in this conversation</span>
                <h2>Previous answers</h2>
              </div>
              <span className="history-count">{conversation.length - 1} {conversation.length === 2 ? 'turn' : 'turns'}</span>
            </div>

            <div className="history-list">
              {conversation.slice(0, -1).map((turn, index) => (
                <details className="history-turn" key={`${turn.question}-${index}`}>
                  <summary>{turn.question}</summary>
                  <div className="history-answer">
                    <span className="history-label">Assistant</span>
                    <p>{turn.answer}</p>
                  </div>
                </details>
              ))}
            </div>
          </section>
        )}

        {answer && (
          <section className="results">
            <article className="answer-card">
              <div className="card-header">
                <div>
                  <span className="card-eyebrow">Generated response</span>
                  <h2>{loading ? 'Answering' : 'Answer'}</h2>
                </div>

                <div className={`grounded-badge ${loading ? 'is-streaming' : ''}`}>
                  <span>{loading ? '●' : '✓'}</span>
                  {loading ? 'Streaming' : 'Grounded'}
                </div>
              </div>

              <div className="active-question">
                <span className="history-label">You asked</span>
                <p>{question}</p>
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