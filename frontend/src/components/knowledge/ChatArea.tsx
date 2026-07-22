import { useEffect, useRef } from 'react';
import ReactMarkdown from 'react-markdown';
import type { ResearchStatus } from '@/lib/api';
import { ResearchTrace } from './ResearchTrace';

export interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
  timestamp: string;
  isStreaming?: boolean;
}

interface ChatAreaProps {
  messages: ChatMessage[];
  researchSteps?: ResearchStatus[];
  isResearching?: boolean;
}

const LEGACY_UNVERIFIED_NOTICE = '⚠️ **Unverified — general knowledge, not sourced from the indexed corpus.** Independently confirm any citation before relying on it.';
const KNOWLEDGE_BASE_NOTICE = '*The Digital Jurist did not retrieve supporting material from its knowledge base for this question, so the response below provides general legal information.*';

function displayContent(content: string): string {
  return content.replace(LEGACY_UNVERIFIED_NOTICE, KNOWLEDGE_BASE_NOTICE);
}

export function ChatArea({ messages, researchSteps = [], isResearching = false }: ChatAreaProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' });
  }, [messages, researchSteps]);

  return (
    <div className="flex-1 overflow-y-auto bg-[#fafaf8] px-5 py-8 md:px-12 lg:px-16">
      <div className="mx-auto max-w-3xl space-y-10">
        <div className="text-center">
          <span className="border-y border-slate-300/70 px-4 py-1 text-[10px] font-semibold uppercase tracking-[0.2em] text-slate-400">
            Research session
          </span>
        </div>

        {messages.map((message, index) => (
          <article key={`${message.role}-${index}`} className="group">
            <div className={`mb-3 flex items-center gap-3 ${message.role === 'user' ? 'text-slate-500' : 'text-emerald-950'}`}>
              <span className="text-[11px] font-semibold uppercase tracking-[0.18em]">
                {message.role === 'user' ? 'Counsel' : 'Digital Jurist'}
              </span>
              <span className={`h-px flex-1 ${message.role === 'user' ? 'bg-slate-200' : 'bg-emerald-950/15'}`} />
              <span className="text-[11px] text-slate-400">{message.timestamp}</span>
            </div>

            <div className={message.role === 'assistant' ? 'border-l-2 border-emerald-950/30 pl-6' : 'pl-6'}>
              {message.isStreaming && !message.content ? (
                <div className="flex items-center gap-2 py-2 text-sm text-slate-500">
                  <span className="h-2 w-2 animate-pulse rounded-full bg-emerald-800" />
                  Awaiting the first verified draft token…
                </div>
              ) : (
                <div className="prose prose-slate max-w-none font-serif text-[17px] leading-8 prose-headings:font-serif prose-headings:text-emerald-950 prose-a:text-emerald-800">
                  <ReactMarkdown>{displayContent(message.content)}</ReactMarkdown>
                  {message.isStreaming && <span className="ml-1 inline-block h-5 w-1.5 animate-pulse bg-emerald-900 align-[-3px]" aria-label="Generating" />}
                </div>
              )}
            </div>

            {message.isStreaming && (
              <ResearchTrace steps={researchSteps} isResearching={isResearching} />
            )}
          </article>
        ))}
        <div ref={bottomRef} />
      </div>
    </div>
  );
}
