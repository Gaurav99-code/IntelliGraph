import { useEffect, useRef, useState } from 'react'
import * as d3 from 'd3'

const TYPE_META = {
  document: { label: 'Documents', color: '#8a8880' },
  topic: { label: 'Topics', color: '#378ADD' },
  entity: { label: 'Entities', color: '#1D9E75' },
}

const idOf = (value) => (typeof value === 'object' ? value.id : value)
const edgeKey = (edge) => edge.id || `${idOf(edge.source)}|${edge.label}|${idOf(edge.target)}`
const colorOf = (node) => TYPE_META[node.type]?.color || '#8a8880'
const labelOf = (node) => TYPE_META[node.type]?.label || 'Graph'
const css = (value) => getComputedStyle(document.documentElement).getPropertyValue(value).trim()

function computeHighlight(focus, nodes, links) {
  if (!focus || focus.kind === 'reset') return null
  const nodeIds = new Set()
  const edgeIds = new Set()
  if (focus.kind === 'node') {
    nodeIds.add(focus.id)
    links.forEach((link) => {
      const source = idOf(link.source), target = idOf(link.target)
      if (source === focus.id || target === focus.id) {
        nodeIds.add(source)
        nodeIds.add(target)
        edgeIds.add(edgeKey(link))
      }
    })
  }
  if (focus.kind === 'evidence') {
    focus.nodeIds.forEach((id) => nodeIds.add(id))
    focus.edgeIds.forEach((id) => edgeIds.add(id))
  }
  if (focus.kind === 'type') {
    nodes.filter((node) => node.type === focus.type).forEach((node) => nodeIds.add(node.id))
    links.forEach((link) => {
      const source = idOf(link.source), target = idOf(link.target)
      if (nodeIds.has(source) && nodeIds.has(target)) edgeIds.add(edgeKey(link))
    })
  }
  return { nodes: nodeIds, edges: edgeIds, fit: [...nodeIds] }
}

