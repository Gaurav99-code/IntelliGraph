import { useState } from 'react'

export default function LogViewer({ open, onClose, onRefresh, logs, loading, error }) {
  const [source, setSource] = useState('all')

  if (!open) return null
  const visibleLogs = source === 'all'
    ? [...(logs.backend || []).map((line) => `[backend] ${line}`), ...(logs.frontend || []).map((line) => `[frontend] ${line}`)]
    : logs[source] || []

  return (
    <div className="log-overlay" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose() }}>
      <section className="log-modal" role="dialog" aria-modal="true" aria-labelledby="log-title">
        <div className="log-modal-header">
          <div>
            <div className="panel-kicker">Developer tools</div>
            <h2 id="log-title">Application logs</h2>
            <p>Recent local activity from the backend and frontend.</p>
          </div>
          <button type="button" className="log-close" onClick={onClose} aria-label="Close logs">×</button>
        </div>
        <div className="log-toolbar">
          <div className="log-tabs" role="tablist" aria-label="Log source">
            {['all', 'backend', 'frontend'].map((tab) => <button type="button" key={tab} className={'log-tab' + (source === tab ? ' active' : '')} onClick={() => { setSource(tab); onRefresh(tab) }}>{tab}</button>)}
          </div>
          <button type="button" className="panel-action" onClick={() => onRefresh(source)} disabled={loading}>{loading ? 'Refreshing…' : '↻ Refresh'}</button>
        </div>
        {error && <div className="log-error">{error}</div>}
        <pre className="log-content">{visibleLogs.length ? visibleLogs.join('\n') : loading ? 'Loading logs…' : 'No log entries yet.'}</pre>
        <div className="log-modal-footer">Logs are stored locally in <code>logs/backend.log</code> and <code>logs/frontend.log</code>.</div>
      </section>
    </div>
  )
}
