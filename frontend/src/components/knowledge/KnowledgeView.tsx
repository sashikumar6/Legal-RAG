import { useEffect, useRef, useState } from 'react';
import { WelcomeGrid } from './WelcomeGrid';
import { ChatArea, ChatMessage } from './ChatArea';
import { InputBox } from './InputBox';
import { LegalAI, ChatCitation } from '@/lib/api';

const ACTIVE_CONVERSATION_KEY = 'dj_active_conversation_id';
const ACTIVE_MESSAGES_KEY = 'dj_active_messages';

interface ViewProps {
  onCitationsUpdate: (c: ChatCitation[]) => void;
  initialConversationId?: string | null;
  initialMessages?: ChatMessage[];
}

export function KnowledgeView({ onCitationsUpdate, initialConversationId, initialMessages }: ViewProps) {
  // Starts empty on both server and client's first render — reading localStorage
  // during the initial render would mismatch Next.js's SSR output and break
  // hydration, since the server never has access to it. Cached history is
  // loaded in the effect below instead, which only ever runs client-side.
  const [messages, setMessages] = useState<ChatMessage[]>(initialMessages ?? []);
  const [isThinking, setIsThinking] = useState(false);
  const conversationIdRef = useRef<string | null>(initialConversationId ?? null);
  const skipNextPersist = useRef(true);

  useEffect(() => {
    if (initialMessages || initialConversationId) return;
    try {
      const cachedMessages = localStorage.getItem(ACTIVE_MESSAGES_KEY);
      const cachedConversationId = localStorage.getItem(ACTIVE_CONVERSATION_KEY);
      if (cachedMessages) setMessages(JSON.parse(cachedMessages));
      if (cachedConversationId) conversationIdRef.current = cachedConversationId;
    } catch {
      // ignore malformed cache
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    // Skip the mount-time run: `messages` here is still the pre-hydration
    // value, and writing it would clobber the cache before the effect above
    // gets a chance to read it (both run in the same initial commit).
    if (skipNextPersist.current) {
      skipNextPersist.current = false;
      return;
    }
    localStorage.setItem(ACTIVE_MESSAGES_KEY, JSON.stringify(messages));
  }, [messages]);

  const handleSend = async (text: string) => {
    const userMsg: ChatMessage = { role: 'user', content: text, timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) };
    setMessages(prev => [...prev, userMsg]);
    setIsThinking(true);
    onCitationsUpdate([]);

    try {
      const resp = await LegalAI.chat(text, 'federal', undefined, conversationIdRef.current);

      if (resp.conversation_id) {
        conversationIdRef.current = resp.conversation_id;
        localStorage.setItem(ACTIVE_CONVERSATION_KEY, resp.conversation_id);
      }

      const aiMsg: ChatMessage = {
        role: 'assistant',
        content: resp.answer || "I could not find an answer in the federal corpus.",
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
      };

      setMessages(prev => [...prev, aiMsg]);

      if (resp.citations) {
        onCitationsUpdate(resp.citations);
      }
    } catch (e: any) {
      setMessages(prev => [...prev, { role: 'assistant', content: `**Error:** An exception occurred contacting the backend.\n\`\`\`text\n${e.message}\n\`\`\``, timestamp: new Date().toLocaleTimeString() }]);
    } finally {
      setIsThinking(false);
    }
  };

  return (
    <div className="flex-1 flex flex-col bg-white overflow-hidden relative">
      {messages.length === 0 ? (
        <WelcomeGrid onSelect={handleSend} />
      ) : (
        <ChatArea messages={messages} />
      )}
      
      {isThinking && (
        <div className="absolute bottom-28 right-1/2 translate-x-1/2 bg-white px-4 py-2 shadow-lg rounded-full border border-slate-200 flex items-center space-x-2 z-10 animate-fade-in">
          <span className="w-2 h-2 rounded-full bg-slate-900 animate-bounce"></span>
          <span className="w-2 h-2 rounded-full bg-slate-700 animate-bounce" style={{ animationDelay: '0.1s' }}></span>
          <span className="w-2 h-2 rounded-full bg-slate-500 animate-bounce" style={{ animationDelay: '0.2s' }}></span>
          <span className="text-xs font-semibold text-slate-800 tracking-wider uppercase ml-1">Analyzing...</span>
        </div>
      )}
      
      <InputBox onSend={handleSend} disabled={isThinking} />
    </div>
  );
}
