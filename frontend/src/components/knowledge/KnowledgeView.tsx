import { useState } from 'react';
import { WelcomeGrid } from './WelcomeGrid';
import { ChatArea, ChatMessage } from './ChatArea';
import { InputBox } from './InputBox';
import { LegalAI, ChatCitation } from '@/lib/api';

interface ViewProps {
  onCitationsUpdate: (c: ChatCitation[]) => void;
}

export function KnowledgeView({ onCitationsUpdate }: ViewProps) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isThinking, setIsThinking] = useState(false);

  const handleSend = async (text: string) => {
    const userMsg: ChatMessage = { role: 'user', content: text, timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) };
    setMessages(prev => [...prev, userMsg]);
    setIsThinking(true);
    onCitationsUpdate([]);

    try {
      const resp = await LegalAI.chat(text, 'federal');
      
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
