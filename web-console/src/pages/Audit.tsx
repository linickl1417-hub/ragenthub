import { useEffect, useState } from 'react'
import { listAudits } from '../api'

export default function Audit() {
  const [rows, setRows] = useState<any[]>([])
  useEffect(() => { listAudits().then(setRows) }, [])

  return (
    <table style={{ width: '100%', borderCollapse: 'collapse' }}>
      <thead>
        <tr style={{ background: '#f7f8fa' }}>
          <th style={th}>#</th><th style={th}>user</th><th style={th}>domain</th>
          <th style={th}>question</th><th style={th}>guard</th><th style={th}>ms</th><th style={th}>time</th>
        </tr>
      </thead>
      <tbody>
        {rows.map(r => (
          <tr key={r.id}>
            <td style={td}>{r.id}</td>
            <td style={td}>{r.user_id}</td>
            <td style={td}>{r.domain}</td>
            <td style={td}>{r.question}</td>
            <td style={td}>{r.guard_action}</td>
            <td style={td}>{r.latency_ms}</td>
            <td style={td}>{r.created_at}</td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

const th: React.CSSProperties = { border: '1px solid #e2e8f0', padding: 8, textAlign: 'left' }
const td: React.CSSProperties = th
