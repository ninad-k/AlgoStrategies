import { useState, useEffect } from 'react'
import AppShell from '../components/layout/AppShell'
import TopBar from '../components/layout/TopBar'
import LoadingSpinner from '../components/ui/LoadingSpinner'
import ErrorBanner from '../components/ui/ErrorBanner'
import {
  getTraders, createTrader, updateTrader, deleteTrader,
  getStrategies, createStrategy, updateStrategy, deleteStrategy,
  getAccounts, createAccount,
} from '../api/config'

const TABS = ['Traders', 'Strategies', 'Accounts']

export default function Config() {
  const [tab, setTab] = useState('Traders')
  const [traders, setTraders] = useState([])
  const [strategies, setStrategies] = useState([])
  const [accounts, setAccounts] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [form, setForm] = useState({})
  const [editing, setEditing] = useState(null) // id of row being edited

  async function load() {
    setLoading(true)
    try {
      const [t, s, a] = await Promise.all([getTraders(), getStrategies(), getAccounts()])
      setTraders(t); setStrategies(s); setAccounts(a)
    } catch { setError('Failed to load config.') }
    finally { setLoading(false) }
  }
  useEffect(() => { load() }, [])

  function startEdit(item) { setEditing(item.id); setForm({ ...item }) }
  function cancelEdit() { setEditing(null); setForm({}) }

  async function saveTrader() {
    try {
      if (editing === 'new') await createTrader(form)
      else await updateTrader(editing, form)
      cancelEdit(); load()
    } catch { setError('Save failed.') }
  }

  async function saveStrategy() {
    const body = { ...form, symbol_filter: (form.symbol_filter || '').split(',').map(s => s.trim()).filter(Boolean) }
    try {
      if (editing === 'new') await createStrategy(body)
      else await updateStrategy(editing, body)
      cancelEdit(); load()
    } catch { setError('Save failed.') }
  }

  async function saveAccount() {
    try {
      await createAccount(form)
      cancelEdit(); load()
    } catch (e) { setError(e.response?.data?.detail || 'Save failed.') }
  }

  async function handleDeleteTrader(id) {
    if (!confirm('Delete trader?')) return
    try { await deleteTrader(id); load() } catch { setError('Delete failed.') }
  }

  async function handleDeleteStrategy(id) {
    if (!confirm('Delete strategy?')) return
    try { await deleteStrategy(id); load() } catch { setError('Delete failed.') }
  }

  const inputCls = 'border border-gray-300 rounded px-2.5 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-teal-500'

  return (
    <AppShell>
      <TopBar title="Configuration" />
      <div className="p-6 space-y-5">
        <div className="flex gap-1 border-b border-gray-200">
          {TABS.map(t => (
            <button
              key={t}
              onClick={() => { setTab(t); cancelEdit() }}
              className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors -mb-px ${tab === t ? 'border-teal-500 text-teal-600' : 'border-transparent text-gray-500 hover:text-gray-700'}`}
            >
              {t}
            </button>
          ))}
        </div>
        <ErrorBanner message={error} />
        {loading ? <LoadingSpinner /> : (
          <>
            {/* ── TRADERS ── */}
            {tab === 'Traders' && (
              <div className="space-y-4">
                <div className="flex justify-end">
                  <button onClick={() => { setEditing('new'); setForm({}) }} className="bg-teal-500 text-white text-sm px-4 py-2 rounded-lg hover:bg-teal-400">+ Add Trader</button>
                </div>
                {editing && (
                  <div className="bg-gray-50 border border-gray-200 rounded-xl p-4 space-y-3">
                    <div className="text-sm font-semibold">{editing === 'new' ? 'New Trader' : 'Edit Trader'}</div>
                    <div className="grid grid-cols-2 gap-3">
                      <div><label className="text-xs text-gray-600 block mb-1">Name</label><input className={inputCls + ' w-full'} value={form.name || ''} onChange={e => setForm(f => ({ ...f, name: e.target.value }))} /></div>
                      <div><label className="text-xs text-gray-600 block mb-1">Default Lot Size</label><input type="number" step="0.01" className={inputCls + ' w-full'} value={form.default_lot_size || ''} onChange={e => setForm(f => ({ ...f, default_lot_size: e.target.value }))} /></div>
                    </div>
                    <div className="flex gap-2">
                      <button onClick={saveTrader} className="bg-teal-500 text-white text-sm px-4 py-1.5 rounded hover:bg-teal-400">Save</button>
                      <button onClick={cancelEdit} className="text-sm text-gray-500 px-4 py-1.5 border border-gray-300 rounded hover:bg-gray-50">Cancel</button>
                    </div>
                  </div>
                )}
                <table className="w-full text-sm bg-white border border-gray-200 rounded-lg overflow-hidden">
                  <thead><tr className="bg-navy-800">{['Name', 'Default Lots', 'Actions'].map(h => <th key={h} className="px-4 py-2.5 text-left text-xs text-gray-300 font-medium">{h}</th>)}</tr></thead>
                  <tbody>
                    {traders.map((t, i) => (
                      <tr key={t.id} className={`border-t border-gray-100 ${i % 2 === 0 ? 'bg-white' : 'bg-gray-50'}`}>
                        <td className="px-4 py-2.5 font-medium">{t.name}{t.id === 0 && <span className="ml-2 text-xs text-gray-400">(system)</span>}</td>
                        <td className="px-4 py-2.5 text-gray-600">{t.default_lot_size ?? '—'}</td>
                        <td className="px-4 py-2.5 flex gap-2">
                          {t.id !== 0 && <><button onClick={() => startEdit(t)} className="text-xs text-teal-600 hover:underline">Edit</button><button onClick={() => handleDeleteTrader(t.id)} className="text-xs text-red-500 hover:underline">Delete</button></>}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            {/* ── STRATEGIES ── */}
            {tab === 'Strategies' && (
              <div className="space-y-4">
                <div className="flex justify-end">
                  <button onClick={() => { setEditing('new'); setForm({}) }} className="bg-teal-500 text-white text-sm px-4 py-2 rounded-lg hover:bg-teal-400">+ Add Strategy</button>
                </div>
                {editing && (
                  <div className="bg-gray-50 border border-gray-200 rounded-xl p-4 space-y-3">
                    <div className="text-sm font-semibold">{editing === 'new' ? 'New Strategy' : 'Edit Strategy'}</div>
                    <div className="grid grid-cols-2 gap-3">
                      <div><label className="text-xs text-gray-600 block mb-1">Name</label><input className={inputCls + ' w-full'} value={form.name || ''} onChange={e => setForm(f => ({ ...f, name: e.target.value }))} /></div>
                      <div><label className="text-xs text-gray-600 block mb-1">Magic Number</label><input type="number" className={inputCls + ' w-full'} value={form.magic_number || ''} onChange={e => setForm(f => ({ ...f, magic_number: e.target.value }))} /></div>
                      <div><label className="text-xs text-gray-600 block mb-1">Lot Size</label><input type="number" step="0.01" className={inputCls + ' w-full'} value={form.lot_size || ''} onChange={e => setForm(f => ({ ...f, lot_size: e.target.value }))} /></div>
                      <div><label className="text-xs text-gray-600 block mb-1">Symbol Filter (comma-separated)</label><input className={inputCls + ' w-full'} value={Array.isArray(form.symbol_filter) ? form.symbol_filter.join(',') : form.symbol_filter || ''} onChange={e => setForm(f => ({ ...f, symbol_filter: e.target.value }))} placeholder="XAUUSD,EURUSD" /></div>
                    </div>
                    <div className="flex gap-2">
                      <button onClick={saveStrategy} className="bg-teal-500 text-white text-sm px-4 py-1.5 rounded hover:bg-teal-400">Save</button>
                      <button onClick={cancelEdit} className="text-sm text-gray-500 px-4 py-1.5 border border-gray-300 rounded hover:bg-gray-50">Cancel</button>
                    </div>
                  </div>
                )}
                <table className="w-full text-sm bg-white border border-gray-200 rounded-lg overflow-hidden">
                  <thead><tr className="bg-navy-800">{['Name', 'Magic', 'Lot Size', 'Symbols', 'Actions'].map(h => <th key={h} className="px-4 py-2.5 text-left text-xs text-gray-300 font-medium">{h}</th>)}</tr></thead>
                  <tbody>
                    {strategies.map((s, i) => (
                      <tr key={s.id} className={`border-t border-gray-100 ${i % 2 === 0 ? 'bg-white' : 'bg-gray-50'}`}>
                        <td className="px-4 py-2.5 font-medium">{s.name}</td>
                        <td className="px-4 py-2.5 text-gray-600">{s.magic_number ?? '—'}</td>
                        <td className="px-4 py-2.5 text-gray-600">{s.lot_size ?? '—'}</td>
                        <td className="px-4 py-2.5 text-gray-600">{s.symbol_filter?.join(', ') || '—'}</td>
                        <td className="px-4 py-2.5 flex gap-2">
                          <button onClick={() => startEdit(s)} className="text-xs text-teal-600 hover:underline">Edit</button>
                          <button onClick={() => handleDeleteStrategy(s.id)} className="text-xs text-red-500 hover:underline">Delete</button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            {/* ── ACCOUNTS ── */}
            {tab === 'Accounts' && (
              <div className="space-y-4">
                <div className="flex justify-end">
                  <button onClick={() => { setEditing('new'); setForm({}) }} className="bg-teal-500 text-white text-sm px-4 py-2 rounded-lg hover:bg-teal-400">+ Add Account</button>
                </div>
                {editing === 'new' && (
                  <div className="bg-gray-50 border border-gray-200 rounded-xl p-4 space-y-3">
                    <div className="text-sm font-semibold">New Account</div>
                    <div className="grid grid-cols-3 gap-3">
                      <div><label className="text-xs text-gray-600 block mb-1">Account ID</label><input className={inputCls + ' w-full'} value={form.account_id || ''} onChange={e => setForm(f => ({ ...f, account_id: e.target.value }))} /></div>
                      <div><label className="text-xs text-gray-600 block mb-1">Broker</label><input className={inputCls + ' w-full'} value={form.broker || ''} onChange={e => setForm(f => ({ ...f, broker: e.target.value }))} /></div>
                      <div><label className="text-xs text-gray-600 block mb-1">Currency</label><input className={inputCls + ' w-full'} value={form.currency || 'USD'} onChange={e => setForm(f => ({ ...f, currency: e.target.value }))} /></div>
                    </div>
                    <div className="flex gap-2">
                      <button onClick={saveAccount} className="bg-teal-500 text-white text-sm px-4 py-1.5 rounded hover:bg-teal-400">Save</button>
                      <button onClick={cancelEdit} className="text-sm text-gray-500 px-4 py-1.5 border border-gray-300 rounded hover:bg-gray-50">Cancel</button>
                    </div>
                  </div>
                )}
                <table className="w-full text-sm bg-white border border-gray-200 rounded-lg overflow-hidden">
                  <thead><tr className="bg-navy-800">{['Account ID', 'Broker', 'Currency'].map(h => <th key={h} className="px-4 py-2.5 text-left text-xs text-gray-300 font-medium">{h}</th>)}</tr></thead>
                  <tbody>
                    {accounts.map((a, i) => (
                      <tr key={a.id} className={`border-t border-gray-100 ${i % 2 === 0 ? 'bg-white' : 'bg-gray-50'}`}>
                        <td className="px-4 py-2.5 font-medium">{a.account_id}</td>
                        <td className="px-4 py-2.5 text-gray-600">{a.broker ?? '—'}</td>
                        <td className="px-4 py-2.5 text-gray-600">{a.currency}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </>
        )}
      </div>
    </AppShell>
  )
}
