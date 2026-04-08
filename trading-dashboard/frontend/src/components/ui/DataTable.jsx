export default function DataTable({ columns, rows, emptyText = 'No data' }) {
  if (!rows?.length) {
    return <div className="text-center py-8 text-gray-400 text-sm">{emptyText}</div>
  }
  return (
    <div className="overflow-x-auto rounded-lg border border-gray-200">
      <table className="w-full text-sm">
        <thead>
          <tr className="bg-navy-800">
            {columns.map((col) => (
              <th
                key={col.key}
                className="px-3 py-2.5 text-left text-xs text-gray-300 font-medium uppercase tracking-wide whitespace-nowrap"
              >
                {col.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={i} className={`border-t border-gray-100 ${i % 2 === 0 ? 'bg-white' : 'bg-gray-50'} hover:bg-teal-50 transition-colors`}>
              {columns.map((col) => (
                <td key={col.key} className="px-3 py-2 text-gray-700 whitespace-nowrap">
                  {col.render ? col.render(row[col.key], row) : row[col.key] ?? '—'}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
