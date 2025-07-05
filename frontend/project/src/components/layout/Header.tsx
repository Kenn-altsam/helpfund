import { Link, useLocation } from 'react-router-dom';
import { Heart, User } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/Button';
import { LanguageSwitcher } from '@/components/LanguageSwitcher';
import { useGlobalContext } from '@/context/GlobalContext';

export function Header() {
  const { t } = useTranslation();
  const location = useLocation();
  const { state } = useGlobalContext();
  // const considerationCount = state.considerationList.length; // kept for potential future use, not shown in header

  // Hide the global header on pages that have their own layouts (Finder, Login, Register)
  if (['/finder', '/login', '/register'].includes(location.pathname)) {
    return null;
  }

  return (
    <header className="sticky top-0 z-40 w-full border-b bg-background/80">
      <div className="container flex h-16 items-center justify-between">
        {/* Navigation */}
        <nav className="hidden md:flex items-center space-x-4">
          <Link to="/">
            <Button variant="outline" size="sm" className={`text-sm ${location.pathname === '/' ? 'bg-muted text-primary' : ''}`}> 
              {t('header.home')}
            </Button>
          </Link>
          <Link to="/finder">
            <Button variant="outline" size="sm" className={`text-sm ${location.pathname === '/finder' ? 'bg-muted text-primary' : ''}`}> 
              {t('header.finder')}
            </Button>
          </Link>
          {state.user && location.pathname !== '/' && (
            <Link to="/profile" className="relative">
              <Button variant="outline" size="sm" className={`flex items-center space-x-1 text-sm ${location.pathname === '/profile' ? 'bg-muted text-primary' : ''}`}> 
                <User className="h-4 w-4" />
                <span>{t('header.profile')}</span>
              </Button>
            </Link>
          )}
        </nav>

        {/* Right side: brand + controls */}
        <div className="flex items-center space-x-4">
          <Link to="/" className="flex items-center space-x-2">
            <Heart className="h-6 w-6 text-primary" />
            <span className="text-xl font-bold">{t('header.title')}</span>
          </Link>

          <LanguageSwitcher />
          
          {!state.user ? (
            <div className="flex items-center space-x-2">
              <Link to="/login">
                <Button variant="ghost" size="sm">
                  {t('header.login')}
                </Button>
              </Link>
              <Link to="/register">
                <Button size="sm">
                  {t('header.register')}
                </Button>
              </Link>
            </div>
          ) : (
            location.pathname !== '/' && (
              <div className="flex items-center space-x-2">
                <Link to="/profile">
                  <Button variant="ghost" size="icon">
                    <User className="h-4 w-4" />
                  </Button>
                </Link>
              </div>
            )
          )}
        </div>
      </div>
    </header>
  );
}