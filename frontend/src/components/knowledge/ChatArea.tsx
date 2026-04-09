import ReactMarkdown from 'react-markdown';

export interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
  timestamp: string;
}

export function ChatArea({ messages }: { messages: ChatMessage[] }) {
  return (
    <div className="flex-1 overflow-y-auto px-12 py-8 bg-slate-50 space-y-8">
      <div className="max-w-3xl mx-auto space-y-8 flex flex-col">
        {messages.map((m, i) => (
          <div
            key={i}
            className={`flex flex-col max-w-[85%] ${
              m.role === 'user' ? 'self-end' : 'self-start'
            }`}
          >
            {/* Message Header */}
            <div className={`mb-1 text-xs font-semibold tracking-widest text-slate-400 uppercase ${m.role === 'user' ? 'text-right' : 'text-left'}`}>
              {m.role === 'user' ? 'COUNSEL' : 'THE DIGITAL JURIST'} • {m.timestamp}
            </div>
            
            {/* Message Body */}
            <div
              className={`p-6 rounded-2xl ${
                m.role === 'user'
                  ? 'bg-white text-slate-900 shadow-sm border border-slate-100'
                  : 'bg-white text-slate-800 shadow-sm border border-slate-200 border-l-[6px] border-l-[#151238]'
              }`}
            >
              <div className="prose prose-slate prose-sm max-w-none">
                <ReactMarkdown>{m.content}</ReactMarkdown>
              </div>
            </div>
          </div>
        ))}
        {/* Invisible div for auto-scrolling can go here */}
      </div>
    </div>
  );
}
