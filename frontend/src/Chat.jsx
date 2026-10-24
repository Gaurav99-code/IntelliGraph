import { useEffect, useRef, useState } from 'react'
import { getSuggestions } from './data'

const asArray = (value) => Array.isArray(value) ? value : []
const QUERY_STOPWORDS = new Set(['about', 'after', 'again', 'also', 'are', 'because', 'before', 'being', 'between', 'could', 'does', 'during', 'from', 'have', 'how', 'into', 'is', 'its', 'main', 'more', 'most', 'other', 'over', 'same', 'some', 'such', 'than', 'that', 'their', 'there', 'these', 'they', 'this', 'those', 'through', 'under', 'was', 'were', 'what', 'when', 'where', 'which', 'while', 'who', 'why', 'will', 'with', 'would', 'you', 'your', 'and', 'but', 'for', 'not', 'our', 'can', 'all', 'any', 'out', 'too'])

const humanizeId = (value) => String(value || 'Unknown')
  .replace(/^(entity|document|topic):/i, '')
  .replace(/[-_]+/g, ' ')
  .replace(/\b\w/g, (letter) => letter.toUpperCase())

function nodeLabel(value, graph) {
  const id = typeof value === 'object' ? value?.id : value
  const node = asArray(graph?.nodes).find((candidate) => candidate?.id === id)
  return node?.label || (typeof value === 'object' ? value?.label : null) || humanizeId(id)
}

function graphId(value) {
  if (typeof value === 'string' || typeof value === 'number') return String(value)
  return value?.id ? graphId(value.id) : null
}

function searchTerms(question) {
  return [...new Set((question || '').toLowerCase().match(/[a-z][a-z0-9_-]{2,}/g) || [])]
    .filter((term) => !QUERY_STOPWORDS.has(term))
}

function termCount(text, terms) {
  const lower = String(text || '').toLowerCase()
  return terms.reduce((count, term) => count + (lower.includes(term) ? 1 : 0), 0)
}

function sourceExcerpt(text, terms) {
  const value = String(text || '').trim()
  if (!value) return ''
  const paragraphs = value.split(/\n\s*\n/).map((paragraph) => paragraph.trim()).filter(Boolean)
  const sentences = paragraphs.flatMap((paragraph) => paragraph.split(/(?<=[.!?])\s+/).filter(Boolean))
  const best = (sentences.length ? sentences : paragraphs.length ? paragraphs : [value])
    .sort((left, right) => termCount(right, terms) - termCount(left, terms))[0]
  if (best.length <= 520) return best
  const lower = best.toLowerCase()
  const firstMatch = terms.map((term) => lower.indexOf(term)).filter((index) => index >= 0).sort((a, b) => a - b)[0] ?? 0
  const start = Math.max(0, firstMatch - 180)
  const end = Math.min(best.length, start + 520)
  return `${start > 0 ? '…' : ''}${best.slice(start, end).trim()}${end < best.length ? '…' : ''}`
}

