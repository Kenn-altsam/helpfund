import { Link } from 'react-router-dom';
import { Search, Target, Heart, Shield, Zap } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/Button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card';
import { cn } from '@/lib/utils';

export function HomePage() {
  const { t } = useTranslation();

  const scrollToFinder = () => {
    const finderSection = document.getElementById('finder-section');
    if (finderSection) {
      finderSection.scrollIntoView({ behavior: 'smooth' });
    }
  };

  const buttonBaseClasses = 'inline-flex items-center justify-center whitespace-nowrap rounded-md text-sm font-medium ring-offset-background transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50 h-11 rounded-md px-8 text-lg touch-target';
  
  const buttonVariants = {
    default: 'bg-primary text-primary-foreground hover:bg-primary/90',
    outline: 'border border-input bg-background hover:bg-accent hover:text-accent-foreground'
  };

  return (
    <div className="min-h-screen mobile-container">
      {/* Hero Section */}
      <section className="relative py-12 md:py-20 px-4 bg-gradient-to-br from-primary/5 via-background to-secondary/5 safe-area-top">
        <div className="container mx-auto text-center">
          <div className="max-w-4xl mx-auto">
            <h1 className="text-3xl md:text-4xl lg:text-6xl font-bold tracking-tight mb-4 md:mb-6 leading-tight">
              {t('home.hero.title')}
            </h1>
            <p className="text-lg md:text-xl text-muted-foreground mb-6 md:mb-8 leading-relaxed px-2">
              {t('home.hero.subtitle')}
            </p>
            <div className="flex flex-col sm:flex-row gap-4 justify-center">
              <Button size="lg" onClick={scrollToFinder} className="text-lg px-8 touch-target mobile-button">
                <Search className="mr-2 h-5 w-5" />
                {t('home.hero.findSponsors')}
              </Button>
            </div>
          </div>
        </div>
      </section>

      {/* Features Section */}
      <section className="py-12 md:py-20 px-4">
        <div className="container mx-auto">
          <div className="text-center mb-12 md:mb-16">
            <h2 className="text-2xl md:text-3xl lg:text-4xl font-bold mb-4 leading-tight">
              {t('home.features.title')}
            </h2>
            <p className="text-lg md:text-xl text-muted-foreground max-w-2xl mx-auto px-2">
              {t('home.features.subtitle')}
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-6 md:gap-8 mobile-grid">
            <Card className="text-center hover:shadow-lg transition-shadow mobile-card">
              <CardHeader className="pb-3">
                <div className="w-12 h-12 bg-primary/10 rounded-lg flex items-center justify-center mx-auto mb-4">
                  <Zap className="h-6 w-6 text-primary" />
                </div>
                <CardTitle className="text-lg md:text-xl">{t('home.features.aiSearch.title')}</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-muted-foreground mobile-text-base">
                  {t('home.features.aiSearch.description')}
                </p>
              </CardContent>
            </Card>

            <Card className="text-center hover:shadow-lg transition-shadow mobile-card">
              <CardHeader className="pb-3">
                <div className="w-12 h-12 bg-primary/10 rounded-lg flex items-center justify-center mx-auto mb-4">
                  <Shield className="h-6 w-6 text-primary" />
                </div>
                <CardTitle className="text-lg md:text-xl">{t('home.features.verifiedData.title')}</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-muted-foreground mobile-text-base">
                  {t('home.features.verifiedData.description')}
                </p>
              </CardContent>
            </Card>

            <Card className="text-center hover:shadow-lg transition-shadow mobile-card">
              <CardHeader className="pb-3">
                <div className="w-12 h-12 bg-primary/10 rounded-lg flex items-center justify-center mx-auto mb-4">
                  <Target className="h-6 w-6 text-primary" />
                </div>
                <CardTitle className="text-lg md:text-xl">{t('home.features.personalization.title')}</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-muted-foreground mobile-text-base">
                  {t('home.features.personalization.description')}
                </p>
              </CardContent>
            </Card>
          </div>
        </div>
      </section>

      {/* Stats Section */}
      <section className="py-12 md:py-20 px-4 bg-secondary/5">
        <div className="container mx-auto">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6 md:gap-8 text-center mobile-grid">
            <div>
              <div className="text-3xl md:text-4xl font-bold text-primary mb-2">2500+</div>
              <p className="text-muted-foreground mobile-text-base">{t('home.stats.companies')}</p>
            </div>
            <div>
              <div className="text-3xl md:text-4xl font-bold text-primary mb-2">17</div>
              <p className="text-muted-foreground mobile-text-base">{t('home.stats.regions')}</p>
            </div>
            <div>
              <div className="text-3xl md:text-4xl font-bold text-primary mb-2">24/7</div>
              <p className="text-muted-foreground mobile-text-base">{t('home.stats.availability')}</p>
            </div>
          </div>
        </div>
      </section>

      {/* CTA Section */}
      <section id="finder-section" className="py-12 md:py-20 px-4">
        <div className="container mx-auto text-center">
          <div className="max-w-3xl mx-auto">
            <Heart className="h-12 w-12 md:h-16 md:w-16 text-primary mx-auto mb-4 md:mb-6" />
            <h2 className="text-2xl md:text-3xl lg:text-4xl font-bold mb-4 md:mb-6 leading-tight">
              {t('home.cta.title')}
            </h2>
            <p className="text-lg md:text-xl text-muted-foreground mb-6 md:mb-8 px-2">
              {t('home.cta.subtitle')}
            </p>
            <Link 
              to="/finder" 
              className={cn(buttonBaseClasses, buttonVariants.default)}
            >
              <Search className="mr-2 h-5 w-5" />
              {t('home.cta.startSearch')}
            </Link>
          </div>
        </div>
      </section>

      {/* About Section */}
      <section className="py-12 md:py-20 px-4 bg-muted/30 safe-area-bottom">
        <div className="container mx-auto">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 md:gap-12 items-center mobile-grid">
            <div>
              <h2 className="text-2xl md:text-3xl lg:text-4xl font-bold mb-4 md:mb-6 leading-tight">
                {t('home.about.title')}
              </h2>
              <p className="text-base md:text-lg text-muted-foreground mb-4 md:mb-6 leading-relaxed">
                {t('home.about.description1')}
              </p>
              <p className="text-base md:text-lg text-muted-foreground mb-6 md:mb-8 leading-relaxed">
                {t('home.about.description2')}
              </p>
            </div>
            <div className="relative order-first lg:order-last">
              <img
                src="https://images.pexels.com/photos/3184465/pexels-photo-3184465.jpeg?auto=compress&cs=tinysrgb&w=800"
                alt="Команда helpfund.pro"
                className="rounded-lg shadow-lg w-full h-64 md:h-96 object-cover"
              />
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}