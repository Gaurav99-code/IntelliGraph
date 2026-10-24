import { useRef, useState } from 'react'

export default function Uploader({ docs, onFiles, onSelect, onDelete, deletingId }) {
  const input = useRef()
  const [over, setOver] = useState(false)
  return (
    <div className="up">
      <div
        className={'drop' + (over ? ' on' : '')}
        onClick={() => input.current.click()}
        onDragOver={(e) => { e.preventDefault(); setOver(true) }}
        onDragLeave={() => setOver(false)}
        onDrop={(e) => { e.preventDefault(); setOver(false); onFiles([...e.dataTransfer.files]) }}
      >
        Drop PDFs / text here or click to upload
        <input ref={input} type="file" accept=".pdf,.txt,.md,.csv,.json" multiple hidden onChange={(e) => { onFiles([...e.target.files]); e.target.value = '' }} />
      </div>
      <div className="docs">
        {docs.map((d) => (
          <div key={d.id} className="doc" onClick={() => onSelect(d.id)}>
            <span>📄</span>
            <div className="dn">
              <b>{d.name}</b>
              {d.p != null && <div className="bar"><div style={{ width: d.p + '%' }} /></div>}
            </div>
            <i>{d.status || `${d.entities} entities`}</i>
            <button
              type="button"
              className="remove"
              aria-label={`Remove ${d.name}`}
              title="Remove document"
              disabled={deletingId === d.id}
              onClick={(e) => { e.stopPropagation(); onDelete(d.id) }}
            >
              {deletingId === d.id ? '…' : '×'}
            </button>
          </div>
        ))}
      </div>
    </div>
  )
}
