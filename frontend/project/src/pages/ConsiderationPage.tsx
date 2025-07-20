import { BookmarkCheck, Trash2 } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { Button } from '@/components/ui/Button';
import { ConsiderationCompanyCard } from '@/components/ConsiderationCompanyCard';
import { useGlobalContext } from '@/context/GlobalContext';
import { toast } from 'sonner';
import React from 'react';

export function ConsiderationPage() {
  const { t } = useTranslation();
  const { state, removeFromConsideration } = useGlobalContext();
  const { considerationList } = state;
  const [loadingBin, setLoadingBin] = React.useState<string | null>(null);
  const [clearing, setClearing] = React.useState(false);

  const handleRemoveCompany = async (bin: string) => {
    setLoadingBin(bin);
    try {
      await removeFromConsideration(bin);
      toast.success(t('consideration.companyRemoved'), { duration: 2000 });
    } catch (error) {
      toast.error(t('consideration.removeError') || 'Failed to remove company', { duration: 2000 });
    } finally {
      setLoadingBin(null);
    }
  };

  const handleClearAll = async () => {
    setClearing(true);
    try {
      for (const company of considerationList) {
        await removeFromConsideration(company.bin);
      }
      toast.success(t('consideration.cleared'), { duration: 2000 });
    } catch (error) {
      toast.error(t('consideration.clearError') || 'Failed to clear consideration list', { duration: 2000 });
    } finally {
      setClearing(false);
    }
  };

  if (considerationList.length === 0) {
    return (
      <div className="container mx-auto px-4 py-8">
        <div className="flex items-center justify-center min-h-[60vh]">
          <div className="text-center max-w-md">
            <BookmarkCheck className="h-16 w-16 text-muted-foreground mx-auto mb-4" />
            <h2 className="text-2xl font-bold mb-2">{t('consideration.empty.title')}</h2>
            <p className="text-muted-foreground mb-6">
              {t('consideration.empty.description')}
            </p>
            <Link 
              to="/finder"
              className="inline-flex items-center justify-center whitespace-nowrap rounded-md text-sm font-medium ring-offset-background transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50 bg-primary text-primary-foreground hover:bg-primary/90 h-10 px-4 py-2"
            >
              {t('consideration.empty.findSponsors')}
            </Link>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="container mx-auto px-4 py-8">
      <div className="mb-8">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold mb-2">{t('consideration.title')}</h1>
            <p className="text-muted-foreground">
              {considerationList.length === 1 
                ? t('consideration.count', { count: considerationList.length })
                : t('consideration.countPlural', { count: considerationList.length })
              }
            </p>
          </div>
          {considerationList.length > 0 && (
            <Button
              variant="outline"
              onClick={handleClearAll}
              disabled={clearing}
            >
              <Trash2 className="h-4 w-4 mr-2" />
              {clearing ? t('consideration.clearing') || t('consideration.clearAll') : t('consideration.clearAll')}
            </Button>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {considerationList.map((company) => (
          <div key={company.bin} className="relative">
            <ConsiderationCompanyCard company={company} />
            <Button
              variant="destructive"
              size="sm"
              className="absolute top-2 right-2"
              onClick={() => handleRemoveCompany(company.bin)}
              disabled={loadingBin === company.bin || clearing}
            >
              {loadingBin === company.bin ? (
                <span className="flex items-center"><span className="animate-spin mr-2 w-4 h-4 border-2 border-t-transparent border-white rounded-full"></span>{t('consideration.companyRemoved')}</span>
              ) : (
                <Trash2 className="h-4 w-4" />
              )}
            </Button>
          </div>
        ))}
      </div>

      <div className="mt-12 p-6 bg-muted/30 rounded-lg">
        <h3 className="text-lg font-semibold mb-2">{t('consideration.nextSteps.title')}</h3>
        <ul className="space-y-2 text-sm text-muted-foreground">
          <li>{t('consideration.nextSteps.step1')}</li>
          <li>{t('consideration.nextSteps.step2')}</li>
          <li>{t('consideration.nextSteps.step3')}</li>
          <li>{t('consideration.nextSteps.step4')}</li>
        </ul>
      </div>
    </div>
  );
}