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
      className={`mb-10 flex flex-col items-center justify-center border-2 border-dashed bg-white p-12 text-center transition-colors ${isDragging ? 'border-emerald-800 bg-[#f4f6f2]' : 'border-slate-300 hover:border-emerald-900/40'}`}
    >
      <input
        type="file"
        className="hidden"
        ref={fileInputRef}
        onChange={handleFileChange}
        accept=".pdf,.docx,.txt"
      />

      <div className="mb-6 bg-[#f4f6f2] p-4">
        <CloudUpload size={28} className="text-emerald-900" />
      </div>

      <h3 className="mb-2 font-serif text-2xl text-emerald-950">Drop documents here</h3>
      <p className="mb-8 max-w-sm text-slate-500">
        Support for PDF, DOCX, and TXT files. Maximum individual file size 50MB.
      </p>

      <div className="mb-10 flex space-x-4">
        <button
          onClick={() => fileInputRef.current?.click()}
          className="flex items-center space-x-2 bg-emerald-950 px-5 py-2.5 text-sm font-medium text-white shadow-sm transition-colors hover:bg-emerald-900"
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
