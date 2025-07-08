import React, { useState, useRef, useEffect } from 'react';
import { Send, Menu, X, MessageSquare, User, Heart } from 'lucide-react';
import { Link, useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { ChatMessage } from '@/components/ChatMessage';
import { ChatHistory } from '@/components/ChatHistory';
import { useGlobalContext } from '@/context/GlobalContext';
import { chatApi, historyApi } from '@/services/api';
import { ChatHistoryItem, Company } from '@/types';
import { generateId } from '@/lib/utils';
import { toast } from 'sonner';

interface Message {
  id: string;
  type: 'user' | 'assistant' | 'loading';
  content?: string;
  companies?: Company[];
  createdAt?: number | string;
}

export function FinderPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { state, dispatch } = useGlobalContext();
  const { user, history: globalHistory } = state;

  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);

  // --- 💡 ИЗМЕНЕНИЕ 1: Читаем начальные значения из sessionStorage ---
  const [assistantId, setAssistantId] = useState<string | null>(() => sessionStorage.getItem('activeAssistantId'));
  const [threadId, setThreadId] = useState<string | null>(() => sessionStorage.getItem('activeThreadId'));

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  /* ------------------------------------------------------------------
   * Persist assistant & thread IDs in sessionStorage when they change
   * ------------------------------------------------------------------ */
  // --- 💡 ИЗМЕНЕНИЕ 2: Сохраняем ID в sessionStorage при их изменении ---
  useEffect(() => {
    if (assistantId) {
      sessionStorage.setItem('activeAssistantId', assistantId);
    } else {
      sessionStorage.removeItem('activeAssistantId'); // Очищаем, если ID стал null
    }
  }, [assistantId]);

  useEffect(() => {
    if (threadId) {
      sessionStorage.setItem('activeThreadId', threadId);
    } else {
      sessionStorage.removeItem('activeThreadId'); // Очищаем, если ID стал null
    }
  }, [threadId]);

  /* --------------------------- Scroll helpers --------------------------- */
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  /* ------------------------------------------------------------------
   * Load global history & restore active chat on mount
   * ------------------------------------------------------------------ */
  // --- 💡 ИЗМЕНЕНИЕ: Улучшенная логика восстановления чата ---
  useEffect(() => {
    const loadInitialData = async () => {
      try {
        // 1. Сначала загружаем список всех чатов для боковой панели
        const historyList = await historyApi.getHistory();
        dispatch({ type: 'LOAD_HISTORY', payload: historyList });

        // 2. Проверяем, есть ли активный чат в sessionStorage
        const activeThreadId = sessionStorage.getItem('activeThreadId');
        if (!activeThreadId) {
          return; // Нет активного чата, выходим
        }

        // 3. Пытаемся найти сохраненную сводку чата
        let activeHistoryItem = historyList.find(h => h.threadId === activeThreadId);

        // 4. Если сводка НЕ НАЙДЕНА, но ID треда есть - это "потерянный" чат. Восстанавливаем его!
        if (!activeHistoryItem) {
          console.warn(`History item for thread ${activeThreadId} not found. Attempting to recover...`);
          try {
            const assistantIdFromStorage = sessionStorage.getItem('activeAssistantId');
            if (!assistantIdFromStorage) {
              // Если нет и assistantId, восстановить невозможно
              throw new Error('Cannot recover chat: missing assistantId in sessionStorage.');
            }

            // Пытаемся загрузить историю напрямую из треда OpenAI
            const recoveredHistory = await chatApi.getConversationHistory(
              assistantIdFromStorage,
              activeThreadId
            );

            // Если история в треде не пуста, значит, чат реален
            if (recoveredHistory.length > 0) {
              console.log(`Successfully recovered ${recoveredHistory.length} messages.`);
              // Создаем временный элемент истории, чтобы UI мог с ним работать
              const tempHistoryItem: ChatHistoryItem = {
                id: generateId(),
                // Берем первый промпт пользователя как заголовок
                userPrompt: recoveredHistory.find(m => m.role === 'user')?.content || 'Восстановленный чат',
                aiResponse: [], // Не знаем точного ответа, но это не так важно
                created_at: new Date().toISOString(),
                threadId: activeThreadId,
                assistantId: assistantIdFromStorage,
              };

              // Добавляем временный элемент в глобальное состояние, чтобы он появился в сайдбаре
              dispatch({ type: 'ADD_HISTORY', payload: tempHistoryItem });

              // Делаем его активным для дальнейшей работы
              activeHistoryItem = tempHistoryItem;
            } else {
              // История пуста, значит, это "мертвый" ID. Начинаем новый чат.
              startNewChat();
              return;
            }
          } catch (recoveryError) {
            console.error('Failed to recover chat:', recoveryError);
            startNewChat(); // Если восстановление не удалось, сбрасываем
            return;
          }
        }

        // 5. Если у нас есть item (старый или восстановленный), загружаем его
        if (activeHistoryItem) {
          await handleSelectHistory(activeHistoryItem, true);
        }
      } catch (error) {
        console.error('Failed to load initial history:', error);
      }
    };

    if (user) {
      loadInitialData();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [dispatch, user]);

  /* ------------------------------ Handlers ------------------------------ */
  const handleSendMessage = async () => {
    if (!input.trim() || isLoading) return;

    const userMessage: Message = { id: generateId(), type: 'user', content: input.trim() };
    const loadingMessage: Message = { id: generateId(), type: 'loading' };

    setMessages(prev => [...prev, userMessage, loadingMessage]);

    const currentInput = input.trim();
    setInput('');
    setIsLoading(true);

    try {
      const previousMessages = messages
        .filter(m => m.type === 'user' || m.type === 'assistant')
        .map(m => ({
          role: m.type as 'user' | 'assistant',
          content: m.content || '',
        }));

      const requestPayload = {
        user_input: currentInput,
        history: previousMessages,
        assistant_id: assistantId || undefined,
        thread_id: threadId || undefined,
      };

      const response = await chatApi.sendMessage(requestPayload);

      // Persist IDs returned by backend
      if (response.assistant_id) setAssistantId(response.assistant_id);
      if (response.thread_id) setThreadId(response.thread_id);

      // Replace loading message with assistant response
      setMessages(prev => {
        const withoutLoading = prev.filter(m => m.type !== 'loading');
        return [
          ...withoutLoading,
          {
            id: generateId(),
            type: 'assistant',
            content: response.message ?? t('finder.response', { count: response.companies?.length || 0 }),
            companies: response.companies || [],
          },
        ];
      });

      /* --------------------- HISTORY MANAGEMENT --------------------- */
      const effectiveThreadId = response.thread_id || threadId;
      if (effectiveThreadId) {
        const existingChat = globalHistory.find(h => h.threadId === effectiveThreadId);

        // Persist full history item in backend
        await historyApi.saveHistory({
          id: existingChat?.id,
          userPrompt: currentInput,
          rawAiResponse: response.rawCompanies || [],
          created_at: new Date().toISOString(),
          threadId: effectiveThreadId,
          assistantId: response.assistant_id || assistantId,
        });

        const updatedHistoryItem: ChatHistoryItem = {
          id: existingChat?.id || generateId(),
          userPrompt: currentInput,
          aiResponse: response.companies || [],
          created_at: new Date().toISOString(),
          threadId: effectiveThreadId,
          assistantId: response.assistant_id || assistantId,
        };

        if (existingChat) {
          dispatch({ type: 'UPDATE_HISTORY', payload: updatedHistoryItem });
        } else {
          dispatch({ type: 'ADD_HISTORY', payload: updatedHistoryItem });
        }
      }

      if (response.companies?.length) {
        toast.success(t('finder.companiesFound', { count: response.companies.length }), { duration: 2000 });
      }
    } catch (error) {
      console.error('Failed to send message:', error);
      setMessages(prev => prev.filter(m => m.type !== 'loading'));
      toast.error(t('finder.searchError'), { duration: 2000 });
    } finally {
      setIsLoading(false);
      inputRef.current?.focus();
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  const handleSelectHistory = async (
    item: ChatHistoryItem,
    keepSidebarOpen = false,
  ) => {
    // fast-return if already selected
    if (item.threadId === threadId && messages.length) {
      if (!keepSidebarOpen) setSidebarOpen(false);
      return;
    }

    // optimistic UI while fetching
    setIsLoading(true);
    setMessages([]);

    try {
      if (!item.threadId || !item.assistantId) {
        throw new Error('Missing threadId / assistantId');
      }

      /** 1 ▶ fetch raw history (backend MUST include metadata.companies) */
      const history = await chatApi.getConversationHistory(
        item.assistantId,
        item.threadId,
      );

      /** 2 ▶ normalise every record to your local Message type */
      const normalised: Message[] = history.map((h: any) => ({
        id: h.id ?? generateId(),
        type: h.role as 'user' | 'assistant',
        content: h.content,
        // 🟢 GUARANTEED: either came from backend or empty array (never undefined)
        companies: h.companies ?? h.metadata?.companies ?? [],
        createdAt: h.created_at ?? Date.now(),
      }));

      /** 3 ▶ if backend forgot companies for the LAST assistant message, patch from summary row */
      const lastAssistant = [...normalised].reverse().find(m => m.type === 'assistant');
      if (
        lastAssistant &&
        (lastAssistant.companies?.length ?? 0) === 0 &&
        item.aiResponse?.length
      ) {
        lastAssistant.companies = item.aiResponse;
      }

      /** 4 ▶ push to state */
      setThreadId(item.threadId);
      setAssistantId(item.assistantId);
      setMessages(normalised);
    } catch (err) {
      console.error('History load failed → fallback', err);
      setThreadId(item.threadId ?? null);
      setAssistantId(item.assistantId ?? null);

      // fallback: 2-message reconstruction
      setMessages([
        { id: generateId(), type: 'user', content: item.userPrompt },
        {
          id: generateId(),
          type: 'assistant',
          content: t('finder.response', { count: item.aiResponse.length }),
          companies: item.aiResponse,
        },
      ]);
      toast.error(t('finder.historyLoadError'), { duration: 2000 });
    } finally {
      setIsLoading(false);
      if (!keepSidebarOpen) setSidebarOpen(false);
    }
  };

  const handleDeleteHistory = async (id: string) => {
    try {
      const deletedItem = globalHistory.find(h => h.id === id);
      await historyApi.deleteHistory(id);
      dispatch({ type: 'DELETE_HISTORY', payload: id });

      // If current chat removed, reset
      if (deletedItem && deletedItem.threadId === threadId) {
        startNewChat();
      }

      toast.success(t('finder.historyDeleted'), { duration: 2000 });
    } catch (error) {
      console.error('Failed to delete history:', error);
      toast.error(t('finder.historyDeleteError'), { duration: 2000 });
    }
  };

  const startNewChat = () => {
    setMessages([]);
    setAssistantId(null);
    setThreadId(null);
    sessionStorage.removeItem('activeAssistantId');
    sessionStorage.removeItem('activeThreadId');
    if (!sidebarOpen) inputRef.current?.focus();
    setSidebarOpen(false);
  };

  /* --------------------------- Auth fallback --------------------------- */
  if (!user) {
    return (
      <div className="container mx-auto px-4 py-8">
        <div className="flex items-center justify-center min-h-[60vh]">
          <div className="text-center">
            <User className="h-16 w-16 text-muted-foreground mx-auto mb-4" />
            <h2 className="text-2xl font-bold mb-2">{t('finder.notLoggedIn.title')}</h2>
            <p className="text-muted-foreground mb-6">{t('finder.notLoggedIn.description')}</p>
            <Button onClick={() => navigate('/login')}>{t('finder.notLoggedIn.login')}</Button>
          </div>
        </div>
      </div>
    );
  }

  /* =============================== JSX =============================== */
  return (
    <div className="flex h-screen bg-background">
      {/* Sidebar */}
      <div
        className={`fixed inset-y-0 left-0 z-50 w-80 bg-background border-r transform transition-transform duration-300 ease-in-out ${
          sidebarOpen ? 'translate-x-0' : '-translate-x-full'
        }`}
      >
        <div className="flex flex-col h-full">
          <div className="flex items-center justify-between p-4 border-b">
            <h2 className="font-semibold">{t('finder.title')}</h2>
            <div className="flex items-center space-x-2">
              <Button variant="ghost" size="sm" onClick={startNewChat} className="text-xs">
                {t('finder.newChat')}
              </Button>
              <Button variant="ghost" size="icon" onClick={() => setSidebarOpen(false)}>
                <X className="h-4 w-4" />
              </Button>
            </div>
          </div>
          <div className="flex-1 overflow-y-auto">
            <ChatHistory history={globalHistory} onSelectHistory={handleSelectHistory} onDeleteHistory={handleDeleteHistory} />
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div className="flex-1 flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b bg-background/95 backdrop-blur relative">
          <div className="flex items-center space-x-3">
            <Button variant="ghost" size="icon" onClick={() => setSidebarOpen(true)}>
              <Menu className="h-4 w-4" />
            </Button>
            <Link to="/finder">
              <Button variant="ghost" size="sm" className="flex items-center space-x-2">
                <MessageSquare className="h-5 w-5 text-primary" />
                <span>{t('finder.title')}</span>
              </Button>
            </Link>
          </div>

          <div className="absolute left-1/2 -translate-x-1/2 flex items-center">
            <Link to="/" className="flex items-center space-x-2">
              <Heart className="h-6 w-6 text-primary" />
              <span className="text-xl font-bold">helpfund.pro</span>
            </Link>
          </div>

          <div className="flex items-center space-x-2">
            <Link to="/consideration">
              <Button variant="ghost" size="sm">
                {t('header.consideration')}
              </Button>
            </Link>
            <Link to="/profile">
              <Button variant="ghost" size="sm" className="flex items-center space-x-1">
                <User className="h-4 w-4" />
                <span>{t('header.profile')}</span>
              </Button>
            </Link>
          </div>
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto p-4">
          {messages.length === 0 ? (
            <div className="flex items-center justify-center h-full">
              <div className="text-center max-w-md">
                <MessageSquare className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
                <h3 className="text-lg font-semibold mb-2">{t('finder.welcome.title')}</h3>
                <p className="text-muted-foreground mb-4">{t('finder.welcome.description')}</p>
                <div className="text-sm text-muted-foreground space-y-1">
                  <p>
                    <strong>{t('finder.welcome.examples')}</strong>
                  </p>
                  <p>{t('finder.welcome.example1')}</p>
                  <p>{t('finder.welcome.example2')}</p>
                  <p>{t('finder.welcome.example3')}</p>
                </div>
              </div>
            </div>
          ) : (
            <div className="max-w-4xl mx-auto">
              {messages.map(message => (
                <ChatMessage key={message.id} {...message} />
              ))}
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        {/* Input */}
        <div className="border-t bg-background p-4">
          <div className="max-w-4xl mx-auto">
            <div className="flex space-x-2">
              <Input
                ref={inputRef}
                value={input}
                onChange={e => setInput(e.target.value)}
                onKeyPress={handleKeyPress}
                placeholder={t('finder.placeholder')}
                disabled={isLoading}
                className="flex-1"
              />
              <Button onClick={handleSendMessage} disabled={!input.trim() || isLoading} size="icon">
                <Send className="h-4 w-4" />
              </Button>
            </div>
            <p className="text-xs text-muted-foreground mt-2 text-center">{t('finder.sendHint')}</p>
          </div>
        </div>
      </div>

      {/* Overlay */}
      {sidebarOpen && <div className="fixed inset-0 bg-black/50 z-40" onClick={() => setSidebarOpen(false)} />} 
    </div>
  );
}