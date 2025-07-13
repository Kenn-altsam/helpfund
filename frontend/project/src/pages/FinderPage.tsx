import React, { useState, useRef, useEffect } from 'react';
import { Send, Menu, X, MessageSquare, User} from 'lucide-react';
import { Link } from 'react-router-dom';
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
import ErrorBoundary from '@/components/ErrorBoundary';

interface Message {
  id: string;
  type: 'user' | 'assistant' | 'loading';
  content?: string;
  companies?: Company[];
  createdAt?: number | string;
}

export function FinderPage() {
  const { t } = useTranslation();
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
        console.log('FinderPage: Calling historyApi.getHistory()'); // DEBUG
        const historyList = await historyApi.getHistory();
        console.log('FinderPage: Received history list:', historyList); // DEBUG
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
        console.error('FinderPage: Failed to load initial history:', error); // DEBUG
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

  // When a history item is selected from the sidebar
  const handleSelectHistory = async (
    item: ChatHistoryItem,
    keepSidebarOpen = false,
  ) => {
    console.log('handleSelectHistory called with item:', item); // DEBUG
    if (!item.assistantId || !item.threadId) {
      toast.error('This chat is missing key information and cannot be loaded.');
      return;
    }

    setSidebarOpen(keepSidebarOpen);
    setIsLoading(true);
    setMessages([{ id: generateId(), type: 'loading' }]); // Show loading state

    try {
      // Set the active IDs for the selected chat
      setAssistantId(item.assistantId);
      setThreadId(item.threadId);
      console.log(`Set active IDs: asst=${item.assistantId}, thread=${item.threadId}`); // DEBUG

      const conversationHistory = await chatApi.getConversationHistory(
        item.assistantId,
        item.threadId,
      );
      console.log('Received conversation history:', conversationHistory); // DEBUG

      // Transform the raw history into the Message format for the UI
      const formattedMessages = conversationHistory
        .map(
          (msg: any): Message | null => {
            // Skip system messages or messages without content
            if (msg.role === 'system' || !msg.content) return null;

            return {
              id: msg.id || generateId(), // Fallback to generateId if needed
              type: msg.role as 'user' | 'assistant',
              content: msg.content,
              companies: msg.companies || [], // Ensure companies are carried over
              createdAt: msg.createdAt,
            };
          },
        )
        .filter((msg): msg is Message => msg !== null); // Filter out any null entries

      setMessages(formattedMessages);

      if (formattedMessages.length > 0) {
        toast.success(t('finder.chatRestored'));
      } else {
        // Handle case where history is empty (e.g., new chat just created but no messages yet)
        setMessages([]); // Clear any loading/stale messages
        toast.info(t('finder.emptyChat'));
      }
    } catch (error) {
      console.error('Failed to load chat history:', error);
      toast.error(t('finder.restoreError'));
      // In case of error, maybe revert to a clean state
      setMessages([]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleDeleteHistory = async (id: string) => {
    toast.info(t('finder.deletingChat'));
    try {
      await historyApi.deleteHistory(id);
      dispatch({ type: 'DELETE_HISTORY', payload: id });

      // If the deleted chat was the active one, start a new chat
      const activeThreadId = sessionStorage.getItem('activeThreadId');
      const deletedChat = globalHistory.find(h => h.id === id);
      if (deletedChat && deletedChat.threadId === activeThreadId) {
        startNewChat();
      }

      toast.success(t('finder.chatDeleted'));
    } catch (error) {
      console.error('Failed to delete history:', error);
      toast.error(t('finder.deleteError'));
    }
  };

  // Function to start a completely new chat session
  const startNewChat = () => {
    setMessages([]);
    setAssistantId(null);
    setThreadId(null);
    setInput('');
    // --- 💡 ИЗМЕНЕНИЕ: Также очищаем sessionStorage ---
    sessionStorage.removeItem('activeAssistantId');
    sessionStorage.removeItem('activeThreadId');
    toast.success(t('finder.newChatStarted'));
    inputRef.current?.focus();
  };

  return (
    <ErrorBoundary>
      <div className="flex h-screen bg-gray-50 dark:bg-gray-900">
        {/* Mobile Sidebar Toggle */}
        <div className="absolute top-4 left-4 z-20 md:hidden">
          <Button variant="ghost" size="icon" onClick={() => setSidebarOpen(true)}>
            <Menu className="h-5 w-5" />
          </Button>
        </div>

        {/* Desktop Sidebar */}
        <div
          className={`fixed inset-y-0 left-0 z-30 w-80 bg-white dark:bg-gray-800 border-r dark:border-gray-700 transform transition-transform duration-300 ease-in-out md:relative md:translate-x-0 ${
            sidebarOpen ? 'translate-x-0' : '-translate-x-full'
          }`}
        >
          <div className="flex flex-col h-full">
            <div className="flex items-center justify-between p-4 border-b dark:border-gray-700">
              <h2 className="text-xl font-semibold text-gray-800 dark:text-gray-200">
                {t('finder.history')}
              </h2>
              <div className="flex items-center">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={startNewChat}
                  className="mr-2"
                >
                  {t('finder.newChat')}
                </Button>
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={() => setSidebarOpen(false)}
                  className="md:hidden"
                >
                  <X className="h-5 w-5" />
                </Button>
              </div>
            </div>
            <div className="flex-1 overflow-y-auto">
              <ChatHistory
                history={globalHistory}
                onSelectHistory={handleSelectHistory}
                onDeleteHistory={handleDeleteHistory}
              />
            </div>
          </div>
        </div>

        {/* Main Content */}
        <main className="flex-1 flex flex-col h-screen">
          <header className="flex items-center justify-between p-4 border-b bg-white dark:bg-gray-800 dark:border-gray-700">
            <div className="flex items-center space-x-2">
              <Link to="/finder">
                <Button variant="ghost" className="flex items-center space-x-2">
                  <MessageSquare className="h-6 w-6 text-blue-500" />
                  <span className="text-lg font-semibold text-gray-800 dark:text-gray-200">
                    {t('finder.title')}
                  </span>
                </Button>
              </Link>
            </div>
            <div className="flex items-center space-x-4">
              <Link to="/consideration">
                <Button variant="ghost">{t('header.consideration')}</Button>
              </Link>
              <Link to="/profile">
                <Button variant="ghost" className="flex items-center space-x-2">
                  <User className="h-5 w-5" />
                  <span>{t('header.profile')}</span>
                </Button>
              </Link>
            </div>
          </header>

          <div className="flex-1 overflow-y-auto p-6 space-y-4">
            {messages.length === 0 && !isLoading ? (
              <div className="flex flex-col items-center justify-center h-full text-center text-gray-500 dark:text-gray-400">
                <MessageSquare className="w-16 h-16 mb-4" />
                <h2 className="text-2xl font-semibold mb-2 text-gray-800 dark:text-gray-200">
                  {t('finder.welcome.title')}
                </h2>
                <p className="max-w-md">{t('finder.welcome.description')}</p>
              </div>
            ) : (
              messages.map(message => (
                <ChatMessage key={message.id} {...message} />
              ))
            )}
            <div ref={messagesEndRef} />
          </div>

          <div className="p-4 bg-white dark:bg-gray-800 border-t dark:border-gray-700">
            <div className="relative">
              <Input
                ref={inputRef}
                value={input}
                onChange={e => setInput(e.target.value)}
                onKeyPress={handleKeyPress}
                placeholder={t('finder.placeholder')}
                disabled={isLoading}
                className="pr-12"
              />
              <Button
                type="submit"
                size="icon"
                className="absolute right-2 top-1/2 -translate-y-1/2"
                onClick={handleSendMessage}
                disabled={isLoading || !input.trim()}
              >
                <Send className="w-5 h-5" />
              </Button>
            </div>
          </div>
        </main>
        {/* Overlay */}
        {sidebarOpen && (
          <div className="fixed inset-0 bg-black/50 z-40 md:hidden" onClick={() => setSidebarOpen(false)} />
        )}
      </div>
    </ErrorBoundary>
  );
}