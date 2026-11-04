const API = '/api/v1'

export interface Citation { content: string; source: string; score: number }
export interface ChatResponse {
  answer: string
  citations: Citation[]
  agent_trace: { guard_action: string; retrieved: number; llm_provider: string; cache_hit?: boolean }
  audit_id: number
  latency_ms: number
}

export async function chat(question: string, domain: string): Promise<ChatResponse> {
  const r = await fetch(`${API}/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question, domain, user_id: 'web-console' })
  })
  return r.json()
}

export async function listDocuments(domain?: string) {
  const qs = domain ? `?domain=${domain}` : ''
  const r = await fetch(`${API}/documents${qs}`)
  return r.json()
}

export async function listAudits(limit = 50) {
  const r = await fetch(`${API}/audit/recent?limit=${limit}`)
  return r.json()
}

export async function uploadDocument(file: File, domain: string) {
  const fd = new FormData()
  fd.append('file', file)
  fd.append('domain', domain)
  const r = await fetch(`${API}/documents`, { method: 'POST', body: fd })
  return r.json()
}
