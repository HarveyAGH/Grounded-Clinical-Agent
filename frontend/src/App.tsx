import { useState, useRef, useEffect } from 'react';
import { Sidebar } from './components/Sidebar';
import { ChatMessage } from './components/ChatMessage';
import { LoadingIndicator } from './components/LoadingIndicator';
import { PromptBar } from './components/PromptBar';
import type { RequestOutput } from './types';

interface Message {
  id: string;
  role: 'user' | 'assistant';
  userText?: string;
  response?: RequestOutput;
  followUps?: string[];
}

function deriveFollowUps(query: string, data: RequestOutput): string[] {
  const q = query.toLowerCase();
  const a = (data.medical_output?.answer || '').toLowerCase();

  if (q.includes('antibiotic') || q.includes('prophylaxis') || a.includes('antibiotic')) {
    return [
      'What alternatives exist for penicillin-allergic patients?',
      'Which cardiac conditions require dental antibiotic prophylaxis?',
    ];
  }
  if (q.includes('caries') || q.includes('fluoride') || a.includes('fluoride')) {
    return [
      'How often should fluoride varnish be applied?',
      'How do sealants compare to fluoride for caries prevention?',
    ];
  }
  if (q.includes('edentulism') || a.includes('edentulism')) {
    return [
      'What are the primary risk factors for edentulism?',
      'How do health policies address oral disease burden?',
    ];
  }
  if (data.status === 'medical_agent') {
    return [
      'Can you elaborate on the supporting evidence?',
      'Are there contraindications to be aware of?',
    ];
  }
  return [];
}

export default function App() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' });
  }, [messages, loading]);

  const send = async (text?: string) => {
    const q = (text || input).trim();
    if (!q || loading) return;

    const userMsg: Message = { id: `u-${Date.now()}`, role: 'user', userText: q };
    setMessages((prev) => [...prev, userMsg]);
    setInput('');
    setLoading(true);

    try {
      const res = await fetch('/query', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: q }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data: RequestOutput = await res.json();
      const followUps = deriveFollowUps(q, data);
      const asstMsg: Message = { id: `a-${Date.now()}`, role: 'assistant', response: data, followUps };
      setMessages((prev) => [...prev, asstMsg]);
    } catch (err: unknown) {
      const errMsg = err instanceof Error ? err.message : 'Connection failed';
      const asstMsg: Message = {
        id: `a-${Date.now()}`,
        role: 'assistant',
        response: { status: 'escalated', conversational_output: `Unable to reach the server: ${errMsg}` },
      };
      setMessages((prev) => [...prev, asstMsg]);
    } finally {
      setLoading(false);
    }
  };

  const reset = () => {
    setMessages([]);
    setInput('');
  };

  const WELCOME_STARTERS = [
    { label: 'Antibiotic prophylaxis guidelines', query: 'What are the indications for antibiotic prophylaxis in dental procedures?' },
    { label: 'Caries prevention evidence', query: 'What does clinical evidence recommend for dental caries prevention?' },
    { label: 'Global oral health status', query: 'What is edentulism and how is oral disease measured globally?' },
    { label: 'How verification works', query: 'How does the clinical verification process work?' },
  ];

  return (
    <div className="app">
      <Sidebar onNewChat={reset} onSelectPrompt={(q) => send(q)} />

      <main className="chat-area">
        <div className="chat-scroll" ref={scrollRef}>
          <div className="chat-inner">
            {messages.length === 0 ? (
              <div className="welcome">
                <div className="welcome-icon">
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="var(--ink-2)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M12 2l2.4 7.2L22 12l-7.6 2.8L12 22l-2.4-7.2L2 12l7.6-2.8z" />
                  </svg>
                </div>
                <h2>What can I help with?</h2>
                <p>Ask questions about dental clinical guidelines. Answers are retrieved from evidence documents and verified for accuracy.</p>
                <div className="welcome-starters">
                  {WELCOME_STARTERS.map((s, i) => (
                    <button key={i} className="welcome-starter-btn" onClick={() => send(s.query)}>
                      <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        <path d="M9 10l-5 5 5 5" />
                        <path d="M20 4v7a4 4 0 0 1-4 4H4" />
                      </svg>
                      {s.label}
                    </button>
                  ))}
                </div>
              </div>
            ) : (
              messages.map((msg) => (
                <ChatMessage
                  key={msg.id}
                  role={msg.role}
                  userText={msg.userText}
                  response={msg.response}
                  followUps={msg.followUps}
                  onFollowUp={(q) => send(q)}
                />
              ))
            )}
            {loading && <LoadingIndicator />}
          </div>
        </div>

        <PromptBar
          value={input}
          onChange={setInput}
          onSend={() => send()}
          disabled={loading}
        />
      </main>
    </div>
  );
}
