import { CloudUpload, FileText, File, FileCode } from 'lucide-react';
import { useRef, useState } from 'react';

export function Dropzone({ onUpload }: { onUpload: (f: File) => void }) {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [isDragging, setIsDragging] = useState(false);

  const acceptFile = (file?: File) => {
    if (file) onUpload(file);
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      acceptFile(e.target.files[0]);
    }
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  return (
    <div
      onDragOver={(event) => { event.preventDefault(); setIsDragging(true); }}
      onDragLeave={() => setIsDragging(false)}
      onDrop={(event) => {
        event.preventDefault();
        setIsDragging(false);
        acceptFile(event.dataTransfer.files[0]);
      }}
      className={`mb-10 flex flex-col items-center justify-center rounded-2xl border-2 border-dashed bg-white p-12 text-center transition-colors ${isDragging ? 'border-emerald-800 bg-emerald-50' : 'border-slate-300 hover:border-slate-400'}`}
    >
      <input 
        type="file" 
        className="hidden" 
        ref={fileInputRef} 
        onChange={handleFileChange} 
        accept=".pdf,.docx,.txt"
      />
      
      <div className="bg-slate-100 p-4 rounded-xl mb-6">
        <CloudUpload size={28} className="text-slate-700" />
      </div>
      
      <h3 className="text-2xl font-bold text-slate-900 mb-2">Drop documents here</h3>
      <p className="text-slate-500 mb-8 max-w-sm">
        Support for PDF, DOCX, and TXT files. Maximum individual file size 50MB.
      </p>
      
      <div className="flex space-x-4 mb-10">
        <button 
          onClick={() => fileInputRef.current?.click()}
          className="flex items-center space-x-2 bg-[#151238] hover:bg-slate-900 text-white px-5 py-2.5 rounded-lg font-medium text-sm transition-colors shadow-sm"
        >
          <FileText size={16} />
          <span>Select Files</span>
        </button>
      </div>
      
      <div className="flex items-center space-x-8 text-slate-400 font-medium text-sm">
        <div className="flex items-center space-x-2">
          <File size={16} />
          <span>PDF</span>
        </div>
        <div className="flex items-center space-x-2">
          <FileText size={16} />
          <span>DOCX</span>
        </div>
        <div className="flex items-center space-x-2">
          <FileCode size={16} />
          <span>TXT</span>
        </div>
      </div>
    </div>
  );
}
