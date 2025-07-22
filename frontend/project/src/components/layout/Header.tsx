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

  // Hide the global header on Finder, Login and Register pages
  if (['/finder', '/auth/login', '/auth/register'].includes(location.pathname)) {
    return null;
  }

  // Determine if we are on pages that require the centered brand & extra right-side links
  const isMainPage = ['/', '/finder'].includes(location.pathname);
  // On Consideration page we don't want to display the central brand link
  const showBrand = !['/consideration', '/profile'].includes(location.pathname);

  return (
    <header className="sticky top-0 z-40 w-full border-b bg-background/80">
      <div className="container flex h-16 items-center">
        {/* Left section: Brand and main navigation links */}
        <div className="flex flex-1 items-center justify-start gap-x-4">
          {showBrand && (
            <Link to="/" className="flex items-center space-x-2">
              <Heart className="h-6 w-6 text-primary" />
              <span className="hidden sm:inline text-xl font-bold">{t('header.title')}</span>
            </Link>
          )}
          <nav className="hidden md:flex items-center space-x-4">
            <Link to="/">
              <Button
                variant="outline"
                size="sm"
                className={`text-sm ${location.pathname === '/' ? 'bg-muted text-primary' : ''}`}
              >
                {t('header.home')}
              </Button>
            </Link>
            <Link to="/finder">
              <Button
                variant="outline"
                size="sm"
                className={`text-sm ${location.pathname === '/finder' ? 'bg-muted text-primary' : ''}`}
              >
                {t('header.finder')}
              </Button>
            </Link>
          </nav>
        </div>

        {/* Right-side controls: Auth buttons, user actions, language switcher */}
        <div className="flex flex-1 items-center justify-end space-x-2">
          {!state.user ? (
            <>
              <Link to="/auth/login">
                <Button variant="ghost" size="sm">
                  {t('header.login')}
                </Button>
              </Link>
              <Link to="/auth/register">
                <Button size="sm">{t('header.register')}</Button>
              </Link>
            </>
          ) : (
            <>
              {/* Show Consideration link only on Home & Finder pages */}
              {isMainPage && (
                <Link to="/consideration">
                  <Button
                    variant="outline"
                    size="sm"
                    className={`text-sm ${location.pathname === '/consideration' ? 'bg-muted text-primary' : ''}`}
                  >
                    {t('header.consideration')}
                  </Button>
                </Link>
              )}
              {/* Profile link */}
              <Link to="/profile">
                <Button
                  variant="outline"
                  size="sm"
                  className={`flex items-center space-x-1 text-sm ${location.pathname === '/profile' ? 'bg-muted text-primary' : ''}`}
                >
                  <User className="h-4 w-4" />
                  <span>{t('header.profile')}</span>
                </Button>
              </Link>
            </>
          )}
          <LanguageSwitcher />
        </div>
      </div>
    </header>
  );
}