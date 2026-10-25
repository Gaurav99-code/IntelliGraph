import { useState } from 'react'

const prettify = (value) => String(value || 'activity').replaceAll('_', ' ').replace(/\b\w/g, (letter) => letter.toUpperCase())

const formatTimestamp = (value) => {
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? String(value || '') : date.toLocaleString()
}

function legacyEvents(logs, source) {
  const lines = source === 'all'
    ? [...(logs.backend || []).map((line) => ({ line, source: 'backend' })), ...(logs.frontend || []).map((line) => ({ line, source: 'frontend' }))]
    : (logs[source] || []).map((line) => ({ line, source }))
  return lines.map(({ line, source: lineSource }, index) => {
    const match = String(line).match(/^(.*?) \| (\w+) \| [^|]+ \| (.*)$/)
    return {
      id: `legacy-${lineSource}-${index}`,
      timestamp: match?.[1] || '',
      source: lineSource,
      action: match?.[2]?.toLowerCase() || 'log_entry',
      message: match?.[3] || line,
      details: {},
    }
  })
}

export default function LogViewer({ open, onClose, onRefresh, logs, events = [], loading, error }) {
  const [source, setSource] = useState('all')

  if (!open) return null
  const visibleEvents = (events.length ? events : legacyEvents(logs, source))
    .filter((event) => source === 'all' || event.source === source)

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
        <div className="log-content">
          {visibleEvents.length ? <div className="log-list">{visibleEvents.map((event) => {
            const details = event.details && typeof event.details === 'object' ? event.details : {}
            const fileNames = details.file_names || (details.file_name ? [details.file_name] : [])
            return <article className="log-entry" key={event.id || `${event.timestamp}-${event.action}-${event.message}`}>
              <div className="log-entry-time">{formatTimestamp(event.timestamp)}</div>
              <div className="log-entry-main">
                <div className="log-entry-title"><span className={'log-source ' + event.source}>{event.source}</span><b>{prettify(event.action)}</b></div>
                <div className="log-entry-message">{event.message}</div>
                {fileNames.length > 0 && <div className="log-entry-files">File{fileNames.length > 1 ? 's' : ''}: {fileNames.join(', ')}</div>}
                {Object.entries(details).filter(([key]) => key !== 'file_names' && key !== 'file_name').length > 0 && <div className="log-entry-details">{Object.entries(details).filter(([key]) => key !== 'file_names' && key !== 'file_name').map(([key, value]) => <span key={key}><b>{prettify(key)}:</b> {Array.isArray(value) ? value.join(', ') : String(value)}</span>)}</div>}
              </div>
            </article>
          })}</div> : loading ? 'Loading logs…' : 'No log entries yet.'}
        </div>
        <div className="log-modal-footer">Activity is stored locally with timestamps in <code>logs/activity.jsonl</code>. Raw backend/frontend logs remain available in <code>logs/backend.log</code> and <code>logs/frontend.log</code>.</div>
      </section>
    </div>
  )
}
