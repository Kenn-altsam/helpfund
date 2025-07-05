import React from 'react';
import { ExternalLink, Phone, Mail, Plus, Check } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Badge } from '@/components/ui/Badge';
import { Company } from '@/types';
import { useGlobalContext } from '@/context/GlobalContext';
import { toast } from 'sonner';

interface CompanyCardProps {
  company: Company;
}

export function CompanyCard({ company }: CompanyCardProps) {
  const { t } = useTranslation();
  const { addToConsideration, isInConsideration } = useGlobalContext();
  const isAdded = isInConsideration(company.bin);

  const handleAddToConsideration = () => {
    if (!isAdded) {
      addToConsideration(company);
      toast.success(t('company.companyAdded'), { duration: 3000 });
    }
  };

  const parseContacts = (contacts?: string) => {
    if (!contacts) return { phone: null, email: null };
    
    const phoneMatch = contacts.match(/\+7\s?\(\d{3,4}\)\s?\d{3}-\d{2}-\d{2}/);
    const emailMatch = contacts.match(/[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}/);
    
    return {
      phone: phoneMatch ? phoneMatch[0] : null,
      email: emailMatch ? emailMatch[0] : null,
    };
  };

  const { phone, email } = parseContacts(company.contacts);

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
              {company.region && (
                <Badge variant="secondary" className="text-xs">
                  {company.region}
                </Badge>
              )}
            </div>
          </div>
        </div>
      </CardHeader>

      <CardContent className="space-y-3">
        {company.industry && (
          <div>
            <p className="text-sm font-medium text-muted-foreground">{t('company.industry')}</p>
            <p className="text-sm">{company.industry}</p>
          </div>
        )}

        <div>
          <p className="text-sm font-medium text-muted-foreground">{t('company.taxes')}</p>
          <p className="text-sm">{company.taxes}</p>
        </div>

        {company.website && (
          <div>
            <p className="text-sm font-medium text-muted-foreground">{t('company.website')}</p>
            <a
              href={company.website}
              target="_blank"
              rel="noopener noreferrer"
              className="text-sm text-primary hover:underline flex items-center space-x-1"
            >
              <span>{company.website}</span>
              <ExternalLink className="h-3 w-3" />
            </a>
          </div>
        )}

        {(phone || email) && (
          <div>
            <p className="text-sm font-medium text-muted-foreground">{t('company.contacts')}</p>
            <div className="flex flex-wrap gap-2 mt-1">
              {phone && (
                <a
                  href={`tel:${phone}`}
                  className="text-sm text-primary hover:underline flex items-center space-x-1"
                >
                  <Phone className="h-3 w-3" />
                  <span>{phone}</span>
                </a>
              )}
              {email && (
                <a
                  href={`mailto:${email}`}
                  className="text-sm text-primary hover:underline flex items-center space-x-1"
                >
                  <Mail className="h-3 w-3" />
                  <span>{email}</span>
                </a>
              )}
            </div>
          </div>
        )}
      </CardContent>

      <CardFooter>
        <Button
          onClick={handleAddToConsideration}
          disabled={isAdded}
          className="w-full"
          variant={isAdded ? 'secondary' : 'default'}
        >
          {isAdded ? (
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