'use client';

import { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

function formatMessageForMarkdown(content: string): string {
  if (!content) return '';
  return content
    .replace(/<br\s*\/?>/gi, '\n')
    .replace(/\r\n/g, '\n');
}

export default function Home() {
  const [messages, setMessages] = useState<{ role: string; content: string }[]>([]);
  const [input, setInput] = useState('');
  const [file, setFile] = useState<File | null>(null);
  const [uploadStatus, setUploadStatus] = useState('');
  const [isChatLoading, setIsChatLoading] = useState(false);

  // --- 1. File Upload Logic ---
  const handleUpload = async () => {
    if (!file) return;
    setUploadStatus('Uploading...');
    
    const formData = new FormData();
    formData.append('file', file);

    try {
      const res = await fetch(`${API_BASE_URL}/upload`, {
        method: 'POST',
        body: formData,
      });
      if (res.ok) {
        setUploadStatus('File uploaded and sent to Celery worker!');
        setFile(null); // Clear the file input
      } else {
        setUploadStatus(`Upload failed (${res.status}).`);
      }
    } catch {
      setUploadStatus('Error connecting to backend.');
    }
  };

  // --- 2. Chat Logic ---
  const handleChat = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || isChatLoading) return;

    const userMessage = input;
    setInput(''); // Clear input box instantly
    
    // Add user message to UI
    setMessages((prev) => [...prev, { role: 'user', content: userMessage }]);
    
    // Add an empty AI message that we will stream text into
    setMessages((prev) => [...prev, { role: 'ai', content: '' }]); 
    setIsChatLoading(true);

    try {
      const res = await fetch(`${API_BASE_URL}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: userMessage }),
      });
      if (!res.ok) {
        throw new Error(`Chat request failed with status ${res.status}`);
      }
      const data = await res.json();
      const answer = typeof data?.answer === 'string' ? data.answer : 'No response returned.';

      setMessages((prev) => {
        const updated = [...prev];
        updated[updated.length - 1].content = answer;
        return updated;
      });
    } catch (err) {
      console.error('Chat error:', err);
    } finally {
      setIsChatLoading(false);
    }
  };

  // --- 3. Layout UI ---
  return (
    <main className="flex h-screen bg-gray-50 p-4 text-black">
      {/* Sidebar for Uploads */}
      <aside className="w-1/3 max-w-sm bg-white rounded-xl shadow-sm p-6 mr-4 flex flex-col border border-gray-200">
        <h2 className="text-xl font-bold mb-2">Knowledge Base</h2>
        <p className="text-sm text-gray-500 mb-6">
          Upload CSVs for DuckDB or PDFs for Vector Search.
        </p>
        
        <input 
          type="file" 
          onChange={(e) => setFile(e.target.files?.[0] || null)} 
          className="mb-4 text-sm file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-sm file:font-semibold file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100 cursor-pointer"
        />
        <button 
          onClick={handleUpload}
          disabled={!file}
          className="bg-blue-600 text-white py-2 rounded-lg disabled:opacity-50 hover:bg-blue-700 transition font-medium"
        >
          Upload & Process
        </button>
        {uploadStatus && <p className="mt-4 text-sm text-blue-600 font-medium">{uploadStatus}</p>}
      </aside>

      {/* Main Chat Area */}
      <section className="flex-1 bg-white rounded-xl shadow-sm flex flex-col overflow-hidden border border-gray-200">
        <div className="bg-gray-100 p-4 border-b border-gray-200">
          <h2 className="text-xl font-bold">Hybrid Analytics Agent</h2>
        </div>
        
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {messages.map((msg, idx) => (
            <div key={idx} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
              <div className={`max-w-[75%] p-4 rounded-xl shadow-sm ${msg.role === 'user' ? 'bg-blue-600 text-white' : 'bg-gray-50 text-gray-800 border border-gray-200'}`}>
                <ReactMarkdown
                  remarkPlugins={[remarkGfm]}
                  components={{
                    p: ({ children }) => <p className="mb-2 last:mb-0">{children}</p>,
                    ul: ({ children }) => <ul className="list-disc pl-5 mb-2">{children}</ul>,
                    ol: ({ children }) => <ol className="list-decimal pl-5 mb-2">{children}</ol>,
                    table: ({ children }) => (
                      <div className="overflow-x-auto mb-2">
                        <table className="w-full border-collapse text-sm">{children}</table>
                      </div>
                    ),
                    th: ({ children }) => <th className="border border-gray-300 px-2 py-1 text-left">{children}</th>,
                    td: ({ children }) => <td className="border border-gray-300 px-2 py-1">{children}</td>,
                    code: ({ children }) => <code className="bg-black/10 px-1 py-0.5 rounded">{children}</code>,
                  }}
                >
                  {formatMessageForMarkdown(msg.content)}
                </ReactMarkdown>
              </div>
            </div>
          ))}
        </div>

        <form onSubmit={handleChat} className="p-4 border-t border-gray-200 flex gap-2 bg-gray-50">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask about your data..."
            className="flex-1 border border-gray-300 rounded-lg px-4 py-3 focus:outline-none focus:ring-2 focus:ring-blue-600 bg-white"
          />
          <button
            type="submit"
            disabled={isChatLoading}
            className="bg-blue-600 text-white px-8 py-3 rounded-lg hover:bg-blue-700 transition font-bold disabled:opacity-60 disabled:cursor-not-allowed"
          >
            {isChatLoading ? 'Sending...' : 'Send'}
          </button>
        </form>
      </section>
    </main>
  );
}