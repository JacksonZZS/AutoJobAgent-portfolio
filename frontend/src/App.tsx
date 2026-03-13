import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { useAuthStore } from './store/authStore'
import LoginPage from './pages/LoginPage'
import RegisterPage from './pages/RegisterPage'
import DashboardPage from './pages/DashboardPage'
import HistoryPage from './pages/HistoryPage'
import ResumeOptimizerPage from './pages/ResumeOptimizerPage'
import FavoritesPage from './pages/FavoritesPage'
import StatisticsPage from './pages/StatisticsPage'
import InterviewPrepPage from './pages/InterviewPrepPage'
import ResumeManagerPage from './pages/ResumeManagerPage'
import EmailSettingsPage from './pages/EmailSettingsPage'
import Layout from './components/layout/Layout'

function App() {
  const { user } = useAuthStore()

  return (
    <BrowserRouter>
      <Routes>
        {/* Public routes */}
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />

        {/* Protected routes */}
        <Route
          path="/"
          element={user ? <Layout /> : <Navigate to="/login" />}
        >
          <Route index element={<DashboardPage />} />
          <Route path="history" element={<HistoryPage />} />
          <Route path="optimizer" element={<ResumeOptimizerPage />} />
          <Route path="favorites" element={<FavoritesPage />} />
          <Route path="statistics" element={<StatisticsPage />} />
          <Route path="interview" element={<InterviewPrepPage />} />
          <Route path="resumes" element={<ResumeManagerPage />} />
          <Route path="email-settings" element={<EmailSettingsPage />} />
        </Route>

        {/* Fallback */}
        <Route path="*" element={<Navigate to="/" />} />
      </Routes>
    </BrowserRouter>
  )
}

export default App
