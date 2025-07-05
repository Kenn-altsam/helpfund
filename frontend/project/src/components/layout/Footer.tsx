import { Heart } from 'lucide-react';
import { useTranslation } from 'react-i18next';

export function Footer() {
  const { t } = useTranslation();

  return (
    <footer className="border-t bg-background">
      <div className="container px-12 py-12">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-12">
          <div className="space-y-4 text-center">
            <div className="flex items-center justify-center space-x-2">
              <Heart className="h-5 w-5 text-primary" />
              <span className="font-bold">{t('header.title')}</span>
            </div>
            <p className="text-sm text-muted-foreground">
              {t('footer.description')}
            </p>
          </div>
          
          <div className="space-y-6 text-center">
            <h4 className="font-semibold text-base">{t('footer.about')}</h4>
            <ul className="space-y-4 text-sm text-muted-foreground text-center">
              <li><a href="#" className="hover:text-primary transition-colors">{t('footer.mission')}</a></li>
              <li><a href="#" className="hover:text-primary transition-colors">{t('footer.team')}</a></li>
              <li><a href="#" className="hover:text-primary transition-colors">{t('footer.reports')}</a></li>
            </ul>
          </div>
          
          <div className="space-y-6">
            <h4 className="font-semibold text-base text-center">{t('footer.services')}</h4>
            <div className="text-center">
              <a href="#" className="text-sm text-muted-foreground hover:text-primary transition-colors">
                {t('footer.sponsorSearch')}
              </a>
            </div>
          </div>
          
          <div className="space-y-6 text-center">
            <h4 className="font-semibold text-base">{t('footer.contacts')}</h4>
            <ul className="space-y-4 text-sm text-muted-foreground text-center">
              <li>
                <a href="tel:+77271234567" className="hover:text-primary transition-colors">
                  +7 (727) 123-45-67
                </a>
              </li>
              <li>
                <a href="mailto:info@helpfund.pro" className="hover:text-primary transition-colors">
                  info@helpfund.pro
                </a>
              </li>
              <li>г. Алматы, ул. Абая 150</li>
            </ul>
          </div>
        </div>
        
        <div className="mt-12 pt-8 border-t text-sm text-center text-muted-foreground">
          <p>{t('footer.copyright')}</p>
        </div>
      </div>
    </footer>
  );
}