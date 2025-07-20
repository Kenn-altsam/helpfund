import { useState } from "react";
import { Heart, Loader2, AlertCircle } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/Button';
import { Skeleton } from '@/components/ui/Skeleton';

interface CompanyCharityInfoProps {
  companyName: string;
}

interface CharityResponse {
  status: 'success' | 'error' | 'warning';
  answer: string;
}

export const CompanyCharityInfo = ({ companyName }: CompanyCharityInfoProps) => {
  const { t } = useTranslation();
  const [info, setInfo] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState<'success' | 'error' | 'warning' | null>(null);

  const linkify = (text: string) => {
    const urlRegex = /(https?:\/\/[^\s]+)/g;

    return text.replace(urlRegex, (url) => {
      try {
        const urlObj = new URL(url);
        const shortText = `${urlObj.hostname}${urlObj.pathname.length > 30 ? "/..." : urlObj.pathname}`;
        return `<a href="${url}" target="_blank" class="text-blue-600 underline">${shortText}</a>`;
      } catch {
        return url;
      }
    });
  };

  const fetchInfo = async () => {
    setLoading(true);
    setInfo(null);
    setStatus(null);
    
    try {
      const res = await fetch("/api/v1/ai/charity-research", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${localStorage.getItem("access_token")}`,
        },
        body: JSON.stringify({ company_name: companyName }),
      });
      
      if (!res.ok) {
        throw new Error(`HTTP error! status: ${res.status}`);
      }
      
      const data: CharityResponse = await res.json();
      setInfo(data.answer);
      setStatus(data.status);
    } catch (err) {
      console.error('Charity research error:', err);
      setInfo(t('company.charity.noData'));
      setStatus('warning');
    } finally {
      setLoading(false);
    }
  };

  const getStatusColor = () => {
    switch (status) {
      case 'success':
        return 'border-green-200 bg-green-50';
      case 'warning':
        return 'border-yellow-200 bg-yellow-50';
      case 'error':
        return 'border-red-200 bg-red-50';
      default:
        return 'border-gray-200 bg-gray-50';
    }
  };

  const getStatusIcon = () => {
    switch (status) {
      case 'success':
        return <Heart className="h-4 w-4 text-green-600" />;
      case 'warning':
        return <AlertCircle className="h-4 w-4 text-yellow-600" />;
      case 'error':
        return <AlertCircle className="h-4 w-4 text-red-600" />;
      default:
        return <Heart className="h-4 w-4 text-gray-600" />;
    }
  };

  return (
    <div className="mt-3">
      <Button
        onClick={fetchInfo}
        variant="outline"
        size="sm"
        className={`w-full text-xs transition-all duration-200 ${loading ? 'opacity-75 cursor-not-allowed' : 'hover:bg-gray-50'}`}
        disabled={loading}
      >
        {loading ? (
          <>
            <Loader2 className="h-3 w-3 mr-2 animate-spin" />
            {t('company.charity.loading')}
          </>
        ) : (
          <>
            <Heart className="h-3 w-3 mr-2" />
            {t('company.charity.button')}
          </>
        )}
      </Button>
      
      {loading && (
        <div className="mt-2 p-3 rounded-md border border-gray-200 bg-gray-50 animate-pulse">
          <div className="flex items-start gap-2">
            <Skeleton className="h-4 w-4 rounded-full" />
            <div className="flex-1 space-y-2">
              <Skeleton className="h-3 w-full" />
              <Skeleton className="h-3 w-3/4" />
              <Skeleton className="h-3 w-1/2" />
              <Skeleton className="h-3 w-2/3" />
            </div>
          </div>
        </div>
      )}
      
      {info && !loading && (
        <div className={`mt-2 p-3 rounded-md border text-xs whitespace-pre-wrap transition-all duration-300 ease-in-out ${getStatusColor()}`}>
          <div className="flex items-start gap-2">
            {getStatusIcon()}
            <div 
              className="flex-1"
              dangerouslySetInnerHTML={{ __html: linkify(info) }}
            />
          </div>
        </div>
      )}
    </div>
  );
}; 