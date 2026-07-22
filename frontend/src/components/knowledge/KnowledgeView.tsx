import { useEffect, useRef, useState } from 'react';
import { WelcomeGrid } from './WelcomeGrid';
import { ChatArea, ChatMessage } from './ChatArea';
import { InputBox } from './InputBox';
import { LegalAI, ChatCitation, ResearchStatus } from '@/lib/api';
import type { ConversationSnapshot } from '@/lib/history';

const ACTIVE_CONVERSATION_KEY = 'dj_active_conversation_id';
const ACTIVE_MESSAGES_KEY = 'dj_active_messages';

interface ViewProps {
  onCitationsUpdate: (c: ChatCitation[]) => void;
  onConversationUpdated: (conversation: ConversationSnapshot) => void;
  initialConversationId?: string | null;
  initialMessages?: ChatMessage[];
}

function createLocalConversationId(): string {
  return `local-${crypto.randomUUID()}`;
}

export function KnowledgeView({
  onCitationsUpdate,
  onConversationUpdated,
  initialConversationId,
  initialMessages,
}: ViewProps) {
  const [messages, setMessages] = useState<ChatMessage[]>(initialMessages ?? []);
  const [isThinking, setIsThinking] = useState(false);
  const [researchSteps, setResearchSteps] = useState<ResearchStatus[]>([]);
  const messagesRef = useRef<ChatMessage[]>(initialMessages ?? []);
  const conversationIdRef = useRef<string | null>(
    initialConversationId?.startsWith('local-') ? null : initialConversationId ?? null,
  );
  const localConversationIdRef = useRef<string | null>(
    initialConversationId?.startsWith('local-') ? initialConversationId : null,
  );
  const skipNextPersist = useRef(true);

  useEffect(() => {
    if (initialMessages || initialConversationId) return;
    try {
      const cachedMessages = localStorage.getItem(ACTIVE_MESSAGES_KEY);
      const cachedConversationId = localStorage.getItem(ACTIVE_CONVERSATION_KEY);
      if (cachedMessages) {
        const parsedMessages = JSON.parse(cachedMessages);
        setMessages(parsedMessages);
        messagesRef.current = parsedMessages;
      }
      if (cachedConversationId) {
        if (cachedConversationId.startsWith('local-')) {
          localConversationIdRef.current = cachedConversationId;
        } else {
          conversationIdRef.current = cachedConversationId;
        }
      }
    } catch {
      // A corrupted local history must not block a new research session.
    }
  }, [initialConversationId, initialMessages]);

  useEffect(() => {
    if (skipNextPersist.current) {
      skipNextPersist.current = false;
      return;
    }
    localStorage.setItem(ACTIVE_MESSAGES_KEY, JSON.stringify(messages));
  }, [messages]);

  const handleSend = async (text: string) => {
    const timestamp = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    const userMessage: ChatMessage = { role: 'user', content: text, timestamp };
    const assistantMessage: ChatMessage = { role: 'assistant', content: '', timestamp, isStreaming: true };

    const pendingMessages = [...messagesRef.current, userMessage, assistantMessage];
    messagesRef.current = pendingMessages;
    setMessages(pendingMessages);
    setIsThinking(true);
    setResearchSteps([]);
    onCitationsUpdate([]);

    try {
      const response = await LegalAI.chatStream(text, 'auto', undefined, conversationIdRef.current, {
        onStatus: (status) => {
          setResearchSteps((previous) => {
            const last = previous[previous.length - 1];
            return last?.stage === status.stage ? [...previous.slice(0, -1), status] : [...previous, status];
          });
        },
        onToken: (token) => {
          setMessages((previous) => {
            const next = previous.map((message, index) => (
            index === previous.length - 1
              ? { ...message, content: message.content + token, isStreaming: true }
              : message
            ));
            messagesRef.current = next;
            return next;
          });
        },
      });

      let historyId = localConversationIdRef.current;
      if (response.conversation_id) {
        conversationIdRef.current = response.conversation_id;
        localConversationIdRef.current = null;
        historyId = response.conversation_id;
        localStorage.setItem(ACTIVE_CONVERSATION_KEY, response.conversation_id);
      } else {
        historyId = historyId || createLocalConversationId();
        localConversationIdRef.current = historyId;
        localStorage.setItem(ACTIVE_CONVERSATION_KEY, historyId);
      }

      const finalAnswer = response.clarification_needed
        ? response.clarification_question || 'Please provide more detail so I can research this accurately.'
        : response.answer || 'I could not find an answer in the available legal sources.';
      const completedMessages = messagesRef.current.map((message, index) => (
        index === messagesRef.current.length - 1
          ? {
              ...message,
              content: finalAnswer,
              isStreaming: false,
            }
          : message
      ));
      messagesRef.current = completedMessages;
      setMessages(completedMessages);
      onCitationsUpdate(response.citations || []);
      onConversationUpdated({
        conversation_id: historyId || createLocalConversationId(),
        title: completedMessages.find((message) => message.role === 'user')?.content.slice(0, 500) || 'Untitled case',
        mode: response.mode,
        updated_at: new Date().toISOString(),
        messages: completedMessages,
        citations: response.citations || [],
      });
    } catch (error: unknown) {
      const detail = error instanceof Error ? error.message : 'Unknown network error';
      const interruptedMessages = messagesRef.current.map((message, index) => (
        index === messagesRef.current.length - 1
          ? { ...message, content: `**Research interrupted.** ${detail}`, isStreaming: false }
          : message
      ));
      messagesRef.current = interruptedMessages;
      setMessages(interruptedMessages);

      const historyId = conversationIdRef.current
        || localConversationIdRef.current
        || createLocalConversationId();
      if (!conversationIdRef.current) localConversationIdRef.current = historyId;
      localStorage.setItem(ACTIVE_CONVERSATION_KEY, historyId);
      onConversationUpdated({
        conversation_id: historyId,
        title: interruptedMessages.find((message) => message.role === 'user')?.content.slice(0, 500) || 'Untitled case',
        mode: 'auto',
        updated_at: new Date().toISOString(),
        messages: interruptedMessages,
        citations: [],
      });
    } finally {
      setIsThinking(false);
    }
  };

  return (
    <section className="relative flex flex-1 flex-col overflow-hidden bg-[#fafaf8]">
      {messages.length === 0 ? (
        <WelcomeGrid onSelect={handleSend} />
      ) : (
        <ChatArea messages={messages} researchSteps={researchSteps} isResearching={isThinking} />
      )}
      <InputBox onSend={handleSend} disabled={isThinking} />
    </section>
  );
}
