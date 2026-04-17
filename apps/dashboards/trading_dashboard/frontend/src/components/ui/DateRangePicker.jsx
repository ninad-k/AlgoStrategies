import { useState } from 'react'

const PRESETS = [
  { label: '1W', days: 7 },
  { label: '1M', days: 30 },
  { label: '3M', days: 90 },
  { label: 'YTD', days: null },
]

function ytdFrom() {
  const d = new Date()
  return new Date(d.getFullYear(), 0, 1).toISOString().split('T')[0]
}

function daysAgo(n) {
  const d = new Date()
  d.setDate(d.getDate() - n)
  return d.toISOString().split('T')[0]
}

export default function DateRangePicker({ onChange }) {
  const [active, setActive] = useState('1M')

  function select(preset) {
    setActive(preset.label)
    const from = preset.days ? daysAgo(preset.days) : ytdFrom()
    const to = new Date().toISOString().split('T')[0]
    onChange({ date_from: from, date_to: to })
  }

  return (
    <div className="flex gap-1">
      {PRESETS.map((p) => (
        <button
          key={p.label}
          onClick={() => select(p)}
          className={`px-3 py-1 rounded text-xs font-medium transition-colors ${
            active === p.label
              ? 'bg-teal-500 text-white'
              : 'bg-white border border-gray-200 text-gray-600 hover:border-teal-400'
          }`}
        >
          {p.label}
        </button>
      ))}
    </div>
  )
}
