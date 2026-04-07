import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { AuthProvider, useAuth } from './store/AuthContext'
import Login from './pages/Login'
import Dashboard from './pages/Dashboard'
import TraderDetail from './pages/TraderDetail'
import StrategyDetail from './pages/StrategyDetail'
import SymbolBreakdown from './pages/SymbolBreakdown'
import Upload from './pages/Upload'
import Config from './pages/Config'

function ProtectedRoute({ children }) {
  const { user } = useAuth()
  return user ? children : <Navigate to="/login" replace />
}

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/dashboard" element={<ProtectedRoute><Dashboard /></ProtectedRoute>} />
          <Route path="/traders/:id" element={<ProtectedRoute><TraderDetail /></ProtectedRoute>} />
          <Route path="/strategies/:id" element={<ProtectedRoute><StrategyDetail /></ProtectedRoute>} />
          <Route path="/symbols" element={<ProtectedRoute><SymbolBreakdown /></ProtectedRoute>} />
          <Route path="/upload" element={<ProtectedRoute><Upload /></ProtectedRoute>} />
          <Route path="/config" element={<ProtectedRoute><Config /></ProtectedRoute>} />
          <Route path="*" element={<Navigate to="/dashboard" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  )
}
