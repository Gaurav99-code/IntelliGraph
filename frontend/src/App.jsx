import { useEffect, useState } from 'react'
import './App.css'
import Uploader from './Uploader'
import Chat from './Chat'
import GraphPanel from './GraphPanel'
import { deleteDocument, getDocuments, getGraph, queryKnowledgeBase, uploadDocuments } from './api'

const WELCOME = {
  role: 'a',
  plain: 'Upload documents above, then ask a broad question (routed to topic communities) or a specific one (routed to graph paths). The graph on the right highlights what was used.',
}

export default function App() {
  const [focus, setFocus] = useState({ kind: 'reset' })
  const [msgs, setMsgs] = useState([WELCOME])
  const [docs, setDocs] = useState([])
  const [graph, setGraph] = useState({ nodes: [], edges: [] })
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [deletingId, setDeletingId] = useState(null)

  useEffect(() => {
    Promise.all([getDocuments(), getGraph()])
      .then(([documentResponse, graphResponse]) => {
        setDocs(documentResponse.documents)
        setGraph(graphResponse)
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false))
  }, [])

  const ingest = async (files) => {
    setError('')
    try {
      const response = await uploadDocuments(files)
      setDocs((current) => [...current, ...response.documents])
      setGraph(response.graph)
      if (response.documents[0]) setFocus({ kind: 'node', id: `document:${response.documents[0].id}` })
    } catch (err) {
      setError(err.message)
    }
  }

  const removeDocument = async (documentId) => {
    if (!window.confirm('Remove this document and its graph data?')) return
    setError('')
    setDeletingId(documentId)
    try {
      await deleteDocument(documentId)
      const [documentResponse, graphResponse] = await Promise.all([getDocuments(), getGraph()])
      setDocs(documentResponse.documents)
      setGraph(graphResponse)
      setFocus({ kind: 'reset' })
    } catch (err) {
      setError(err.message)
    } finally {
      setDeletingId(null)
    }
  }

  const ask = async (question) => {
    const id = Date.now()
    setError('')
    setMsgs((current) => [...current, { role: 'u', text: question }, { role: 'a', id, typing: true }])
    try {
      const result = await queryKnowledgeBase(question)
      setMsgs((current) => current.map((message) => (message.id === id ? { role: 'a', result } : message)))
      const evidenceEdges = result.graph_paths.flat()
      const evidenceNodes = [...new Set(evidenceEdges.flatMap((edge) => [edge.source, edge.target]))]
      setFocus({ kind: 'evidence', edgeIds: evidenceEdges.map((edge) => edge.id), nodeIds: evidenceNodes })
    } catch (err) {
      setMsgs((current) => current.map((message) => (message.id === id ? { role: 'a', plain: err.message } : message)))
      setError(err.message)
    }
  }

  return (
    <div className="app">
      <header>
        <h1>GraphRAG Knowledge Base</h1>
        <span>Topic-augmented knowledge graph</span>
        <div className={'pill ' + (error ? 'bad' : '')}>{loading ? 'Connecting…' : error ? 'Backend unavailable' : 'Backend connected'}</div>
      </header>
      {error && <div className="error">{error}</div>}
      <main>
        <section className="left">
          <Uploader docs={docs} onFiles={ingest} onSelect={(id) => setFocus({ kind: 'node', id: `document:${id}` })} onDelete={removeDocument} deletingId={deletingId} />
          <Chat msgs={msgs} onAsk={ask} />
        </section>
        <section className="right">
          <GraphPanel focus={focus} setFocus={setFocus} graph={graph} />
        </section>
      </main>
    </div>
  )
}
