import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts'

const GUEST_COLOR = '#D97706'
const BAR_COLOR = '#0D7377'

function fmt(v) {
  if (Math.abs(v) >= 1000) return `$${(v / 1000).toFixed(1)}k`
  return `$${v.toFixed(0)}`
}

export default function PnlBarChart({ data = [], nameKey = 'category_name', valueKey = 'total_profit' }) {
  const sorted = [...data].sort((a, b) => b[valueKey] - a[valueKey])
  return (
    <ResponsiveContainer width="100%" height={220}>
      <BarChart data={sorted} layout="vertical" margin={{ left: 8, right: 40, top: 4, bottom: 4 }}>
        <XAxis type="number" tickFormatter={fmt} tick={{ fontSize: 11, fill: '#94a3b8' }} axisLine={false} tickLine={false} />
        <YAxis dataKey={nameKey} type="category" width={90} tick={{ fontSize: 11, fill: '#64748b' }} axisLine={false} tickLine={false} />
        <Tooltip formatter={(v) => [`$${v.toFixed(2)}`, 'P&L']} contentStyle={{ fontSize: 12 }} />
        <Bar dataKey={valueKey} radius={[0, 3, 3, 0]}>
          {sorted.map((entry, i) => (
            <Cell key={i} fill={entry[nameKey] === 'Guest/Common' ? GUEST_COLOR : BAR_COLOR} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  )
}
