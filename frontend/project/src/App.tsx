import { BrowserRouter as Router, Routes, Route, useLocation, Navigate } from 'react-router-dom';
import { Toaster } from 'sonner';
import { GlobalProvider } from '@/context/GlobalContext';
import { Header } from '@/components/layout/Header';
import { Footer } from '@/components/layout/Footer';
import { HomePage } from '@/pages/HomePage';
import { FinderPage } from '@/pages/FinderPage';
import { ConsiderationPage } from '@/pages/ConsiderationPage';
import { ProfilePage } from '@/pages/ProfilePage';
import { AuthPage } from '@/pages/AuthPage';
import { ProtectedRoute } from '@/components/ProtectedRoute';

function AppContent() {
  const location = useLocation();
  const showFooter = !['/finder', '/consideration'].includes(location.pathname);

  return (
    <div className="min-h-screen flex flex-col">
      <Header />
      <main className="flex-1">
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route 
            path="/finder" 
            element={
              <ProtectedRoute>
                <FinderPage />
              </ProtectedRoute>
            } 
          />
          <Route 
            path="/consideration" 
            element={
              <ProtectedRoute>
                <ConsiderationPage />
              </ProtectedRoute>
            } 
          />
          <Route 
            path="/profile" 
            element={
              <ProtectedRoute>
                <ProfilePage />
              </ProtectedRoute>
            } 
          />
          {/* Redirect /companies/consideration to /consideration to avoid treating 'consideration' as a companyId */}
          <Route path="/companies/consideration" element={<Navigate to="/consideration" replace />} />
          <Route path="/auth/login" element={<AuthPage />} />
          <Route path="/auth/register" element={<AuthPage />} />
        </Routes>
      </main>
      {showFooter && <Footer />}
      <Toaster position="top-right" richColors duration={2000} />
    </div>
  );
}

export function App() {
  return (
    <Router>
      <GlobalProvider>
        <AppContent />
      </GlobalProvider>
    </Router>
  );
}