import { Clock, Scale, Shield, Landmark, FileText } from 'lucide-react';

export function WelcomeGrid({ onSelect }: { onSelect: (query: string) => void }) {
  const prompts = [
    {
      icon: <Clock size={20} className="text-slate-600 mb-3" />,
      text: "What are the rules regarding deportation and asylum under Title 8?",
    },
    {
      icon: <Scale size={20} className="text-slate-600 mb-3" />,
      text: "How does Chapter 11 bankruptcy protect corporate debtors under Title 11?",
    },
    {
      icon: <Shield size={20} className="text-slate-600 mb-3" />,
      text: "What are the federal penalties for wire fraud and embezzlement under Title 18?",
    },
    {
      icon: <FileText size={20} className="text-slate-600 mb-3" />,
      text: "Explain the overtime pay and minimum wage requirements under Title 29.",
    },
    {
      icon: <Landmark size={20} className="text-slate-600 mb-3" />,
      text: "What constitutes an antitrust violation or monopoly under Title 15?",
    },
    {
      icon: <FileText size={20} className="text-slate-600 mb-3" />,
      text: "How are individual tax deductions and exemptions calculated under Title 26?",
    }
  ];

  return (
    <div className="flex-1 overflow-y-auto px-12 pt-16 pb-8 bg-slate-50">
      <div className="max-w-4xl mx-auto space-y-12">
        <div>
          <h2 className="text-4xl font-bold tracking-tight text-slate-900 flexitems-center space-x-3 mb-2">
            <span className="w-1 h-8 bg-orange-600 inline-block rounded-full mr-2"></span>
            Knowledge Mode
          </h2>
          <p className="text-xl text-slate-600 font-medium">How can I assist your legal research today?</p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {prompts.map((p, i) => (
            <button
              key={i}
              onClick={() => onSelect(p.text)}
              className="flex flex-col text-left p-6 bg-white border border-slate-200 rounded-xl hover:shadow-md hover:border-slate-300 transition-all group"
            >
              {p.icon}
              <span className="font-medium text-sm text-slate-900 leading-snug group-hover:text-blue-700 transition-colors">
                {p.text}
              </span>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
