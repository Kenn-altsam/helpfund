import { Bot } from 'lucide-react';
import { CompanyCard } from './CompanyCard';
import { CompanyCardSkeleton } from './CompanyCardSkeleton';
import { Company } from '@/types';

interface ChatMessageProps {
  type: 'user' | 'assistant' | 'loading';
  content?: string;
  companies?: Company[];
}

export function ChatMessage({ type, content, companies }: ChatMessageProps) {
  if (type === 'loading') {
    return (
      <div className="flex items-start space-x-3 mb-6">
        <div className="flex-shrink-0 w-8 h-8 bg-primary rounded-full flex items-center justify-center">
          <Bot className="h-4 w-4 text-primary-foreground" />
        </div>
        <div className="flex-1 space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {Array.from({ length: 4 }).map((_, i) => (
              <CompanyCardSkeleton key={i} />
            ))}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex items-start space-x-3 mb-6">
      {type === 'assistant' && (
        <div className="flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center bg-primary">
          <Bot className="h-4 w-4 text-primary-foreground" />
        </div>
      )}
      
      <div className="flex-1">
        {content && (
          <div className={`rounded-lg p-3 mb-3 ${
            type === 'user' 
              ? 'bg-secondary text-secondary-foreground ml-auto max-w-xs' 
              : 'bg-muted text-muted-foreground'
          }`}>
            <p className="text-sm">{content}</p>
          </div>
        )}
        
        {companies && companies.length > 0 && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {companies.map((company) => (
              <CompanyCard key={company.bin} company={company} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}