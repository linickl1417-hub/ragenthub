import { useState } from 'react'
import { chat, type ChatResponse } from '../api'

export default function Chat({ domain }: { domain: string }) {
  const [q, setQ] = useState('')
  const [resp, setResp] = useState<ChatResponse | null>(null)
  const [loading, setLoading] = useState(false)

  async function ask() {
    setLoading(true)
    try {
      setResp(await chat(q, domain))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div>
      <textarea value={q} onChange={e => setQ(e.target.value)} rows={3}
        style={{ width: '100%', padding: 8 }} placeholder="输入问题…" />
      <button onClick={ask} disabled={loading}
        style={{ marginTop: 8, padding: '8px 20px', background: '#2b6cb0', color: '#fff', border: 0 }}>
        {loading ? '思考中…' : '提问'}
      </button>

      {resp && (
        <div style={{ marginTop: 16 }}>
          <div style={{ background: '#fff', padding: 16, borderRadius: 6, border: '1px solid #e2e8f0', whiteSpace: 'pre-wrap' }}>
            {resp.answer}
          </div>
          <div style={{ marginTop: 12, background: '#ebf8ff', padding: 12, borderRadius: 4, fontSize: 13 }}>
            <b>引用 {resp.citations.length} 条</b>
            <ul>{resp.citations.map((c, i) => (
              <li key={i}>{c.source}（相似度 {c.score}）</li>
            ))}</ul>
            <div style={{ color: '#718096' }}>
              guard={resp.agent_trace.guard_action} · {resp.latency_ms}ms · llm={resp.agent_trace.llm_provider} · audit#{resp.audit_id}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
