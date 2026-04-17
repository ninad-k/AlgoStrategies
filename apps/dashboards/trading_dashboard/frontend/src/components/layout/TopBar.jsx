export default function TopBar({ title, children }) {
  return (
    <header className="h-14 bg-white border-b border-gray-200 flex items-center justify-between px-6 shrink-0">
      <h1 className="text-navy-800 font-semibold text-base">{title}</h1>
      <div className="flex items-center gap-3">{children}</div>
    </header>
  )
}
