import { useState, useRef } from 'react'
import AppShell from '../components/layout/AppShell'
import TopBar from '../components/layout/TopBar'
import ErrorBanner from '../components/ui/ErrorBanner'
import { uploadTrades } from '../api/upload'

export default function Upload() {
  const [file, setFile] = useState(null)
  const [accountId, setAccountId] = useState('')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')
  const [dragging, setDragging] = useState(false)
  const inputRef = useRef()

  function handleDrop(e) {
    e.preventDefault(); setDragging(false)
    const f = e.dataTransfer.files[0]
    if (f) setFile(f)
  }

  async function handleSubmit(e) {
    e.preventDefault()
    if (!file || !accountId.trim()) { setError('File and Account ID are required.'); return }
    setError(''); setResult(null); setLoading(true)
    try {
      const res = await uploadTrades(file, accountId.trim())
      setResult(res); setFile(null)
    } catch (err) {
      setError(err.response?.data?.detail || 'Upload failed. Check the file format.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <AppShell>
      <TopBar title="Upload Trade History" />
      <div className="p-6 max-w-xl space-y-6">
        <form onSubmit={handleSubmit} className="space-y-5">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Account ID</label>
            <input
              value={accountId}
              onChange={(e) => setAccountId(e.target.value)}
              placeholder="e.g. 12345678"
              className="w-full border border-gray-300 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-teal-500"
            />
            <p className="text-xs text-gray-400 mt-1">The MT5 account this file belongs to</p>
          </div>

          <div
            onDragOver={(e) => { e.preventDefault(); setDragging(true) }}
            onDragLeave={() => setDragging(false)}
            onDrop={handleDrop}
            onClick={() => inputRef.current.click()}
            className={`border-2 border-dashed rounded-xl py-12 text-center cursor-pointer transition-colors ${dragging ? 'border-teal-400 bg-teal-50' : 'border-gray-300 hover:border-teal-400 bg-white'}`}
          >
            <div className="text-3xl mb-2">⬆</div>
            <div className="text-sm text-gray-600 font-medium">Drag & drop CSV or Excel here</div>
            <div className="text-xs text-gray-400 mt-1">or click to browse</div>
            <div className="text-xs text-gray-400 mt-2">Supported: .csv  .xlsx  .xls</div>
            <input ref={inputRef} type="file" accept=".csv,.xlsx,.xls" className="hidden" onChange={(e) => setFile(e.target.files[0])} />
          </div>

          {file && (
            <div className="flex items-center justify-between bg-teal-50 border border-teal-200 rounded-lg px-3 py-2.5 text-sm">
              <span className="text-teal-700 font-medium">{file.name} ({(file.size / 1024).toFixed(1)} KB)</span>
              <button type="button" onClick={() => setFile(null)} className="text-gray-400 hover:text-red-500 ml-2">✕</button>
            </div>
          )}

          <ErrorBanner message={error} />

          <button
            type="submit"
            disabled={loading}
            className="w-full bg-teal-500 hover:bg-teal-400 text-white font-medium py-2.5 rounded-lg text-sm transition-colors disabled:opacity-60"
          >
            {loading ? 'Processing…' : 'Upload & Process'}
          </button>
        </form>

        {result && (
          <div className="bg-white border border-green-200 rounded-xl p-5 shadow-sm space-y-3">
            <div className="flex items-center gap-2 text-green-600 font-semibold text-sm">
              <span>✓</span> Upload complete — Batch {result.batch_id.slice(0, 8)}…
            </div>
            <div className="grid grid-cols-2 gap-3 text-sm">
              {[
                ['Total rows parsed', result.total_rows],
                ['Inserted', result.inserted],
                ['Skipped (duplicate)', result.skipped_duplicates],
                ['Attributed to traders', result.attribution_summary.attributed_trader],
                ['Attributed to strategies', result.attribution_summary.attributed_strategy],
                ['Held in Guest/Common', result.attribution_summary.guest],
              ].map(([label, val]) => (
                <div key={label} className="flex justify-between border-b border-gray-100 pb-1">
                  <span className="text-gray-500">{label}</span>
                  <span className="font-semibold text-navy-800">{val}</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </AppShell>
  )
}
