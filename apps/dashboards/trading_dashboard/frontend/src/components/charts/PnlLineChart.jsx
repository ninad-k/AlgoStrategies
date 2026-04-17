import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from 'recharts'

function fmt(v) {
  if (Math.abs(v) >= 1000) return `$${(v / 1000).toFixed(1)}k`
  return `$${v.toFixed(0)}`
}

export default function PnlLineChart({ data = [] }) {
  return (
    <ResponsiveContainer width="100%" height={200}>
      <LineChart data={data} margin={{ left: 8, right: 16, top: 8, bottom: 4 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
        <XAxis dataKey="date" tick={{ fontSize: 11, fill: '#94a3b8' }} axisLine={false} tickLine={false} />
        <YAxis tickFormatter={fmt} tick={{ fontSize: 11, fill: '#94a3b8' }} axisLine={false} tickLine={false} />
        <Tooltip formatter={(v) => [`$${v.toFixed(2)}`, 'Cumulative P&L']} contentStyle={{ fontSize: 12 }} />
        <Line type="monotone" dataKey="cumulative_pnl" stroke="#0D7377" strokeWidth={2} dot={false} />
      </LineChart>
    </ResponsiveContainer>
  )
}
