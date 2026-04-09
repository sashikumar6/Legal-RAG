import { Paperclip, ArrowRight } from 'lucide-react';
import { useState } from 'react';

export function InputBox({ onSend, disabled }: { onSend: (text: string) => void, disabled?: boolean }) {
  const [input, setInput] = useState('');

  const handleSend = () => {
    if (!input.trim()) return;
    onSend(input);
    setInput('');
  };

  return (
    <div className="bg-white border-t border-slate-200 px-12 py-6 flex-shrink-0">
      <div className="max-w-4xl mx-auto flex items-center bg-white border border-slate-300 rounded-lg shadow-sm focus-within:ring-2 focus-within:ring-slate-800 transition-all">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') handleSend();
          }}
          disabled={disabled}
          placeholder="Enter your query or cite a case..."
          className="flex-1 py-4 px-2 outline-none text-slate-900 placeholder-slate-400 font-medium disabled:opacity-50 disabled:bg-transparent"
        />
        <div className="px-4">
          <button
            onClick={handleSend}
            className="flex items-center space-x-2 bg-[#151238] hover:bg-slate-900 text-white px-4 py-2 rounded-md font-medium text-sm transition-colors shadow-sm disabled:opacity-50 disabled:cursor-not-allowed"
            disabled={disabled || !input.trim()}
          >
            <span>Research</span>
            <ArrowRight size={16} />
          </button>
        </div>
      </div>
      <div className="text-center mt-4 text-xs text-slate-500 font-medium">
        The Digital Jurist AI. For informational purposes only. Consult legal counsel for professional advice.
      </div>
    </div>
  );
}
