const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000').replace(/\/$/, '')

async function request(path, options = {}) {
  const response = await fetch(`${API_BASE_URL}${path}`, options)
  const body = await response.json().catch(() => null)
  if (!response.ok) {
    const error = new Error(body?.detail || `Request failed (${response.status})`)
    error.status = response.status
    throw error
  }
  return body
}

export function getDocuments() {
  return request('/api/documents')
}

export function getGraph() {
  return request('/api/graph')
}

export function getInfrastructure() {
  return request('/api/infrastructure').catch((error) => {
    // Older locally running backends do not expose this endpoint yet, but
    // /api/health includes the same backend status needed by the header.
    if (error.status !== 404) throw error
    return request('/api/health').then((body) => body?.backends || {})
  })
}

export function uploadDocuments(files) {
  const form = new FormData()
  files.forEach((file) => form.append('files', file))
  return request('/api/documents/upload', { method: 'POST', body: form })
}

export function deleteDocument(documentId) {
  return request(`/api/documents/${encodeURIComponent(documentId)}`, { method: 'DELETE' })
}

export function queryKnowledgeBase(question, topK = 5) {
  return request('/api/query', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question, top_k: topK }),
  })
}

export function getLogs(source = 'all', limit = 250) {
  return request(`/api/logs?source=${encodeURIComponent(source)}&limit=${limit}`)
}

export function logClientEvent(level, message, context = {}) {
  return request('/api/logs/client', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ level, message, context }),
  })
}

export { API_BASE_URL }
