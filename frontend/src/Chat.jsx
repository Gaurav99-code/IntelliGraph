import { useEffect, useRef, useState } from 'react'
import { SUGGESTIONS } from './data'

function Message({ m }) {
  if (m.role === 'u') return <div className="m u">{m.text}</div>
  if (m.typing) return <div className="m a"><span className="src">Routing query…</span></div>
  if (m.plain) return <div className="m a"><span className="route l">Demo</span><div>{m.plain}</div></div>
  const result = m.result
  if (!result) return null
  return (
    <div className="m a">
      <span className={'route ' + (result.route === 'thematic' ? 'g' : 'l')}>{result.route === 'thematic' ? 'GLOBAL · Topic communities' : 'LOCAL · Graph traversal'}</span>
      <div className="trace">Router → {result.route} retrieval → {result.sources.length} grounded source{result.sources.length === 1 ? '' : 's'}</div>
      <div>{result.answer}</div>
      {result.topics?.length > 0 && <ol>{result.topics.slice(0, 6).map((topic) => <li key={topic.label}><b>{topic.label}</b> · score {topic.score}</li>)}</ol>}
      <div className="src srcline">Sources: {result.sources.length ? result.sources.map((source) => source.document_name).join(', ') : 'No matching document evidence'}</div>
    </div>
  )
}

export default function Chat({ msgs, onAsk }) {
  const [q, setQ] = useState('')
  const box = useRef()
  useEffect(() => { box.current.scrollTop = box.current.scrollHeight }, [msgs])
  const submit = (e) => { e.preventDefault(); if (q.trim()) { onAsk(q); setQ('') } }
  return (
    <>
      <div className="chat" ref={box}>
        {msgs.map((m, i) => <Message key={i} m={m} />)}
      </div>
      <div className="sug">
        {SUGGESTIONS.map((s) => <button key={s} className="chip" onClick={() => onAsk(s)}>{s}</button>)}
      </div>
      <form onSubmit={submit}>
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Ask a thematic or factual question…" />
        <button className="send">Ask</button>
      </form>
    </>
  )
}
