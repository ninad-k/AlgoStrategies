import { useState, useEffect, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import AppShell from '../components/layout/AppShell'
import TopBar from '../components/layout/TopBar'
import StatCard from '../components/ui/StatCard'
import DateRangePicker from '../components/ui/DateRangePicker'
import DataTable from '../components/ui/DataTable'
import PnlBarChart from '../components/charts/PnlBarChart'
import LoadingSpinner from '../components/ui/LoadingSpinner'
import ErrorBanner from '../components/ui/ErrorBanner'
import Badge from '../components/ui/Badge'
import { getTraderTrades, getTraderRisk, getPnlByTrader, getPnlBySymbol } from '../api/pnl'
import { getTraders } from '../api/config'

function daysAgo(n) {
  const d = new Date(); d.setDate(d.getDate() - n)
  return d.toISOString().split('T')[0]
}

const TRADE_COLS = [
  { key: 'open_time', label: 'Date', render: (v) => v ? new Date(v).toLocaleDateString() : '—' },
  { key: 'symbol', label: 'Symbol' },
  { key: 'type', label: 'Type', render: (v) => <span className={v === 'BUY' ? 'text-green-600 font-medium' : 'text-red-600 font-medium'}>{v}</span> },
  { key: 'lots', label: 'Lots', render: (v) => Number(v).toFixed(2) },
  { key: 'open_price', label: 'Open', render: (v) => Number(v).toFixed(5) },
  { key: 'close_price', label: 'Close', render: (v) => v ? Number(v).toFixed(5) : '—' },
  { key: 'net_profit', label: 'Net P&L', render: (v) => <span className={v >= 0 ? 'text-green-600 font-semibold' : 'text-red-600 font-semibold'}>${Number(v).toFixed(2)}</span> },
  { key: 'planned_rr', label: 'Planned R:R', render: (v) => v ? Number(v).toFixed(2) : '—' },
  { key: 'realised_rr', label: 'Realised R:R', render: (v) => v ? Number(v).toFixed(2) : '—' },
]

export default function TraderDetail() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [filters, setFilters] = useState({ date_from: daysAgo(30), date_to: new Date().toISOString().split('T')[0] })
  const [trader, setTrader] = useState(null)
  const [trades, setTrades] = useState([])
  const [risk, setRisk] = useState(null)
  const [symbols, setSymbols] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const load = useCallback(async () => {
    setLoading(true); setError('')
    try {
      const [traders, t, r, sym] = await Promise.all([
        getTraders(),
        getTraderTrades(id, filters),
        getTraderRisk(id, filters),
        getPnlBySymbol({ ...filters, category_type: 'trader', category_id: id }),
      ])
      setTrader(traders.find(tr => tr.id === parseInt(id)))
      setTrades(t); setRisk(r); setSymbols(sym)
    } catch {
      setError('Failed to load trader data.')
    } finally {
      setLoading(false)
    }
  }, [id, filters])

  useEffect(() => { load() }, [load])

  const fmt = (v) => v != null ? `$${Number(v).toLocaleString('en-US', { minimumFractionDigits: 2 })}` : '—'
  const rrBadge = (deviation) => {
    if (deviation == null) return null
    return deviation >= 0
      ? <Badge label={`+${deviation.toFixed(2)} deviation`} variant="green" />
      : <Badge label={`${deviation.toFixed(2)} deviation`} variant="red" />
  }

  const totalProfit = trades.reduce((s, t) => s + t.net_profit, 0)
  const wins = trades.filter(t => t.net_profit > 0).length

  return (
    <AppShell>
      <TopBar title={trader?.name ?? `Trader #${id}`}>
        <button onClick={() => navigate(-1)} className="text-sm text-gray-500 hover:text-teal-500">← Back</button>
        <DateRangePicker onChange={setFilters} />
      </TopBar>
      <div className="p-6 space-y-6">
        <ErrorBanner message={error} />
        {loading ? <LoadingSpinner /> : (
          <>
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
              <StatCard label="Total P&L" value={fmt(totalProfit)} accent />
              <StatCard label="Trades" value={trades.length} />
              <StatCard label="Win Rate" value={trades.length ? `${((wins / trades.length) * 100).toFixed(1)}%` : '—'} />
              <StatCard label="Default Lots" value={trader?.default_lot_size ?? '—'} />
            </div>

            {/* Risk section */}
            <div className="bg-white rounded-lg border border-gray-200 p-4 shadow-sm">
              <div className="text-sm font-semibold text-navy-800 mb-3">Risk Metrics</div>
              <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                <StatCard label="Avg Planned R:R" value={risk?.avg_planned_rr?.toFixed(2) ?? '—'} />
                <StatCard label="Avg Realised R:R" value={risk?.avg_realised_rr?.toFixed(2) ?? '—'} />
                <div className="rounded-lg border border-gray-200 p-4 bg-white">
                  <div className="text-xs text-gray-500 uppercase tracking-wide mb-1">Deviation</div>
                  <div className="mt-1">{rrBadge(risk?.avg_rr_deviation) ?? '—'}</div>
                </div>
                <StatCard label="No Risk Data" value={risk?.no_risk_data_count ?? '—'} sub="trades without SL/TP" />
              </div>
            </div>

            {/* Symbol breakdown */}
            {symbols.length > 0 && (
              <div className="bg-white rounded-lg border border-gray-200 p-4 shadow-sm">
                <div className="text-sm font-semibold text-navy-800 mb-3">P&L by Symbol</div>
                <PnlBarChart data={symbols} />
              </div>
            )}

            {/* Trade table */}
            <div className="bg-white rounded-lg border border-gray-200 shadow-sm">
              <div className="px-4 py-3 border-b border-gray-100 flex items-center justify-between">
                <div className="text-sm font-semibold text-navy-800">Trades ({trades.length})</div>
              </div>
              <div className="p-4">
                <DataTable columns={TRADE_COLS} rows={trades} emptyText="No trades in selected period" />
              </div>
            </div>
          </>
        )}
      </div>
    </AppShell>
  )
}
