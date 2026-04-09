import Link from 'next/link';
import { BookOpen, FileSearch, Plus, Settings, HelpCircle } from 'lucide-react';

interface SidebarProps {
  currentMode: 'knowledge' | 'analysis';
  setMode: (mode: 'knowledge' | 'analysis') => void;
  onNewCase: () => void;
}

export function Sidebar({ currentMode, setMode, onNewCase }: SidebarProps) {
  return (
    <aside className="w-64 bg-slate-50 border-r border-slate-200 flex flex-col h-full flex-shrink-0">
      {/* App Branding */}
      <div className="p-6">
        <h1 className="text-xl font-bold tracking-tight text-slate-900">The Digital Jurist</h1>
      </div>

      {/* Mode Switcher Label */}
      <div className="px-6 mb-2 mt-4">
        <p className="text-xs font-semibold tracking-widest text-slate-500 uppercase">
          AI Legal Suite
        </p>
      </div>

      {/* Navigation Modules */}
      <nav className="flex-1 px-4 space-y-2">
        <button
          onClick={() => setMode('knowledge')}
          className={`w-full flex items-center space-x-3 px-4 py-3 rounded-lg text-sm font-medium transition-colors ${
            currentMode === 'knowledge'
              ? 'bg-[#151238] text-white shadow-sm'
              : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900'
          }`}
        >
          <BookOpen size={18} className={currentMode === 'knowledge' ? 'text-white' : 'text-slate-400'} />
          <span className="tracking-wide">KNOWLEDGE MODE</span>
        </button>

        <button
          onClick={() => setMode('analysis')}
          className={`w-full flex items-center space-x-3 px-4 py-3 rounded-lg text-sm font-medium transition-colors ${
            currentMode === 'analysis'
              ? 'bg-[#151238] text-white shadow-sm'
              : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900'
          }`}
        >
          <FileSearch size={18} className={currentMode === 'analysis' ? 'text-white' : 'text-slate-400'} />
          <span className="tracking-wide">ANALYSIS MODE</span>
        </button>
      </nav>

      {/* Bottom Actions */}
      <div className="p-4 space-y-4">
        <button
          onClick={onNewCase}
          className="w-full flex items-center justify-center space-x-2 bg-[#151238] hover:bg-[#0c0a25] text-white px-4 py-2.5 rounded-md font-medium text-sm transition-colors shadow-sm"
        >
          <Plus size={16} />
          <span>New Case</span>
        </button>
        
        <div className="pt-4 border-t border-slate-200 flex flex-col space-y-1">
          <button className="flex items-center space-x-3 px-2 py-2 text-sm text-slate-600 hover:text-slate-900 transition-colors">
            <Settings size={18} className="text-slate-400" />
            <span className="font-medium tracking-wide">SETTINGS</span>
          </button>
          <button className="flex items-center space-x-3 px-2 py-2 text-sm text-slate-600 hover:text-slate-900 transition-colors">
            <HelpCircle size={18} className="text-slate-400" />
            <span className="font-medium tracking-wide">SUPPORT</span>
          </button>
        </div>
      </div>
    </aside>
  );
}
