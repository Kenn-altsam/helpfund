import { Plus, Check, Loader2 } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Badge } from '@/components/ui/Badge';
import { Company } from '@/types';
import { useGlobalContext } from '@/context/GlobalContext';
import { toast } from 'sonner';
import React from 'react';

interface CompanyCardProps {
  company: Company;
}

export function CompanyCard({ company }: CompanyCardProps) {
  const { t } = useTranslation();
  const { addToConsideration, isInConsideration } = useGlobalContext();
  const isAdded = isInConsideration(company.bin);
  const [loading, setLoading] = React.useState(false);

  const handleAddToConsideration = async () => {
    if (!isAdded && !loading) {
      setLoading(true);
      try {
        await addToConsideration(company);
        toast.success(t('company.companyAdded'), { duration: 2000 });
      } catch (error) {
        toast.error(t('company.addError') || 'Failed to add company', { duration: 2000 });
      } finally {
        setLoading(false);
      }
    }
  };

  return (
    <Card className="w-full hover:shadow-md transition-shadow">
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between">
          <div className="space-y-1">
            <CardTitle className="text-lg leading-tight">{company.name}</CardTitle>
            <div className="flex items-center space-x-2">
              <Badge variant="outline" className="text-xs">
                {t('company.bin')}: {company.bin}
              </Badge>
            </div>
          </div>
        </div>
      </CardHeader>

      <CardContent className="space-y-3">
        {/* Show tax_data_2023 */}
        <div className="text-xs">
          <b>{t("company.tax_2023")}:</b> {company.tax_data_2023 !== undefined && company.tax_data_2023 !== null ? company.tax_data_2023 : t("company.tax_2023_missing")}
        </div>
        {/* Show tax_data_2024 */}
        <div className="text-xs">
          <b>{t("company.tax_2024")}:</b> {company.tax_data_2024 !== undefined && company.tax_data_2024 !== null ? company.tax_data_2024 : t("company.tax_2024_missing")}
        </div>
        {/* Show tax_data_2025 */}
        <div className="text-xs">
          <b>{t("company.tax_2025")}:</b> {company.tax_data_2025 !== undefined && company.tax_data_2025 !== null ? company.tax_data_2025 : t("company.tax_2025_missing")}
        </div>
        {/* Show contacts */}
        <div className="text-xs">
          <b>{t("company.contacts")}:</b>{" "}
          {company.contacts !== undefined && company.contacts !== null && company.contacts !== '' ? (
            <span className="flex items-center gap-1">
              <span>{company.contacts}</span>
              <span className="inline-flex items-center px-1.5 py-0.5 rounded text-xs font-medium bg-green-100 text-green-800">
                🌐 найдено
              </span>
            </span>
          ) : (
            <span className="text-gray-500">{t("company.contacts_missing")}</span>
          )}
        </div>
        {/* Show website */}
        <div className="text-xs">
          <b>{t("company.website")}:</b>{" "}
          {company.website !== undefined && company.website !== null && company.website !== '' ? (
            <span className="flex items-center gap-1">
              <a
                href={
                  company.website.startsWith('http://') || company.website.startsWith('https://')
                    ? company.website
                    : `https://${company.website}`
                }
                target="_blank"
                rel="noopener noreferrer"
                className="text-blue-600 underline break-all"
              >
                {company.website}
              </a>
              <span className="inline-flex items-center px-1.5 py-0.5 rounded text-xs font-medium bg-green-100 text-green-800">
                🌐 найдено
              </span>
            </span>
          ) : (
            <span className="text-gray-500">{t("company.website_missing")}</span>
          )}
        </div>
      </CardContent>

      <CardFooter>
        <Button
          onClick={handleAddToConsideration}
          disabled={isAdded || loading}
          className="w-full"
          variant={isAdded ? 'secondary' : 'default'}
        >
          {loading ? (
            <>
              <Loader2 className="h-4 w-4 mr-2 animate-spin" />
              {t('company.addToConsideration')}
            </>
          ) : isAdded ? (
            <>
              <Check className="h-4 w-4 mr-2" />
              {t('company.addedToConsideration')}
            </>
          ) : (
            <>
              <Plus className="h-4 w-4 mr-2" />
              {t('company.addToConsideration')}
            </>
          )}
        </Button>
      </CardFooter>
    </Card>
  );
}