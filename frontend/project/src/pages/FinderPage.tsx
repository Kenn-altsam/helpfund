import React, { useState, useRef, useEffect } from 'react';
import { Send, Menu, X, MessageSquare, User, Heart } from 'lucide-react';
import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
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
}

export function FinderPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { state, dispatch } = useGlobalContext();
  const { user } = state;
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [assistantId, setAssistantId] = useState<string | null>(null);
  const [threadId, setThreadId] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // If not logged in, show login prompt
  if (!user) {
    return (
      <div className="container mx-auto px-4 py-8">
        <div className="flex items-center justify-center min-h-[60vh]">
          <div className="text-center">
            <User className="h-16 w-16 text-muted-foreground mx-auto mb-4" />
            <h2 className="text-2xl font-bold mb-2">{t('finder.notLoggedIn.title')}</h2>
            <p className="text-muted-foreground mb-6">
              {t('finder.notLoggedIn.description')}
            </p>
            <Button onClick={() => navigate('/login')}>
              {t('finder.notLoggedIn.login')}
            </Button>
          </div>
        </div>
      </div>
    );
  }

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  useEffect(() => {
    // Load chat history on mount
    const loadHistory = async () => {
      try {
        const history = await historyApi.getHistory();
        dispatch({ type: 'LOAD_HISTORY', payload: history });
      } catch (error) {
        console.error('Failed to load history:', error);
      }
    };
    loadHistory();
  }, [dispatch]);

  const handleSendMessage = async () => {
    if (!input.trim() || isLoading) return;

    const userMessage: Message = {
      id: generateId(),
      type: 'user',
      content: input.trim(),
    };

    const loadingMessage: Message = {
      id: generateId(),
      type: 'loading',
    };

    setMessages(prev => [...prev, userMessage, loadingMessage]);
    setInput('');
    setIsLoading(true);

    try {
      const response = await chatApi.sendMessage({ 
        prompt: input.trim(),
        assistant_id: assistantId || undefined,
        thread_id: threadId || undefined
      });
      
      // Store the assistant and thread IDs if they're returned
      if (response.assistant_id) {
        setAssistantId(response.assistant_id);
      }
      if (response.thread_id) {
        setThreadId(response.thread_id);
      }

      // Remove loading message and add response
      setMessages(prev => {
        const withoutLoading = prev.filter(msg => msg.type !== 'loading');
        return [
          ...withoutLoading,
          {
            id: generateId(),
            type: 'assistant',
            content: response.message || t('finder.response', { count: response.companies?.length || 0 }),
            companies: response.companies || [],
          },
        ];
      });

      // Save to history
      const historyItem: ChatHistoryItem = {
        id: generateId(),
        userPrompt: input.trim(),
        aiResponse: response.companies || [],
        created_at: new Date().toISOString(),
      };

      await historyApi.saveHistory(historyItem);
      dispatch({ type: 'ADD_HISTORY', payload: historyItem });

      if (response.companies?.length) {
        toast.success(t('finder.companiesFound', { count: response.companies.length }), { duration: 3000 });
      }
    } catch (error) {
      console.error('Failed to send message:', error);
      setMessages(prev => prev.filter(msg => msg.type !== 'loading'));
      toast.error(t('finder.searchError'), { duration: 3000 });
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

  const handleSelectHistory = (item: ChatHistoryItem) => {
    const userMessage: Message = {
      id: generateId(),
      type: 'user',
      content: item.userPrompt,
    };

    const assistantMessage: Message = {
      id: generateId(),
      type: 'assistant',
      content: t('finder.response', { count: item.aiResponse.length }),
      companies: item.aiResponse,
    };

    setMessages([userMessage, assistantMessage]);
    setSidebarOpen(false);
  };

  const handleDeleteHistory = async (id: string) => {
    try {
      await historyApi.deleteHistory(id);
      dispatch({ type: 'DELETE_HISTORY', payload: id });
      toast.success(t('finder.historyDeleted'), { duration: 3000 });
    } catch (error) {
      console.error('Failed to delete history:', error);
      toast.error(t('finder.historyDeleteError'), { duration: 3000 });
    }
  };

  const startNewChat = async () => {
    try {
      await chatApi.resetChat();
      setMessages([]);
      setAssistantId(null);
      setThreadId(null);
      setSidebarOpen(false);
      inputRef.current?.focus();
    } catch (error) {
      console.error('Failed to reset chat:', error);
      toast.error(t('finder.resetError'), { duration: 3000 });
    }
  };

  return (
    <div className="flex h-screen bg-background">
      {/* Sidebar */}
      <div className={`fixed inset-y-0 left-0 z-50 w-80 bg-background border-r transform transition-transform duration-300 ease-in-out ${
        sidebarOpen ? 'translate-x-0' : '-translate-x-full'
      }`}>
        <div className="flex flex-col h-full">
          <div className="flex items-center justify-between p-4 border-b">
            <h2 className="font-semibold">{t('finder.title')}</h2>
            <div className="flex items-center space-x-2">
              <Button
                variant="ghost"
                size="sm" 
                onClick={startNewChat}
                className="text-xs"
              >
                {t('finder.newChat')}
              </Button>
              <Button
                variant="ghost"
                size="icon"
                onClick={() => setSidebarOpen(false)}
              >
                <X className="h-4 w-4" />
              </Button>
            </div>
          </div>
          
          <div className="flex-1 overflow-y-auto">
            <ChatHistory
              history={state.history}
              onSelectHistory={handleSelectHistory}
              onDeleteHistory={handleDeleteHistory}
            />
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div className="flex-1 flex flex-col lg:ml-0">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b bg-background/95 backdrop-blur relative">
          {/* Left section: burger & finder title */}
          <div className="flex items-center space-x-3">
            <Button
              variant="ghost"
              size="icon"
              onClick={() => setSidebarOpen(true)}
            >
              <Menu className="h-4 w-4" />
            </Button>

            <Link to="/finder">
              <Button variant="ghost" size="sm" className="flex items-center space-x-2">
                <MessageSquare className="h-5 w-5 text-primary" />
                {t('finder.title')}
              </Button>
            </Link>
          </div>

          {/* Center section: brand */}
          <div className="absolute left-1/2 -translate-x-1/2 flex items-center">
            <Link to="/" className="flex items-center space-x-2">
              <Heart className="h-6 w-6 text-primary" />
              <span className="text-xl font-bold">helpfund.pro</span>
            </Link>
          </div>

          {/* Right section: Consideration & Profile */}
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
                <p className="text-muted-foreground mb-4">
                  {t('finder.welcome.description')}
                </p>
                <div className="text-sm text-muted-foreground space-y-1">
                  <p><strong>{t('finder.welcome.examples')}</strong></p>
                  <p>{t('finder.welcome.example1')}</p>
                  <p>{t('finder.welcome.example2')}</p>
                  <p>{t('finder.welcome.example3')}</p>
                </div>
              </div>
            </div>
          ) : (
            <div className="max-w-4xl mx-auto">
              {messages.map((message) => (
                <ChatMessage
                  key={message.id}
                  type={message.type}
                  content={message.content}
                  companies={message.companies}
                />
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
                onChange={(e) => setInput(e.target.value)}
                onKeyPress={handleKeyPress}
                placeholder={t('finder.placeholder')}
                disabled={isLoading}
                className="flex-1"
              />
              <Button
                onClick={handleSendMessage}
                disabled={!input.trim() || isLoading}
                size="icon"
              >
                <Send className="h-4 w-4" />
              </Button>
            </div>
            <p className="text-xs text-muted-foreground mt-2 text-center">
              {t('finder.sendHint')}
            </p>
          </div>
        </div>
      </div>

      {/* Overlay */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 bg-black/50 z-40"
          onClick={() => setSidebarOpen(false)}
        />
      )}
    </div>
  );
}