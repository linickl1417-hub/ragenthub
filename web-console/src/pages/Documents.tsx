import { useEffect, useState } from 'react'
import { listDocuments, uploadDocument } from '../api'

export default function Documents({ domain }: { domain: string }) {
  const [docs, setDocs] = useState<any[]>([])
  const [file, setFile] = useState<File | null>(null)

  async function refresh() {
    setDocs(await listDocuments(domain))
  }

  useEffect(() => { refresh() }, [domain])

  async function upload() {
    if (!file) return
    await uploadDocument(file, domain)
    setFile(null)
    refresh()
  }

  return (
    <div>
      <input type="file" accept=".md,.txt,.pdf" onChange={e => setFile(e.target.files?.[0] ?? null)} />
      <button onClick={upload} style={{ marginLeft: 8 }}>上传</button>

      <table style={{ width: '100%', marginTop: 16, borderCollapse: 'collapse' }}>
        <thead>
          <tr style={{ background: '#f7f8fa' }}>
            <th style={td}>文件</th><th style={td}>domain</th><th style={td}>chunks</th><th style={td}>上传时间</th>
          </tr>
        </thead>
        <tbody>
          {docs.map((d, i) => (
            <tr key={i}>
              <td style={td}>{d.filename}</td>
              <td style={td}>{d.domain}</td>
              <td style={td}>{d.chunks}</td>
              <td style={td}>{d.uploaded_at}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

const td: React.CSSProperties = { border: '1px solid #e2e8f0', padding: 8, textAlign: 'left' }
