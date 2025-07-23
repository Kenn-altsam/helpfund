import React, { useState } from 'react';
import { Plus, Check, Loader2, Search } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Badge } from '@/components/ui/Badge';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/Dialog';
import { Company, CompanyCharityResponse, GoogleSearchResult } from '@/types';
import { useGlobalContext } from '@/context/GlobalContext';
import { charityApi } from '@/services/api';
import { toast } from 'sonner';

interface CompanyCharityCardProps {
  company: Company;
}

export function CompanyCharityCard({ company }: CompanyCharityCardProps) {
  const { t } = useTranslation();
  const { addToConsideration, isInConsideration } = useGlobalContext();
  const isAdded = isInConsideration(company.bin);
  
  const [loading, setLoading] = useState(false);
  const [charityLoading, setCharityLoading] = useState(false);
  const [charityResults, setCharityResults] = useState<CompanyCharityResponse | null>(null);
  const [isDialogOpen, setIsDialogOpen] = useState(false);

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

  const handleCharityResearch = async () => {
    if (!company.name) {
      toast.error('Название компании недоступно', { duration: 2000 });
      return;
    }

    setCharityLoading(true);
    setCharityResults(null);

    try {
      const response = await charityApi.researchCompany({
        company_name: company.name,
      });
      setCharityResults(response);
      setIsDialogOpen(true);
    } catch (error: any) {
      const errorMessage = error.response?.data?.detail || error.message || 'Ошибка при исследовании благотворительности';
      toast.error(errorMessage, { duration: 3000 });
    } finally {
      setCharityLoading(false);
    }
  };

  return (
    <>
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
            <b>{t("company.contacts")}:</b> {company.contacts !== undefined && company.contacts !== null && company.contacts !== '' ? company.contacts : t("company.contacts_missing")}
          </div>
          {/* Show website */}
          <div className="text-xs">
            <b>{t("company.website")}:</b>{" "}
            {company.website !== undefined && company.website !== null && company.website !== '' ? (
              <a
                href={
                  company.website.startsWith('http://') || company.website.startsWith('https://')
                    ? company.website
                    : `https://${company.website}`
                }
                target="_blank"
                rel="noopener noreferrer"
                className="text-blue-600 underline"
              >
                {company.website}
              </a>
            ) : t("company.website_missing")}
          </div>
        </CardContent>

        <CardFooter className="flex flex-col space-y-2">
          {/* Кнопка добавления в рассмотрение */}
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

          {/* Кнопка исследования благотворительности */}
          <Button
            onClick={handleCharityResearch}
            disabled={charityLoading || !company.name}
            className="w-full"
            variant="outline"
          >
            {charityLoading ? (
              <>
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                Исследую...
              </>
            ) : (
              <>
                <Search className="h-4 w-4 mr-2" />
                Благотворительность
              </>
            )}
          </Button>
        </CardFooter>
      </Card>

      {/* Диалог с результатами исследования */}
      <Dialog open={isDialogOpen} onOpenChange={setIsDialogOpen}>
        <DialogContent className="max-w-4xl max-h-[80vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>
              Исследование благотворительности: {charityResults?.company_name}
            </DialogTitle>
          </DialogHeader>

          {charityResults && (
            <div className="space-y-4">
              {/* Статус и сводка */}
              <div className={`p-4 rounded-lg ${
                charityResults.status === 'success' ? 'bg-green-50 border border-green-200' : 'bg-red-50 border border-red-200'
              }`}>
                <div className={`font-medium ${
                  charityResults.status === 'success' ? 'text-green-800' : 'text-red-800'
                }`}>
                  {charityResults.status === 'success' ? '✅ Поиск завершен' : '❌ Ошибка поиска'}
                </div>
                <p className={`text-sm mt-2 ${
                  charityResults.status === 'success' ? 'text-green-700' : 'text-red-700'
                }`}>
                  {charityResults.summary}
                </p>
              </div>

              {/* Найденные результаты поиска */}
              {charityResults.charity_info && charityResults.charity_info.length > 0 && (
                <div>
                  <h4 className="text-lg font-medium mb-3">
                    Найдено материалов: {charityResults.charity_info.length}
                  </h4>
                  
                  <div className="space-y-3 max-h-96 overflow-y-auto">
                    {charityResults.charity_info.map((item: GoogleSearchResult, index: number) => (
                      <div key={index} className="border border-gray-200 rounded-lg p-4 hover:bg-gray-50">
                        <h5 className="font-medium text-blue-600 hover:text-blue-800">
                          <a 
                            href={item.link} 
                            target="_blank" 
                            rel="noopener noreferrer"
                            className="hover:underline"
                          >
                            {item.title}
                          </a>
                        </h5>
                        <p className="text-sm text-gray-600 mt-2">
                          {item.snippet}
                        </p>
                        <div className="text-xs text-gray-400 mt-2">
                          <a 
                            href={item.link} 
                            target="_blank" 
                            rel="noopener noreferrer"
                            className="hover:underline break-all"
                          >
                            {item.link}
                          </a>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Если результатов нет */}
              {charityResults.charity_info && charityResults.charity_info.length === 0 && (
                <div className="text-center py-8 text-gray-500">
                  <p>По запросу не найдено информации о благотворительной деятельности.</p>
                </div>
              )}
            </div>
          )}
        </DialogContent>
      </Dialog>
    </>
  );
} 