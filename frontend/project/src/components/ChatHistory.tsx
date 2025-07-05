import { MessageSquare, Trash2 } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/Button';
import { ChatHistoryItem } from '@/types';
import { formatDate, truncateText } from '@/lib/utils';

interface ChatHistoryProps {
  history: ChatHistoryItem[];
  onSelectHistory: (item: ChatHistoryItem) => void;
  onDeleteHistory: (id: string) => void;
}

export function ChatHistory({ history, onSelectHistory, onDeleteHistory }: ChatHistoryProps) {
  const { t } = useTranslation();

  if (history.length === 0) {
    return (
      <div className="p-4 text-center text-muted-foreground">
        <MessageSquare className="h-8 w-8 mx-auto mb-2 opacity-50" />
        <p className="text-sm">{t('finder.historyEmpty')}</p>
      </div>
    );
  }

  return (
    <div className="space-y-2 p-4">
      {history.map((item) => (
        <div
          key={item.id}
          className="group flex items-center justify-between p-3 rounded-lg hover:bg-accent cursor-pointer transition-colors"
          onClick={() => onSelectHistory(item)}
        >
          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium truncate">
              {truncateText(item.userPrompt, 40)}
            </p>
            <p className="text-xs text-muted-foreground">
              {formatDate(item.created_at)} • {item.aiResponse.length}
            </p>
          </div>
          
          <Button
            variant="ghost"
            size="icon"
            className="opacity-0 group-hover:opacity-100 transition-opacity"
            onClick={(e) => {
              e.stopPropagation();
              onDeleteHistory(item.id);
            }}
          >
            <Trash2 className="h-4 w-4" />
          </Button>
        </div>
      ))}
    </div>
  );
}