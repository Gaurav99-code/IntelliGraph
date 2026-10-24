const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000').replace(/\/$/, '')

async function request(path, options = {}) {
  const response = await fetch(`${API_BASE_URL}${path}`, options)
  const body = await response.json().catch(() => null)
  if (!response.ok) {
    throw new Error(body?.detail || `Request failed (${response.status})`)
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
  return request('/api/infrastructure')
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

export { API_BASE_URL }
