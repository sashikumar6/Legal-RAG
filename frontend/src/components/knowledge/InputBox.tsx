import { ArrowUp } from 'lucide-react';
import { useState } from 'react';

export function InputBox({ onSend, disabled }: { onSend: (text: string) => void; disabled?: boolean }) {
  const [input, setInput] = useState('');

  const handleSend = () => {
    const query = input.trim();
    if (!query || disabled) return;
    onSend(query);
    setInput('');
  };

  return (
    <div className="border-t border-slate-200/90 bg-[#fafaf8] px-5 pb-7 pt-4 md:px-12 lg:px-16">
      <div className="mx-auto max-w-3xl">
        <div className="flex items-center gap-3 rounded-md border border-slate-300 bg-white px-4 py-2 shadow-sm transition focus-within:border-emerald-950 focus-within:ring-1 focus-within:ring-emerald-950/20">
          <span className="hidden text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-400 sm:block">Research</span>
          <input
            type="text"
            value={input}
            onChange={(event) => setInput(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === 'Enter' && !event.shiftKey) {
                event.preventDefault();
                handleSend();
              }
            }}
            disabled={disabled}
            placeholder={disabled ? 'Research in progress…' : 'Ask about a statute, regulation, or precedent…'}
            className="min-w-0 flex-1 bg-transparent py-2 text-[15px] text-slate-900 outline-none placeholder:text-slate-400 disabled:cursor-not-allowed"
            aria-label="Legal research query"
          />
          <button
            onClick={handleSend}
            className="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-sm bg-emerald-950 text-white transition hover:bg-emerald-900 disabled:cursor-not-allowed disabled:bg-slate-300"
            disabled={disabled || !input.trim()}
            aria-label="Start research"
          >
            <ArrowUp size={17} />
          </button>
        </div>
        <p className="mt-3 text-center text-[11px] text-slate-500">
          The Digital Jurist provides legal research information, not legal advice.
        </p>
      </div>
    </div>
  );
}
