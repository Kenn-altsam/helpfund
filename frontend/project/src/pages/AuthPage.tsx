import React, { useState } from 'react';
import { Link, useNavigate, useLocation, Navigate } from 'react-router-dom';
import { Heart, Mail, Lock, User } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card';
import { useGlobalContext } from '@/context/GlobalContext';
import { authApi } from '@/services/api';
import { toast } from 'sonner';
import { AuthResponse } from '@/types';

export function AuthPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const location = useLocation();
  const { state, dispatch } = useGlobalContext();
  
  const isLogin = location.pathname === '/auth/login';
  const [isLoading, setIsLoading] = useState(false);
  const [formData, setFormData] = useState({
    email: '',
    password: '',
    full_name: '',
  });

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setFormData(prev => ({
      ...prev,
      [e.target.name]: e.target.value,
    }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!formData.email || !formData.password) {
      toast.error(t('auth.validation.fillRequired'), { duration: 2000 });
      return;
    }

    if (!isLogin && !formData.full_name) {
      toast.error(t('auth.validation.enterName'), { duration: 2000 });
      return;
    }

    try {
      setIsLoading(true);
      
      const response: AuthResponse = isLogin 
        ? await authApi.login({ email: formData.email, password: formData.password })
        : await authApi.register({ 
            email: formData.email, 
            password: formData.password, 
            full_name: formData.full_name 
          });

      if (!response || !response.access_token) {
        throw new Error('Invalid response from server');
      }

      localStorage.setItem('access_token', response.access_token);
      
      dispatch({ type: 'SET_USER', payload: response.user });
      dispatch({ type: 'SET_LOADING', payload: false });
      
      toast.success(isLogin ? t('auth.success.welcome') : t('auth.success.accountCreated'), {
        duration: 2000
      });
      const redirectPath = (location.state as any)?.from?.pathname || '/finder';
      navigate(redirectPath, { replace: true });
    } catch (error: any) {
      console.error('Auth error:', error);
      
      localStorage.removeItem('access_token');
      
      if (error.response?.status === 400) {
        const errorMessage = (error.response.data as any)?.detail;
        if (errorMessage === 'Email already registered') {
          toast.error(t('auth.errors.emailExists'), { duration: 2000 });
        } else {
          toast.error(t('auth.errors.invalidData'), { duration: 2000 });
        }
      } else if (error.response?.status === 404) {
        toast.error(isLogin ? t('auth.errors.loginError') : t('auth.errors.registerError'), { duration: 2000 });
      } else if (error.response?.status === 401) {
        const errorMessage = (error.response.data as any)?.detail;
        if (errorMessage === 'Could not validate credentials') {
          toast.error(t('auth.errors.invalidCredentials'), { duration: 2000 });
        } else {
          toast.error(t('auth.errors.wrongPassword'), { duration: 2000 });
        }
      } else if (error.response?.status === 500) {
        toast.error(t('auth.errors.serverError'), { duration: 2000 });
      } else {
        toast.error(isLogin ? t('auth.errors.loginError') : t('auth.errors.registerError'), { duration: 2000 });
      }
    } finally {
      setIsLoading(false);
    }
  };

  // Redirect authenticated users away from login/register pages
  if (state.user) {
    return <Navigate to="/" replace />;
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-primary/5 via-background to-secondary/5 px-4">
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <Link to="/" className="inline-flex items-center space-x-2 mb-6">
            <Heart className="h-8 w-8 text-primary" />
            <span className="text-2xl font-bold">{t('header.title')}</span>
          </Link>
          <h1 className="text-2xl font-bold">
            {isLogin ? t('auth.login.title') : t('auth.register.title')}
          </h1>
          <p className="text-muted-foreground mt-2">
            {isLogin ? t('auth.login.subtitle') : t('auth.register.subtitle')}
          </p>
        </div>

        <Card>
          <CardHeader>
            <CardTitle className="text-center">
              {isLogin ? t('auth.login.button') : t('auth.register.button')}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleSubmit} className="space-y-4">
              {!isLogin && (
                <div className="space-y-2">
                  <label htmlFor="name" className="text-sm font-medium">
                    {t('auth.fields.name')}
                  </label>
                  <div className="relative">
                    <User className="absolute left-3 top-3 h-4 w-4 text-muted-foreground" />
                    <Input
                      id="name"
                      name="full_name"
                      type="text"
                      placeholder={t('auth.fields.namePlaceholder')}
                      value={formData.full_name}
                      onChange={handleInputChange}
                      className="pl-10"
                      required={!isLogin}
                    />
                  </div>
                </div>
              )}

              <div className="space-y-2">
                <label htmlFor="email" className="text-sm font-medium">
                  {t('auth.fields.email')}
                </label>
                <div className="relative">
                  <Mail className="absolute left-3 top-3 h-4 w-4 text-muted-foreground" />
                  <Input
                    id="email"
                    name="email"
                    type="email"
                    placeholder={t('auth.fields.emailPlaceholder')}
                    value={formData.email}
                    onChange={handleInputChange}
                    className="pl-10"
                    required
                  />
                </div>
              </div>

              <div className="space-y-2">
                <label htmlFor="password" className="text-sm font-medium">
                  {t('auth.fields.password')}
                </label>
                <div className="relative">
                  <Lock className="absolute left-3 top-3 h-4 w-4 text-muted-foreground" />
                  <Input
                    id="password"
                    name="password"
                    type="password"
                    placeholder={t('auth.fields.passwordPlaceholder')}
                    value={formData.password}
                    onChange={handleInputChange}
                    className="pl-10"
                    required
                  />
                </div>
              </div>

              <Button type="submit" className="w-full" disabled={isLoading}>
                {isLoading 
                  ? (isLogin ? t('auth.login.loading') : t('auth.register.loading'))
                  : (isLogin ? t('auth.login.button') : t('auth.register.button'))
                }
              </Button>
            </form>

            <div className="mt-6 text-center">
              <p className="text-sm text-muted-foreground">
                {isLogin ? t('auth.login.noAccount') : t('auth.register.hasAccount')}{' '}
                <Link
                  to={isLogin ? '/auth/register' : '/auth/login'}
                  className="text-primary hover:underline font-medium"
                >
                  {isLogin ? t('auth.login.register') : t('auth.register.login')}
                </Link>
              </p>
            </div>
          </CardContent>
        </Card>

        <div className="mt-8 text-center">
          <p className="text-xs text-muted-foreground">
            {t('auth.terms')}
          </p>
        </div>
      </div>
    </div>
  );
}