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
import { ChatHistoryItem, Company, ChatRequest } from '@/types';
import { generateId } from '@/lib/utils';
import { toast } from 'sonner';

interface Message {
  id: string;
  type: 'user' | 'assistant' | 'loading';
  content?: string;
  companies?: Company[];
  createdAt?: number | string;
}

// Helper: List of 'more' keywords in multiple languages
const MORE_KEYWORDS = [
  'more', 'show more', 'next', 'additional', 'another',
  'ещё', 'еще', 'далее', 'следующие', 'ещё компании', 'ещё фирм', 'больше', 'продолжить', 'продолжи',
  'ещё', 'ещё раз', 'ещё результатов', 'ещё фирм', 'ещё организаций', 'ещё предприятий',
  // Add more as needed
];

function isMoreCommand(input: string) {
  const normalized = input.trim().toLowerCase();
  return MORE_KEYWORDS.some(keyword => normalized === keyword || normalized.startsWith(keyword + ' '));
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

  // 💡 НОВАЯ ЛОГИКА: Используем chat_id для персистентности
  const [chatId, setChatId] = useState<string | null>(() => sessionStorage.getItem('activeChatId'));
  // Оставляем для совместимости с существующими чатами
  const [assistantId, setAssistantId] = useState<string | null>(() => sessionStorage.getItem('activeAssistantId'));
  const [threadId, setThreadId] = useState<string | null>(() => sessionStorage.getItem('activeThreadId'));

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  /* ------------------------------------------------------------------
   * Persist chat_id in sessionStorage when it changes
   * ------------------------------------------------------------------ */
  useEffect(() => {
    if (chatId) {
      sessionStorage.setItem('activeChatId', chatId);
    } else {
      sessionStorage.removeItem('activeChatId');
    }
  }, [chatId]);

  // Оставляем для совместимости
  useEffect(() => {
    if (assistantId) {
      sessionStorage.setItem('activeAssistantId', assistantId);
    } else {
      sessionStorage.removeItem('activeAssistantId');
    }
  }, [assistantId]);

  useEffect(() => {
    if (threadId) {
      sessionStorage.setItem('activeThreadId', threadId);
    } else {
      sessionStorage.removeItem('activeThreadId');
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
  useEffect(() => {
    const loadInitialData = async () => {
      try {
        // 1. Загружаем список всех чатов для боковой панели
        console.log('FinderPage: Calling historyApi.getHistory()');
        const historyList = await historyApi.getHistory();
        console.log('FinderPage: Received history list:', historyList);
        dispatch({ type: 'LOAD_HISTORY', payload: historyList });

        // 2. Проверяем, есть ли активный чат в sessionStorage
        const activeChatId = sessionStorage.getItem('activeChatId');
        if (!activeChatId) {
          return; // Нет активного чата, выходим
        }

        // 3. Ищем чат в загруженной истории
        let activeHistoryItem = historyList.find(h => h.id === activeChatId);

        if (activeHistoryItem) {
          // Загружаем найденный чат
          await handleSelectHistory(activeHistoryItem, true);
        } else {
          // Чат не найден в истории, возможно он был удален
          console.warn(`Chat ${activeChatId} not found in history. Starting new chat.`);
          startNewChat();
        }
      } catch (error) {
        console.error('FinderPage: Failed to load initial history:', error);
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

    const isMore = isMoreCommand(input);
    if (isMore) {
      // Find last user search prompt (not a 'more' command)
      const hasSearchPrompt = messages.some(
        m => m.type === 'user' && !isMoreCommand(m.content || '')
      );
      if (!hasSearchPrompt) {
        toast.error('Please start a new search before requesting more results.');
        return;
      }
    }

    const userMessage: Message = { id: generateId(), type: 'user', content: input.trim() };
    const loadingMessage: Message = { id: generateId(), type: 'loading' };

    setMessages(prev => [...prev, userMessage, loadingMessage]);

    const currentInput = input.trim();
    setInput('');
    setIsLoading(true);

    try {
      // 💡 НОВАЯ ЛОГИКА: Упрощенный запрос без history
      const requestPayload: ChatRequest = {
        user_input: currentInput,
        chat_id: chatId || undefined, // Используем chat_id
      };

      console.log('[handleSendMessage] SENDING:', requestPayload);

      const response = await chatApi.sendMessage(requestPayload);
      console.log('[handleSendMessage] RECEIVED:', response);

      // 💡 ОБНОВЛЯЕМ СОСТОЯНИЕ: Приоритет chat_id
      if (response.chat_id) {
        setChatId(response.chat_id);
      }
      // Оставляем для совместимости
      if (response.assistant_id) setAssistantId(response.assistant_id);
      if (response.thread_id) setThreadId(response.thread_id);

      // Обновляем сообщения
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
      const effectiveChatId = response.chat_id || chatId;
      if (effectiveChatId) {
        const existingChat = globalHistory.find(h => h.id === effectiveChatId);

        // Создаем или обновляем элемент истории
        const updatedHistoryItem: ChatHistoryItem = {
          id: effectiveChatId,
          userPrompt: currentInput,
          aiResponse: response.companies || [],
          created_at: new Date().toISOString(),
          threadId: response.thread_id || threadId || '',
          assistantId: response.assistant_id || assistantId || '',
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
      console.error('[handleSendMessage] Failed to send message:', error);
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
    console.log('[handleSelectHistory] Called with item:', item);
    // fast-return if already selected
    if (item.id === chatId && messages.length) {
      if (!keepSidebarOpen) setSidebarOpen(false);
      return;
    }

    // optimistic UI while fetching
    setIsLoading(true);
    setMessages([]);

    try {
      // 💡 НОВАЯ ЛОГИКА: Загружаем историю по chat_id через новый API
      console.log('[handleSelectHistory] Fetching conversation history for chatId:', item.id);
      const history = await chatApi.getConversationHistory(item.id);
      console.log('[handleSelectHistory] Received conversation history:', history);

      const historyToSet: Message[] = history.map((h: any) => ({
        id: h.id ?? generateId(),
        type: h.role as 'user' | 'assistant',
        content: h.content,
        companies: h.companies ?? [],
        createdAt: h.created_at ?? Date.now(),
      }));

      // Если последнее сообщение ассистента не имеет компаний, добавляем из aiResponse
      const lastAssistant = [...historyToSet].reverse().find(m => m.type === 'assistant');
      if (
        lastAssistant &&
        (lastAssistant.companies?.length ?? 0) === 0 &&
        item.aiResponse?.length
      ) {
        lastAssistant.companies = item.aiResponse;
      }

      // Устанавливаем состояние
      setChatId(item.id);
      setThreadId(item.threadId || '');
      setAssistantId(item.assistantId || '');
      setMessages(historyToSet);
      console.log('[handleSelectHistory] Set messages:', historyToSet);

    } catch (err) {
      console.error('[handleSelectHistory] Failed to load conversation history:', err);
      // Fallback: отображаем базовую информацию из item
      const companiesForFallback = Array.isArray(item.aiResponse) ? item.aiResponse : [];
      setMessages([
        { id: generateId(), type: 'user', content: item.userPrompt },
        {
          id: generateId(),
          type: 'assistant',
          content: t('finder.response', { count: companiesForFallback.length }),
          companies: companiesForFallback,
        },
      ]);
      setChatId(item.id);
      setThreadId(item.threadId || '');
      setAssistantId(item.assistantId || '');
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
      if (deletedItem && deletedItem.id === chatId) {
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
    setChatId(null);
    setAssistantId(null);
    setThreadId(null);
    sessionStorage.removeItem('activeChatId');
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