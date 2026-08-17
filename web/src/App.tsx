import { Navigate, Route, Routes } from 'react-router-dom';

import { useAuth } from './auth/AuthContext';
import { Layout } from './components/Layout';
import { DashboardPage } from './pages/DashboardPage';
import { LoginPage } from './pages/LoginPage';
import { NotificationLogPage } from './pages/NotificationLogPage';
import { OffersPage } from './pages/OffersPage';
import { StoreOwnersPage } from './pages/StoreOwnersPage';

export function App() {
  const { user, isAdmin, loading } = useAuth();

  if (loading) {
    return <div className="splash">Loading…</div>;
  }

  if (!user || !isAdmin) {
    return <LoginPage />;
  }

  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<DashboardPage />} />
        <Route path="offers" element={<OffersPage />} />
        <Route path="stores" element={<StoreOwnersPage />} />
        <Route path="notifications" element={<NotificationLogPage />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
