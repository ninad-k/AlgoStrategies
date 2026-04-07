import { useState, useEffect, useCallback } from 'react'
import AppShell from '../components/layout/AppShell'
import TopBar from '../components/layout/TopBar'
import StatCard from '../components/ui/StatCard'
import DateRangePicker from '../components/ui/DateRangePicker'
import PnlBarChart from '../components/charts/PnlBarChart'
import PnlLineChart from '../components/charts/PnlLineChart'
import LoadingSpinner from '../components/ui/LoadingSpinner'
import ErrorBanner from '../components/ui/ErrorBanner'
import { getPnlSummary, getPnlByTrader, getPnlByStrategy, getTraderTrades } from '../api/pnl'
import { useNavigate } from 'react-router-dom'

function daysAgo(n) {
  const d = new Date(); d.setDate(d.getDate() - n)
  return d.toISOString().split('T')[0]
}

export default function Dashboard() {
  const navigate = useNavigate()
  const [filters, setFilters] = useState({ date_from: daysAgo(30), date_to: new Date().toISOString().split('T')[0] })
  const [summary, setSummary] = useState(null)
  const [byTrader, setByTrader] = useState([])
  const [byStrategy, setByStrategy] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const load = useCallback(async () => {
    setLoading(true); setError('')
    try {
      const [s, t, st] = await Promise.all([
        getPnlSummary(filters),
        getPnlByTrader(filters),
        getPnlByStrategy(filters),
      ])
      setSummary(s); setByTrader(t); setByStrategy(st)
    } catch (e) {
      setError('Failed to load data. Check that the backend is running.')
    } finally {
      setLoading(false)
    }
  }, [filters])

  useEffect(() => { load() }, [load])

  const fmt = (v) => v != null ? `$${Number(v).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}` : '—'
  const pct = (v) => v != null ? `${(v * 100).toFixed(1)}%` : '—'

  return (
    <AppShell>
      <TopBar title="Dashboard">
        <DateRangePicker onChange={setFilters} />
      </TopBar>
      <div className="p-6 space-y-6">
        <ErrorBanner message={error} />
        {loading ? <LoadingSpinner /> : (
          <>
            {/* Stat cards */}
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
              <StatCard label="Total P&L" value={fmt(summary?.total_profit)} accent />
              <StatCard label="Total Trades" value={summary?.trade_count ?? '—'} />
              <StatCard label="Win Rate" value={pct(summary?.win_rate)} />
              <StatCard label="Best Trade" value={fmt(summary?.best_trade)} />
            </div>

            {/* Bar charts */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              <div className="bg-white rounded-lg border border-gray-200 p-4 shadow-sm">
                <div className="text-sm font-semibold text-navy-800 mb-3">P&L by Trader</div>
                {byTrader.length ? (
                  <div className="cursor-pointer" onClick={(e) => {
                    // clicking a bar item → navigate to detail (handled via recharts onClick below)
                  }}>
                    <PnlBarChart data={byTrader} />
                  </div>
                ) : <div className="text-gray-400 text-sm py-8 text-center">No trader data</div>}
              </div>
              <div className="bg-white rounded-lg border border-gray-200 p-4 shadow-sm">
                <div className="text-sm font-semibold text-navy-800 mb-3">P&L by Strategy</div>
                {byStrategy.length ? (
                  <PnlBarChart data={byStrategy} />
                ) : <div className="text-gray-400 text-sm py-8 text-center">No strategy data</div>}
              </div>
            </div>

            {/* Traders table */}
            <div className="bg-white rounded-lg border border-gray-200 shadow-sm overflow-hidden">
              <div className="px-4 py-3 border-b border-gray-100">
                <div className="text-sm font-semibold text-navy-800">Traders</div>
              </div>
              <table className="w-full text-sm">
                <thead>
                  <tr className="bg-navy-800">
                    {['Trader', 'P&L', 'Trades', 'Win Rate', 'Avg Planned R:R', 'Avg Realised R:R'].map(h => (
                      <th key={h} className="px-4 py-2.5 text-left text-xs text-gray-300 font-medium">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {byTrader.map((row, i) => (
                    <tr
                      key={i}
                      className="border-t border-gray-100 hover:bg-teal-50 cursor-pointer transition-colors"
                      onClick={() => row.category_id && navigate(`/traders/${row.category_id}`)}
                    >
                      <td className="px-4 py-2.5 font-medium text-navy-800">{row.category_name}</td>
                      <td className={`px-4 py-2.5 font-semibold ${row.total_profit >= 0 ? 'text-green-600' : 'text-red-600'}`}>{fmt(row.total_profit)}</td>
                      <td className="px-4 py-2.5 text-gray-600">{row.trade_count}</td>
                      <td className="px-4 py-2.5 text-gray-600">{pct(row.win_rate)}</td>
                      <td className="px-4 py-2.5 text-gray-600">{row.avg_planned_rr?.toFixed(2) ?? '—'}</td>
                      <td className="px-4 py-2.5 text-gray-600">{row.avg_realised_rr?.toFixed(2) ?? '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
      </div>
    </AppShell>
  )
}
