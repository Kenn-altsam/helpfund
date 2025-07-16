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
        {/* Only show fields that exist on Company type */}
        {company.tax_data_2023 !== undefined && (
          <div className="text-xs">
            <b>Tax 2023:</b> {company.tax_data_2023}
          </div>
        )}
        {company.tax_data_2024 !== undefined && (
          <div className="text-xs">
            <b>Tax 2024:</b> {company.tax_data_2024}
          </div>
        )}
        {company.tax_data_2025 !== undefined && (
          <div className="text-xs">
            <b>Tax 2025:</b> {company.tax_data_2025}
          </div>
        )}
        {company.contacts && (
          <div className="text-xs">
            <b>Contacts:</b> {company.contacts}
          </div>
        )}
        {company.website && (
          <div className="text-xs">
            <b>Website:</b> <a href={company.website} target="_blank" rel="noopener noreferrer" className="text-blue-600 underline">{company.website}</a>
          </div>
        )}
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