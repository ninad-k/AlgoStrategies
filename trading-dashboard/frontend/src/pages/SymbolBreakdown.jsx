import { useState, useEffect, useCallback } from 'react'
import AppShell from '../components/layout/AppShell'
import TopBar from '../components/layout/TopBar'
import DateRangePicker from '../components/ui/DateRangePicker'
import PnlBarChart from '../components/charts/PnlBarChart'
import LoadingSpinner from '../components/ui/LoadingSpinner'
import ErrorBanner from '../components/ui/ErrorBanner'
import { getPnlBySymbol } from '../api/pnl'

function daysAgo(n) {
  const d = new Date(); d.setDate(d.getDate() - n)
  return d.toISOString().split('T')[0]
}

export default function SymbolBreakdown() {
  const [filters, setFilters] = useState({ date_from: daysAgo(30), date_to: new Date().toISOString().split('T')[0] })
  const [data, setData] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const load = useCallback(async () => {
    setLoading(true); setError('')
    try {
      const rows = await getPnlBySymbol(filters)
      setData(rows)
    } catch {
      setError('Failed to load symbol data.')
    } finally {
      setLoading(false)
    }
  }, [filters])

  useEffect(() => { load() }, [load])

  const fmt = (v) => v != null ? `$${Number(v).toFixed(2)}` : '—'
  const pct = (v) => v != null ? `${(v * 100).toFixed(1)}%` : '—'

  return (
    <AppShell>
      <TopBar title="P&L by Symbol">
        <DateRangePicker onChange={setFilters} />
      </TopBar>
      <div className="p-6 space-y-6">
        <ErrorBanner message={error} />
        {loading ? <LoadingSpinner /> : (
          <>
            <div className="bg-white rounded-lg border border-gray-200 p-4 shadow-sm">
              <div className="text-sm font-semibold text-navy-800 mb-3">All Symbols</div>
              <PnlBarChart data={data} />
            </div>

            <div className="bg-white rounded-lg border border-gray-200 shadow-sm overflow-hidden">
              <table className="w-full text-sm">
                <thead>
                  <tr className="bg-navy-800">
                    {['Symbol', 'Trades', 'P&L', 'Win Rate', 'Avg Planned R:R', 'Avg Realised R:R'].map(h => (
                      <th key={h} className="px-4 py-2.5 text-left text-xs text-gray-300 font-medium">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {data.map((row, i) => (
                    <tr key={i} className={`border-t border-gray-100 ${i % 2 === 0 ? 'bg-white' : 'bg-gray-50'}`}>
                      <td className="px-4 py-2.5 font-semibold text-navy-800">{row.category_name}</td>
                      <td className="px-4 py-2.5 text-gray-600">{row.trade_count}</td>
                      <td className={`px-4 py-2.5 font-semibold ${row.total_profit >= 0 ? 'text-green-600' : 'text-red-600'}`}>{fmt(row.total_profit)}</td>
                      <td className="px-4 py-2.5 text-gray-600">{pct(row.win_rate)}</td>
                      <td className="px-4 py-2.5 text-gray-600">{row.avg_planned_rr?.toFixed(2) ?? '—'}</td>
                      <td className="px-4 py-2.5 text-gray-600">{row.avg_realised_rr?.toFixed(2) ?? '—'}</td>
                    </tr>
                  ))}
                  {!data.length && (
                    <tr><td colSpan={6} className="text-center py-8 text-gray-400">No data</td></tr>
                  )}
                </tbody>
              </table>
            </div>
          </>
        )}
      </div>
    </AppShell>
  )
}
