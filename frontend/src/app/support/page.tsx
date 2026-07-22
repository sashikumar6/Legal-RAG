import Link from 'next/link';

export default function SupportPage() {
  return (
    <div className="p-8 max-w-2xl">
      <h1 className="text-xl font-bold text-slate-900 mb-4">Support</h1>
      <p className="text-sm text-slate-600 mb-2">
        The Digital Jurist is an AI legal research assistant. For informational purposes only —
        not legal advice.
      </p>
      <p className="text-sm text-slate-600">
        Found a bug or have a question? Open an issue on{' '}
        <a
          href="https://github.com/sashikumar6/Legal-RAG/issues"
          target="_blank"
          rel="noopener noreferrer"
          className="text-slate-900 underline hover:no-underline"
        >
          GitHub
        </a>.
      </p>
      <Link href="/" className="inline-block mt-6 text-sm text-slate-500 hover:text-slate-900">
        ← Back
      </Link>
    </div>
  );
}
