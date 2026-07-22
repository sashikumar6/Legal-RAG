'use client';

import { useEffect, useRef, useState } from 'react';
import { Search, Settings, User as UserIcon } from 'lucide-react';
import { useAuth } from '@/lib/AuthContext';
import { LegalAI, HistoryResultItem } from '@/lib/api';
import type { ChatCitation } from '@/lib/api';
import type { ChatMessage } from '@/components/knowledge/ChatArea';

interface HeaderProps {
  currentMode: 'knowledge' | 'analysis';
  onModeChange: (mode: 'knowledge' | 'analysis') => void;
  onLoadConversation?: (conversationId: string, messages: ChatMessage[], citations?: ChatCitation[]) => void;
  onOpenSettings: () => void;
}

function useOutsideClick(onOutside: () => void) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) onOutside();
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [onOutside]);
  return ref;
}

export function Header({ currentMode, onModeChange, onLoadConversation, onOpenSettings }: HeaderProps) {
  const { user, loading, signInWithGoogle, signOut } = useAuth();

  const [accountOpen, setAccountOpen] = useState(false);
  const accountRef = useOutsideClick(() => setAccountOpen(false));

  const [query, setQuery] = useState('');
  const [results, setResults] = useState<HistoryResultItem[]>([]);
  const [searchOpen, setSearchOpen] = useState(false);
  const [searching, setSearching] = useState(false);
  const searchRef = useOutsideClick(() => setSearchOpen(false));

  useEffect(() => {
    if (!user || query.trim().length === 0) {
      setResults([]);
      return;
    }
    setSearching(true);
    const handle = setTimeout(async () => {
      try {
        const resp = await LegalAI.searchHistory(query.trim());
        setResults(resp.results);
      } catch {
        setResults([]);
      } finally {
        setSearching(false);
      }
    }, 350);
    return () => clearTimeout(handle);
  }, [query, user]);

  const handleSelectResult = async (conversationId: string) => {
    if (!onLoadConversation) return;
    try {
      const detail = await LegalAI.getConversation(conversationId);
      const messages: ChatMessage[] = detail.messages.map((m) => ({
        role: m.role as 'user' | 'assistant',
        content: m.content,
        timestamp: new Date(m.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      }));
      const citations = [...detail.messages]
        .reverse()
        .find((message) => message.role === 'assistant' && message.citations.length > 0)
        ?.citations || [];
      onLoadConversation(conversationId, messages, citations);
      setSearchOpen(false);
      setQuery('');
    } catch {
      // swallow — a failed load just leaves the current conversation as-is
    }
  };

  return (
    <header className="flex h-16 shrink-0 items-center justify-between border-b border-slate-200 bg-[#fafaf8] px-5 md:px-8">

      {/* Current Context / Breadcrumbs */}
      <div className="flex items-center space-x-2">
        <h2 className="font-serif text-xl font-semibold tracking-tight text-emerald-950">The Digital Jurist</h2>
        <span className="text-slate-300 mx-2">|</span>
        <div className="flex space-x-6 text-sm font-medium">
          <button onClick={() => onModeChange('knowledge')} className={`${currentMode === 'knowledge' ? 'border-b-2 border-emerald-950 pb-5 pt-5 text-emerald-950' : 'text-slate-400 hover:text-slate-700'}`}>
            Knowledge Mode
          </button>
          <button onClick={() => onModeChange('analysis')} className={`${currentMode === 'analysis' ? 'border-b-2 border-emerald-950 pb-5 pt-5 text-emerald-950' : 'text-slate-400 hover:text-slate-700'}`}>
            Analysis Mode
          </button>
        </div>
      </div>

      {/* Search and User Actions */}
      <div className="flex items-center space-x-6">
        <div className="relative w-72" ref={searchRef}>
          <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
            <Search size={16} className="text-slate-400" />
          </div>
          <input
            type="text"
            value={query}
            onChange={(e) => { setQuery(e.target.value); setSearchOpen(true); }}
            onFocus={() => setSearchOpen(true)}
            className="block w-full pl-10 pr-3 py-2 border border-slate-200 rounded-full leading-5 bg-slate-50 placeholder-slate-400 focus:outline-none focus:ring-1 focus:ring-slate-500 focus:bg-white focus:border-slate-500 sm:text-sm transition-colors"
            placeholder={user ? "Search your past conversations..." : "Sign in to search your history..."}
            disabled={!user}
          />

          {searchOpen && user && query.trim().length > 0 && (
            <div className="absolute top-full mt-2 w-full bg-white border border-slate-200 rounded-lg shadow-lg z-20 max-h-80 overflow-y-auto">
              {searching ? (
                <div className="px-4 py-3 text-sm text-slate-400">Searching...</div>
              ) : results.length === 0 ? (
                <div className="px-4 py-3 text-sm text-slate-400">No matching conversations</div>
              ) : (
                results.map((r) => (
                  <button
                    key={r.conversation_id}
                    onClick={() => handleSelectResult(r.conversation_id)}
                    className="w-full text-left px-4 py-2.5 text-sm text-slate-700 hover:bg-slate-50 border-b border-slate-100 last:border-b-0"
                  >
                    <div className="font-medium truncate">{r.title || 'Untitled conversation'}</div>
                    <div className="text-xs text-slate-400">{new Date(r.updated_at).toLocaleDateString()}</div>
                  </button>
                ))
              )}
            </div>
          )}
        </div>

        <button onClick={onOpenSettings} aria-label="Open research settings" className="text-slate-400 transition-colors hover:text-emerald-950">
          <Settings size={20} />
        </button>

        <div className="relative" ref={accountRef}>
          <button
            onClick={() => setAccountOpen((v) => !v)}
            className="h-8 w-8 rounded-full bg-slate-800 flex items-center justify-center text-white overflow-hidden border border-slate-200 shadow-sm cursor-pointer"
          >
            <UserIcon size={16} />
          </button>

          {accountOpen && (
            <div className="absolute right-0 top-full mt-2 w-56 bg-white border border-slate-200 rounded-lg shadow-lg z-20 p-2">
              {loading ? (
                <div className="px-3 py-2 text-sm text-slate-400">Loading...</div>
              ) : user ? (
                <>
                  <div className="px-3 py-2 text-sm text-slate-700 truncate">{user.email}</div>
                  <button
                    onClick={() => { signOut(); setAccountOpen(false); }}
                    className="w-full text-left px-3 py-2 text-sm text-slate-600 hover:bg-slate-50 rounded-md"
                  >
                    Sign out
                  </button>
                </>
              ) : (
                <button
                  onClick={() => { signInWithGoogle(); setAccountOpen(false); }}
                  className="w-full text-left px-3 py-2 text-sm text-slate-700 hover:bg-slate-50 rounded-md"
                >
                  Sign in with Google
                </button>
              )}
            </div>
          )}
        </div>
      </div>
    </header>
  );
}
