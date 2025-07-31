import { Link, useLocation } from 'react-router-dom';
import { Heart, User, Menu, X } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { useState } from 'react';
import { Button } from '@/components/ui/Button';
import { LanguageSwitcher } from '@/components/LanguageSwitcher';
import { useGlobalContext } from '@/context/GlobalContext';

export function Header() {
  const { t } = useTranslation();
  const location = useLocation();
  const { state } = useGlobalContext();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  // const considerationCount = state.considerationList.length; // kept for potential future use, not shown in header

  // Hide the global header on Finder, Login and Register pages
  if (['/finder', '/auth/login', '/auth/register'].includes(location.pathname)) {
    return null;
  }

  // Determine if we are on pages that require the centered brand & extra right-side links
  const isMainPage = ['/', '/finder'].includes(location.pathname);
  // On Consideration page we don't want to display the central brand link
  const showBrand = !['/consideration', '/profile'].includes(location.pathname);

  const toggleMobileMenu = () => {
    setMobileMenuOpen(!mobileMenuOpen);
  };

  const closeMobileMenu = () => {
    setMobileMenuOpen(false);
  };

  return (
    <header className="sticky top-0 z-40 w-full border-b bg-background/80 backdrop-blur-sm safe-area-top">
      <div className="container flex h-16 items-center mobile-padding">
        {/* Left section: Brand and mobile menu button */}
        <div className="flex flex-1 items-center justify-start gap-x-4">
          {showBrand && (
            <Link to="/" className="flex items-center space-x-2" onClick={closeMobileMenu}>
              <Heart className="h-6 w-6 text-primary" />
              <span className="hidden sm:inline text-xl font-bold">{t('header.title')}</span>
            </Link>
          )}
          
          {/* Mobile menu button */}
          <Button 
            variant="ghost" 
            size="icon" 
            onClick={toggleMobileMenu}
            className="md:hidden touch-target"
          >
            {mobileMenuOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
          </Button>
          
          {/* Desktop navigation */}
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
              <Link to="/auth/login" className="hidden sm:block">
                <Button variant="ghost" size="sm" className="touch-target">
                  {t('header.login')}
                </Button>
              </Link>
              <Link to="/auth/register" className="hidden sm:block">
                <Button size="sm" className="touch-target">{t('header.register')}</Button>
              </Link>
            </>
          ) : (
            <>
              {/* Show Consideration link only on Home & Finder pages */}
              {isMainPage && (
                <Link to="/consideration" className="hidden sm:block">
                  <Button
                    variant="outline"
                    size="sm"
                    className={`text-sm touch-target ${location.pathname === '/consideration' ? 'bg-muted text-primary' : ''}`}
                  >
                    {t('header.consideration')}
                  </Button>
                </Link>
              )}
              {/* Profile link */}
              <Link to="/profile" className="hidden sm:block">
                <Button
                  variant="outline"
                  size="sm"
                  className={`flex items-center space-x-1 text-sm touch-target ${location.pathname === '/profile' ? 'bg-muted text-primary' : ''}`}
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

      {/* Mobile menu overlay */}
      {mobileMenuOpen && (
        <div className="md:hidden">
          {/* Backdrop */}
          <div 
            className="fixed inset-0 bg-black/50 z-30" 
            onClick={closeMobileMenu}
          />
          
          {/* Mobile menu */}
          <div className="fixed top-16 left-0 right-0 bg-background border-b z-40 safe-area-left safe-area-right">
            <div className="p-4 space-y-4">
              {/* Navigation links */}
              <nav className="space-y-2">
                <Link to="/" onClick={closeMobileMenu}>
                  <Button
                    variant="ghost"
                    className={`w-full justify-start text-left touch-target ${location.pathname === '/' ? 'bg-muted text-primary' : ''}`}
                  >
                    {t('header.home')}
                  </Button>
                </Link>
                <Link to="/finder" onClick={closeMobileMenu}>
                  <Button
                    variant="ghost"
                    className={`w-full justify-start text-left touch-target ${location.pathname === '/finder' ? 'bg-muted text-primary' : ''}`}
                  >
                    {t('header.finder')}
                  </Button>
                </Link>
              </nav>

              {/* Auth/User section */}
              <div className="border-t pt-4 space-y-2">
                {!state.user ? (
                  <>
                    <Link to="/auth/login" onClick={closeMobileMenu}>
                      <Button variant="ghost" className="w-full justify-start text-left touch-target">
                        {t('header.login')}
                      </Button>
                    </Link>
                    <Link to="/auth/register" onClick={closeMobileMenu}>
                      <Button className="w-full justify-start text-left touch-target">
                        {t('header.register')}
                      </Button>
                    </Link>
                  </>
                ) : (
                  <>
                    {isMainPage && (
                      <Link to="/consideration" onClick={closeMobileMenu}>
                        <Button
                          variant="ghost"
                          className={`w-full justify-start text-left touch-target ${location.pathname === '/consideration' ? 'bg-muted text-primary' : ''}`}
                        >
                          {t('header.consideration')}
                        </Button>
                      </Link>
                    )}
                    <Link to="/profile" onClick={closeMobileMenu}>
                      <Button
                        variant="ghost"
                        className={`w-full justify-start text-left touch-target ${location.pathname === '/profile' ? 'bg-muted text-primary' : ''}`}
                      >
                        <User className="h-4 w-4 mr-2" />
                        {t('header.profile')}
                      </Button>
                    </Link>
                  </>
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </header>
  );
}