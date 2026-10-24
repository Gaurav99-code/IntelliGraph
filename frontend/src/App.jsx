import { useEffect, useRef, useState } from 'react'
import './App.css'
import Uploader from './Uploader'
import Chat from './Chat'
import GraphPanel from './GraphPanel'
import LogViewer from './LogViewer'
import { deleteDocument, getDocuments, getGraph, getInfrastructure, getLogs, logClientEvent, queryKnowledgeBase, uploadDocuments } from './api'

const graphId = (value) => {
  if (typeof value === 'string' || typeof value === 'number') return String(value).trim() || null
  if (value && typeof value === 'object') return graphId(value.id)
  return null
}

const validGraphEdges = (graphPaths) => (Array.isArray(graphPaths) ? graphPaths : [])
  .flatMap((path) => Array.isArray(path) ? path : [])
  .filter((edge) => edge && typeof edge === 'object')
  .map((edge) => ({
    edge,
    edgeId: graphId(edge.id),
    sourceId: graphId(edge.source),
    targetId: graphId(edge.target),
  }))
  .filter(({ edgeId, sourceId, targetId }) => edgeId || sourceId || targetId)

const WELCOME = {
  role: 'a',
  welcome: true,
}

export default function App() {
  const [focus, setFocus] = useState({ kind: 'reset' })
  const [msgs, setMsgs] = useState([WELCOME])
  const [docs, setDocs] = useState([])
  const [graph, setGraph] = useState({ nodes: [], edges: [] })
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [deletingId, setDeletingId] = useState(null)
  const [infrastructure, setInfrastructure] = useState(null)
  const [showLogs, setShowLogs] = useState(false)
  const [logState, setLogState] = useState({ logs: { backend: [], frontend: [] }, loading: false, error: '' })
  const [fullscreenSection, setFullscreenSection] = useState(null)
  const researchRef = useRef(null)
  const graphRef = useRef(null)

  useEffect(() => {
    void logClientEvent('info', 'frontend_ready')
    const syncFullscreenState = () => {
      if (document.fullscreenElement === researchRef.current) setFullscreenSection('research')
      else if (document.fullscreenElement === graphRef.current) setFullscreenSection('graph')
      else setFullscreenSection(null)
    }
    document.addEventListener('fullscreenchange', syncFullscreenState)
    return () => document.removeEventListener('fullscreenchange', syncFullscreenState)
  }, [])

  const toggleFullscreen = async (section) => {
    const element = section === 'research' ? researchRef.current : graphRef.current
    if (!element) return
    try {
      if (fullscreenSection === section && document.fullscreenElement !== element) {
        setFullscreenSection(null)
      } else if (document.fullscreenElement === element) {
        await document.exitFullscreen()
        setFullscreenSection(null)
      }
      else if (document.fullscreenElement) {
        await document.exitFullscreen()
        setFullscreenSection(section)
        await element.requestFullscreen()
      } else {
        // Keep a CSS fallback for embedded browsers that block the Fullscreen API.
        setFullscreenSection(section)
        if (element.requestFullscreen) await element.requestFullscreen()
      }
    } catch {
      // The fixed-position CSS mode remains usable even when native fullscreen is denied.
      setFullscreenSection(section)
    }
  }

  const extractionLabel = () => {
    const counts = infrastructure?.extraction_method_counts || {}
    if (counts.llm && counts.heuristic) return 'LLM + heuristic fallback'
    if (counts.llm) return 'LLM extraction'
    return 'Heuristic fallback'
  }

  const loadLogs = async (source = 'all') => {
    setLogState((current) => ({ ...current, loading: true, error: '' }))
    try {
      const response = await getLogs(source)
      setLogState({ logs: response.logs || { backend: [], frontend: [] }, loading: false, error: '' })
    } catch (err) {
      setLogState((current) => ({ ...current, loading: false, error: err.message }))
    }
  }

  const openLogs = () => {
    setShowLogs(true)
    void loadLogs('all')
  }

  useEffect(() => {
    Promise.all([getDocuments(), getGraph(), getInfrastructure()])
      .then(([documentResponse, graphResponse, infrastructureResponse]) => {
        setDocs(documentResponse.documents)
        setGraph(graphResponse)
        setInfrastructure(infrastructureResponse)
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false))
  }, [])

  const ingest = async (files) => {
    setError('')
    void logClientEvent('info', 'document_upload_started', { file_count: files.length })
    try {
      const response = await uploadDocuments(files)
      setDocs((current) => [...current, ...response.documents])
      setGraph(response.graph)
      setInfrastructure(response.backends)
      if (response.documents[0]) setFocus({ kind: 'node', id: `document:${response.documents[0].id}` })
    } catch (err) {
      void logClientEvent('error', 'document_upload_failed', { message: err.message })
      setError(err.message)
    }
  }

  const removeDocument = async (documentId) => {
    if (!window.confirm('Remove this document and its graph data?')) return
    setError('')
    setDeletingId(documentId)
    try {
      await deleteDocument(documentId)
      const [documentResponse, graphResponse, infrastructureResponse] = await Promise.all([getDocuments(), getGraph(), getInfrastructure()])
      setDocs(documentResponse.documents)
      setGraph(graphResponse)
      setInfrastructure(infrastructureResponse)
      setFocus({ kind: 'reset' })
    } catch (err) {
      void logClientEvent('error', 'document_delete_failed', { message: err.message })
      setError(err.message)
    } finally {
      setDeletingId(null)
    }
  }

  const ask = async (question) => {
    const id = Date.now()
    setError('')
    setMsgs((current) => [...current, { role: 'u', text: question }, { role: 'a', id, typing: true }])
    void logClientEvent('info', 'query_started', { question_length: String(question).length })
    try {
      const result = await queryKnowledgeBase(question)
      setMsgs((current) => current.map((message) => (message.id === id ? { role: 'a', result, question } : message)))
      const evidence = validGraphEdges(result?.graph_paths)
      const evidenceNodes = [...new Set(evidence.flatMap(({ sourceId, targetId }) => [sourceId, targetId].filter(Boolean)))]
      const edgeIds = [...new Set(evidence.map(({ edgeId }) => edgeId).filter(Boolean))]
      setFocus(edgeIds.length || evidenceNodes.length ? { kind: 'evidence', edgeIds, nodeIds: evidenceNodes } : { kind: 'reset' })
    } catch (err) {
      void logClientEvent('error', 'query_failed', { message: err.message })
      setMsgs((current) => current.map((message) => (message.id === id ? { role: 'a', plain: err.message } : message)))
      setError(err.message)
    }
  }

  return (
    <div className="app">
      <header>
        <h1 style={{"color":"#748bfd"}}>IntelliGraph</h1>
        <span>Topic-augmented knowledge graph</span>
          <div className="header-actions">
            <button type="button" className="logs-button" onClick={openLogs}><span aria-hidden="true">◉</span> See logs</button>
            <div className={'pill ' + (error || infrastructure?.vector?.available === false ? 'bad' : '')}>{loading ? 'Connecting…' : error ? 'Backend unavailable' : `${extractionLabel()} · ${infrastructure?.graph?.available ? 'Vector + Neo4j' : infrastructure?.vector?.available ? 'Vector + JSON graph' : 'JSON fallback'}`}</div>
          </div>
      </header>
      {error && <div className="error">{error}</div>}
      <main>
        <section className={'left panel' + (fullscreenSection === 'research' ? ' is-fullscreen' : '')} ref={researchRef}>
          <div className="panel-toolbar">
            <div>
              <div className="panel-kicker">Research workspace</div>
              <h2>Ask questions, inspect evidence</h2>
            </div>
            <button type="button" className="panel-action" onClick={() => toggleFullscreen('research')} aria-label={fullscreenSection === 'research' ? 'Exit research fullscreen' : 'Open research fullscreen'}>
              <span aria-hidden="true">{fullscreenSection === 'research' ? '↙' : '⛶'}</span>{fullscreenSection === 'research' ? 'Exit' : 'Expand'}
            </button>
          </div>
          <Uploader docs={docs} onFiles={ingest} onSelect={(id) => setFocus({ kind: 'node', id: `document:${id}` })} onDelete={removeDocument} deletingId={deletingId} />
          <Chat msgs={msgs} onAsk={ask} graph={graph} infrastructure={infrastructure} docs={docs} onFocus={setFocus} />
        </section>
        <section className={'right panel' + (fullscreenSection === 'graph' ? ' is-fullscreen' : '')} ref={graphRef}>
          <div className="panel-toolbar graph-toolbar">
            <div>
              <div className="panel-kicker">Knowledge graph</div>
              <h2>Explore connected concepts</h2>
            </div>
            <button type="button" className="panel-action" onClick={() => toggleFullscreen('graph')} aria-label={fullscreenSection === 'graph' ? 'Exit graph fullscreen' : 'Open graph fullscreen'}>
              <span aria-hidden="true">{fullscreenSection === 'graph' ? '↙' : '⛶'}</span>{fullscreenSection === 'graph' ? 'Exit' : 'Expand'}
            </button>
          </div>
          <div className="graph-host"><GraphPanel focus={focus} setFocus={setFocus} graph={graph} /></div>
        </section>
      </main>
      <LogViewer open={showLogs} onClose={() => setShowLogs(false)} onRefresh={loadLogs} logs={logState.logs} loading={logState.loading} error={logState.error} />
    </div>
  )
}
