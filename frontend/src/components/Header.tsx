import { Search, Settings, User } from 'lucide-react';

interface HeaderProps {
  currentMode: 'knowledge' | 'analysis';
}

export function Header({ currentMode }: HeaderProps) {
  return (
    <header className="h-16 bg-white border-b border-slate-200 flex items-center justify-between px-8 flex-shrink-0">
      
      {/* Current Context / Breadcrumbs */}
      <div className="flex items-center space-x-2">
        <h2 className="text-lg font-bold text-slate-900 tracking-tight">The Digital Jurist</h2>
        <span className="text-slate-300 mx-2">|</span>
        <div className="flex space-x-6 text-sm font-medium">
          <span className={`${currentMode === 'knowledge' ? 'text-slate-800 border-b-2 border-slate-800 pb-5 pt-5 relative top-[1px]' : 'text-slate-400'}`}>
            Knowledge Mode
          </span>
          <span className={`${currentMode === 'analysis' ? 'text-slate-800 border-b-2 border-slate-800 pb-5 pt-5 relative top-[1px]' : 'text-slate-400'}`}>
            Analysis Mode
          </span>
        </div>
      </div>

      {/* Search and User Actions */}
      <div className="flex items-center space-x-6">
        <div className="relative w-72">
          <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
            <Search size={16} className="text-slate-400" />
          </div>
          <input
            type="text"
            className="block w-full pl-10 pr-3 py-2 border border-slate-200 rounded-full leading-5 bg-slate-50 placeholder-slate-400 focus:outline-none focus:ring-1 focus:ring-slate-500 focus:bg-white focus:border-slate-500 sm:text-sm transition-colors"
            placeholder={currentMode === 'knowledge' ? "Search precedents..." : "Search legal repository..."}
          />
        </div>

        <button className="text-slate-400 hover:text-slate-600 transition-colors">
          <Settings size={20} />
        </button>
        
        <div className="h-8 w-8 rounded-full bg-slate-800 flex items-center justify-center text-white overflow-hidden border border-slate-200 shadow-sm cursor-pointer">
          <User size={16} />
        </div>
      </div>
    </header>
  );
}
