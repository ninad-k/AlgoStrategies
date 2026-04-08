export default function StatCard({ label, value, sub, accent = false }) {
  return (
    <div className={`rounded-lg border p-4 bg-white shadow-sm ${accent ? 'border-teal-400' : 'border-gray-200'}`}>
      <div className="text-xs text-gray-500 uppercase tracking-wide mb-1">{label}</div>
      <div className={`text-2xl font-bold ${accent ? 'text-teal-500' : 'text-navy-800'}`}>{value}</div>
      {sub && <div className="text-xs text-gray-400 mt-0.5">{sub}</div>}
    </div>
  )
}
