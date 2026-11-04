import { useState } from 'react'
import Chat from './pages/Chat'
import Documents from './pages/Documents'
import Audit from './pages/Audit'

type Tab = 'chat' | 'docs' | 'audit'

export default function App() {
  const [tab, setTab] = useState<Tab>('chat')
  const [domain, setDomain] = useState('medical')

  return (
    <div style={{ maxWidth: 960, margin: '40px auto', fontFamily: 'sans-serif' }}>
      <h1 style={{ color: '#2b6cb0' }}>RAGentHub 管理台</h1>

      <div style={{ marginBottom: 16, display: 'flex', gap: 8, alignItems: 'center' }}>
        {(['chat', 'docs', 'audit'] as Tab[]).map(t => (
          <button key={t} onClick={() => setTab(t)}
            style={{
              padding: '6px 14px', cursor: 'pointer',
              background: tab === t ? '#2b6cb0' : '#fff',
              color: tab === t ? '#fff' : '#2b6cb0',
              border: '1px solid #2b6cb0', borderRadius: 4
            }}>
            {t === 'chat' ? '问答' : t === 'docs' ? '文档' : '审计'}
          </button>
        ))}
        <select value={domain} onChange={e => setDomain(e.target.value)} style={{ marginLeft: 16 }}>
          <option value="medical">medical</option>
          <option value="finance">finance</option>
          <option value="gov">gov</option>
        </select>
      </div>

      {tab === 'chat' && <Chat domain={domain} />}
      {tab === 'docs' && <Documents domain={domain} />}
      {tab === 'audit' && <Audit />}
    </div>
  )
}