function HighlightedText({ text, terms }) {
  if (!text || !terms.length) return <>{text}</>
  const pattern = terms.map((term) => term.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('|')
  return String(text).split(new RegExp(`(${pattern})`, 'gi')).map((part, index) => (
    terms.includes(part.toLowerCase()) ? <mark key={index}>{part}</mark> : <span key={index}>{part}</span>
  ))
}

function SourceCard({ citation, index, question, onFocus }) {
  const terms = searchTerms(question)
  const text = citation.text || ''
  const matchedTerms = terms.filter((term) => text.toLowerCase().includes(term))
  const excerpt = sourceExcerpt(text, terms)
  return (
    <div className="citation">
      <div className="citation-head"><b>Source {index + 1} · {citation.document_name || 'Unnamed document'}</b>{citation.score !== undefined && <span className="src">score {citation.score}</span>}</div>
      {citation.chunk_id && <div className="src">Chunk: {citation.chunk_id}</div>}
      {matchedTerms.length > 0 && <div className="matched-terms">Matched: {matchedTerms.join(', ')}</div>}
      {excerpt && <div className="citation-text"><HighlightedText text={excerpt} terms={matchedTerms} /></div>}
      {text.length > excerpt.length && <details className="full-chunk"><summary>View full chunk</summary><div className="citation-text"><HighlightedText text={text} terms={matchedTerms} /></div></details>}
      {citation.document_id && <button type="button" className="source-focus" onClick={() => onFocus?.({ kind: 'node', id: `document:${citation.document_id}` })}>Focus document in graph</button>}
    </div>
  )
}

function methodLabel(result, infrastructure) {
  if (result.answer_method === 'llm') return infrastructure?.llm_provider || 'LLM'
  if (result.answer_method === 'extractive') return 'Extractive fallback'
  return result.answer_method || null
}

function WelcomeCard({ hasDocuments }) {
  return (
    <div className="welcome-card">
      <div className="welcome-icon" aria-hidden="true">✦</div>
      <div className="welcome-eyebrow">{hasDocuments ? 'Workspace ready' : 'Welcome to IntelliGraph'}</div>
      <h2>{hasDocuments ? 'Start researching your documents' : 'Turn documents into answers'}</h2>
      <p>{hasDocuments ? 'Ask a question below to trace an answer back to its source text and graph relationships.' : 'Upload PDFs to build a searchable knowledge graph, then ask questions with grounded evidence.'}</p>
      <div className="welcome-steps">
        <span><b>1</b> Upload PDFs</span><span><b>2</b> Ask a question</span><span><b>3</b> Explore evidence</span>
      </div>
    </div>
  )
}

function Message({ m, graph, infrastructure, onFocus, hasDocuments }) {
  if (m.role === 'u') return <div className="m u">{m.text}</div>
  if (m.typing) return <div className="m a"><span className="src">Routing query…</span></div>
  if (m.welcome) return <WelcomeCard hasDocuments={hasDocuments} />
  if (m.plain) return <div className="m a"><span className="route l">Demo</span><div>{m.plain}</div></div>
  const result = m.result
  if (!result) return null
  const sources = asArray(result.sources)
  const citations = asArray(result.citations).length
    ? asArray(result.citations)
    : sources.map((source, index) => ({ id: `source-${index}`, ...source }))
  const graphPaths = asArray(result.graph_paths)
  const graphEdges = [...new Map(graphPaths.flatMap((path) => Array.isArray(path) ? path : [])
    .filter((edge) => edge && typeof edge === 'object')
    .map((edge, index) => [edge.id || `${graphId(edge.source) || 'source'}|${edge.label || edge.relation || 'related'}|${graphId(edge.target) || 'target'}|${index}`, edge])).values()]
  const method = methodLabel(result, infrastructure)
  const hasConfidence = result.confidence !== undefined && result.confidence !== null && Number.isFinite(Number(result.confidence))
  const question = result.question || m.question || ''
  return (
    <div className="m a">
      <span className={'route ' + (result.route === 'thematic' ? 'g' : 'l')}>{result.route === 'thematic' ? 'GLOBAL · Topic communities' : 'LOCAL · Graph traversal'}</span>
      <div className="trace">Router → {result.route || 'factual'} retrieval → {sources.length} grounded source{sources.length === 1 ? '' : 's'}</div>
      {(method || hasConfidence) && <div className="answer-meta">{method && <>Method: <b>{method}</b></>}{method && hasConfidence && ' · '}{hasConfidence && <>Confidence: <b>{Number(result.confidence).toFixed(2)}</b></>}</div>}
      {result.insufficient_evidence === true && <div className="evidence-warning">Insufficient evidence in the uploaded documents.</div>}
      <div>{result.answer}</div>
      {asArray(result.topics).length > 0 && <ol>{asArray(result.topics).slice(0, 6).map((topic) => <li key={topic.label}><b>{topic.label}</b> · score {topic.score}</li>)}</ol>}
      <div className="evidence-section">
        <div className="evidence-title">Sources</div>
        {citations.length ? <div className="evidence-list">{citations.map((citation, index) => (
          <SourceCard key={citation.id || `${citation.document_name || 'source'}-${index}`} citation={citation} index={index} question={question} onFocus={onFocus} />
        ))}</div> : <div className="src evidence-empty">No matching document evidence</div>}
      </div>
      <div className="evidence-section">
        <div className="evidence-title">Graph evidence</div>
        {graphEdges.length ? <div className="evidence-list">{graphEdges.map((edge, index) => (
          <button type="button" className="graph-edge" key={edge.id || `graph-edge-${index}`} onClick={() => onFocus?.({ kind: 'evidence', edgeIds: [edge.id].filter(Boolean), nodeIds: [graphId(edge.source), graphId(edge.target)].filter(Boolean) })}>
            <div><b>{nodeLabel(edge.source, graph)}</b> <span className="graph-edge-label">— {edge.label || edge.relation || 'related to'} →</span> <b>{nodeLabel(edge.target, graph)}</b></div>
            {edge.evidence && <div className="citation-text">Evidence: {edge.evidence}</div>}
            {(edge.document_id || edge.chunk_id) && <div className="src">{edge.document_id && `Document: ${edge.document_id}`}{edge.document_id && edge.chunk_id && ' · '}{edge.chunk_id && `Chunk: ${edge.chunk_id}`}</div>}
            <span className="edge-action">Focus this relationship</span>
          </button>
        ))}</div> : <div className="src evidence-empty">No graph evidence returned</div>}
      </div>
    </div>
  )
}

export default function Chat({ msgs, onAsk, graph, infrastructure, docs, onFocus }) {
  const [q, setQ] = useState('')
  const box = useRef()
  const suggestions = getSuggestions(docs)
  useEffect(() => { box.current.scrollTop = box.current.scrollHeight }, [msgs])
  const submit = (e) => { e.preventDefault(); if (q.trim()) { onAsk(q); setQ('') } }
  return (
    <>
      <div className="chat" ref={box}>
        {msgs.map((m, i) => <Message key={i} m={m} graph={graph} infrastructure={infrastructure} onFocus={onFocus} hasDocuments={asArray(docs).length > 0} />)}
      </div>
      <div className="sug">
        {suggestions.map((s) => <button key={s} className="chip" onClick={() => onAsk(s)}>{s}</button>)}
      </div>
      <form onSubmit={submit}>
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Ask a thematic or factual question…" />
        <button className="send">Ask</button>
      </form>
    </>
  )
}
