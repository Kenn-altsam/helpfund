import { Navigate, useLocation } from 'react-router-dom';
import { useGlobalContext } from '@/context/GlobalContext';
import { LoadingScreen } from '@/components/LoadingScreen';

interface ProtectedRouteProps {
  children: React.ReactNode;
}

export function ProtectedRoute({ children }: ProtectedRouteProps) {
  const { state } = useGlobalContext();
  const { user, isLoading } = state;
  const location = useLocation();

  if (isLoading) {
    return <LoadingScreen />;
  }

  if (!user) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  return <>{children}</>;
} 