export default function GraphPanel({ focus, setFocus, graph }) {
  const wrap = useRef()
  const canvasRef = useRef()
  const tip = useRef()
  const stateRef = useRef({})
  const [info, setInfo] = useState(null)

  useEffect(() => {
    const canvas = canvasRef.current
    const container = wrap.current
    if (!canvas || !container) return undefined
    const context = canvas.getContext('2d')
    const nodes = (graph.nodes || []).map((node) => ({ ...node, x: 0, y: 0, deg: 0 }))
    const links = (graph.edges || []).map((edge) => ({ ...edge, source: edge.source, target: edge.target }))
    const byId = Object.fromEntries(nodes.map((node) => [node.id, node]))
    links.forEach((link) => {
      if (byId[link.source]) byId[link.source].deg += 1
      if (byId[link.target]) byId[link.target].deg += 1
    })
    const state = { nodes, links, byId, transform: d3.zoomIdentity, width: 0, height: 0, dpr: window.devicePixelRatio || 1, highlight: null, selected: null, hovered: null }
    stateRef.current = state

    const radius = (node) => Math.max(6, Math.min(18, 6 + node.deg * 0.7))
    const draw = () => {
      if (!state.width) return
      const tx = css('--tx'), mut = css('--mut'), bg = css('--bg')
      const { transform, highlight } = state
      context.setTransform(state.dpr, 0, 0, state.dpr, 0, 0)
      context.clearRect(0, 0, state.width, state.height)
      context.translate(transform.x, transform.y)
      context.scale(transform.k, transform.k)

      links.forEach((link) => {
        const source = typeof link.source === 'object' ? link.source : byId[link.source]
        const target = typeof link.target === 'object' ? link.target : byId[link.target]
        if (!source || !target) return
        const on = !highlight || highlight.edges.has(edgeKey(link))
        context.globalAlpha = highlight ? (on ? 1 : 0.08) : 0.38
        context.strokeStyle = on && highlight ? '#e0457b' : mut
        context.lineWidth = on && highlight ? 3 : 1
        context.beginPath()
        context.moveTo(source.x, source.y)
        context.lineTo(target.x, target.y)
        context.stroke()
        if (on && (highlight || transform.k > 1.5)) {
          context.globalAlpha = 0.8
          context.fillStyle = on && highlight ? '#e0457b' : mut
          context.font = '10px system-ui'
          context.textAlign = 'center'
          context.fillText(link.label || 'related to', (source.x + target.x) / 2, (source.y + target.y) / 2 - 3)
        }
      })

      nodes.forEach((node) => {
        const on = !highlight || highlight.nodes.has(node.id)
        const radiusValue = radius(node)
        context.globalAlpha = on ? 1 : 0.12
        context.fillStyle = colorOf(node)
        context.beginPath()
        if (node.type === 'document') context.rect(node.x - radiusValue, node.y - radiusValue, radiusValue * 2, radiusValue * 2)
        else context.arc(node.x, node.y, radiusValue, 0, Math.PI * 2)
        context.fill()
        if (node === state.selected || node === state.hovered) {
          context.strokeStyle = tx
          context.lineWidth = 2
          context.stroke()
        }
        if (on && (highlight || transform.k > 0.95 || node.deg > 4 || node === state.hovered || node === state.selected)) {
          context.fillStyle = tx
          context.font = (highlight?.nodes.has(node.id) ? '600 ' : '') + '11px system-ui'
          context.textAlign = 'center'
          context.lineWidth = 3
          context.strokeStyle = bg
          context.strokeText(node.label, node.x, node.y + radiusValue + 12)
          context.fillText(node.label, node.x, node.y + radiusValue + 12)
        }
      })
      context.globalAlpha = 1
    }
    state.draw = draw

    const simulation = d3.forceSimulation(nodes)
      .force('links', d3.forceLink(links).id((node) => node.id).distance((link) => link.source?.type === 'document' || link.target?.type === 'document' ? 100 : 70).strength(0.35))
      .force('charge', d3.forceManyBody().strength(-230))
      .force('x', d3.forceX().strength(0.04))
      .force('y', d3.forceY().strength(0.05))
      .force('collision', d3.forceCollide((node) => 10 + node.deg * 0.5))
      .on('tick', draw)
    state.simulation = simulation

    const zoom = d3.zoom().scaleExtent([0.3, 4]).on('zoom', (event) => {
      state.transform = event.transform
      draw()
    })
    d3.select(canvas).call(zoom).on('dblclick.zoom', null)

    state.fit = (ids) => {
      const selected = ids.map((id) => byId[id]).filter(Boolean)
      if (!selected.length || !state.width || !state.height) return
      const x0 = d3.min(selected, (node) => node.x) - 60
      const x1 = d3.max(selected, (node) => node.x) + 60
      const y0 = d3.min(selected, (node) => node.y) - 60
      const y1 = d3.max(selected, (node) => node.y) + 60
      const scale = Math.max(0.6, Math.min(2.4, Math.min(state.width / (x1 - x0), state.height / (y1 - y0))))
      d3.select(canvas).transition().duration(650).call(zoom.transform, d3.zoomIdentity.translate(state.width / 2 - (scale * (x0 + x1)) / 2, state.height / 2 - (scale * (y0 + y1)) / 2).scale(scale))
    }

    const resize = () => {
      const bounds = container.getBoundingClientRect()
      state.width = bounds.width
      state.height = bounds.height
      canvas.width = bounds.width * state.dpr
      canvas.height = bounds.height * state.dpr
      canvas.style.width = `${bounds.width}px`
      canvas.style.height = `${bounds.height}px`
      if (!state.initialized) {
        state.initialized = true
        d3.select(canvas).call(zoom.transform, d3.zoomIdentity.translate(state.width / 2, state.height / 2).scale(1.05))
        setTimeout(() => state.fit(nodes.map((node) => node.id)), 400)
      }
      draw()
    }
    const observer = new ResizeObserver(resize)
    observer.observe(container)
    resize()

    return () => {
      simulation.stop()
      observer.disconnect()
    }
  }, [graph])

  useEffect(() => {
    const state = stateRef.current
    if (!state.nodes) return
    const highlight = computeHighlight(focus, state.nodes, state.links)
    state.highlight = highlight
    state.selected = focus?.kind === 'node' ? state.byId[focus.id] : null
    if (state.selected) {
      const neighbours = state.links.filter((link) => idOf(link.source) === focus.id || idOf(link.target) === focus.id).map((link) => ({
        link,
        out: idOf(link.source) === focus.id,
        node: state.byId[idOf(link.source) === focus.id ? idOf(link.target) : idOf(link.source)],
      }))
      setInfo({ node: state.selected, neighbours })
    } else {
      setInfo(null)
    }
    if (focus?.kind === 'reset') state.fit?.(state.nodes.map((node) => node.id))
    else if (highlight?.fit.length) state.fit?.(highlight.fit)
    state.draw?.()
  }, [focus])

  const pick = (event) => {
    const state = stateRef.current
    const bounds = canvasRef.current.getBoundingClientRect()
    return state.simulation?.find?.((event.clientX - bounds.left - state.transform.x) / state.transform.k, (event.clientY - bounds.top - state.transform.y) / state.transform.k, 16 / state.transform.k)
  }

  const onMove = (event) => {
    const state = stateRef.current
    const node = pick(event)
    state.hovered = node || null
    canvasRef.current.style.cursor = node ? 'pointer' : 'grab'
    if (node) {
      const bounds = canvasRef.current.getBoundingClientRect()
      tip.current.style.display = 'block'
      tip.current.textContent = `${node.label} · ${labelOf(node)}`
      tip.current.style.left = `${event.clientX - bounds.left + 12}px`
      tip.current.style.top = `${event.clientY - bounds.top + 12}px`
    } else {
      tip.current.style.display = 'none'
    }
    state.draw?.()
  }

  const legend = (type) => setFocus(focus?.kind === 'type' && focus.type === type ? { kind: 'reset' } : { kind: 'type', type })

  return (
    <div className="graph" ref={wrap}>
      <canvas ref={canvasRef} onMouseMove={onMove} onMouseLeave={() => { tip.current.style.display = 'none' }} onClick={(event) => { const node = pick(event); if (node) setFocus({ kind: 'node', id: node.id }) }} />
      <div className="tools">
        {Object.entries(TYPE_META).map(([type, meta]) => <button key={type} className={'leg' + (focus?.kind === 'type' && focus.type === type ? ' act' : '')} onClick={() => legend(type)}><span className="dot" style={{ background: meta.color }} />{meta.label}</button>)}
        <span className="sp" />
        <button className="leg" onClick={() => setFocus({ kind: 'reset' })}>Reset view</button>
      </div>
      <div className="tip" ref={tip} />
      {info && <div className="info"><h3>{info.node.label}</h3><div className="t">{labelOf(info.node)} · {info.neighbours.length} connections</div><ul>{info.neighbours.slice(0, 6).map((item, index) => <li key={index}>{item.out ? item.link.label || 'connects to' : `← ${item.link.label || 'connects to'}`} <b>{item.node?.label || 'unknown'}</b></li>)}</ul></div>}
    </div>
  )
}
