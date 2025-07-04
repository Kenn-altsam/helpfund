import { Link, useLocation } from 'react-router-dom';
import { Heart, BookmarkCheck } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/Button';
import { Badge } from '@/components/ui/Badge';
import { LanguageSwitcher } from '@/components/LanguageSwitcher';
import { useGlobalContext } from '@/context/GlobalContext';

export function Header() {
  const { t } = useTranslation();
  const location = useLocation();
  const { state } = useGlobalContext();
  const considerationCount = state.considerationList.length;

  return (
    <header className="sticky top-0 z-40 w-full border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
      <div className="container flex h-16 items-center justify-between">
        <Link to="/" className="flex items-center space-x-2">
          <Heart className="h-6 w-6 text-primary" />
          <span className="text-xl font-bold">{t('header.title')}</span>
        </Link>

        <nav className="hidden md:flex items-center space-x-6">
          <Link
            to="/"
            className={`text-sm font-medium transition-colors hover:text-primary ${
              location.pathname === '/' ? 'text-primary' : 'text-muted-foreground'
            }`}
          >
            {t('header.home')}
          </Link>
          <Link
            to="/finder"
            className={`text-sm font-medium transition-colors hover:text-primary ${
              location.pathname === '/finder' ? 'text-primary' : 'text-muted-foreground'
            }`}
          >
            {t('header.finder')}
          </Link>
          {state.user && (
            <Link
              to="/consideration"
              className={`text-sm font-medium transition-colors hover:text-primary flex items-center space-x-1 ${
                location.pathname === '/consideration' ? 'text-primary' : 'text-muted-foreground'
              }`}
            >
              <BookmarkCheck className="h-4 w-4" />
              <span>{t('header.consideration')}</span>
              {considerationCount > 0 && (
                <Badge variant="default" className="ml-1">
                  {considerationCount}
                </Badge>
              )}
            </Link>
          )}
        </nav>

        <div className="flex items-center space-x-2">
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
            <div className="flex items-center space-x-2">
              <Link to="/consideration" className="relative">
                <Button variant="ghost" size="icon">
                  <BookmarkCheck className="h-4 w-4" />
                </Button>
                {considerationCount > 0 && (
                  <Badge 
                    variant="default" 
                    className="absolute -top-2 -right-2 h-5 w-5 flex items-center justify-center p-0 text-xs"
                  >
                    {considerationCount}
                  </Badge>
                )}
              </Link>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}