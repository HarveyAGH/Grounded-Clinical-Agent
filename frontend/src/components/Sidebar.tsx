interface SidebarProps {
  onNewChat: () => void;
  onSelectPrompt: (q: string) => void;
}

const STARTERS = [
  'What are the indications for antibiotic prophylaxis in dental procedures?',
  'What does clinical evidence recommend for dental caries prevention?',
  'What is edentulism and how is oral disease measured globally?',
  'How does the clinical verification process work?',
];

export function Sidebar({ onNewChat, onSelectPrompt }: SidebarProps) {
  return (
    <aside className="sidebar">
      <div className="sidebar-brand">
        <div className="sidebar-brand-icon">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M12 2l2.4 7.2L22 12l-7.6 2.8L12 22l-2.4-7.2L2 12l7.6-2.8z" />
          </svg>
        </div>
        <span className="sidebar-brand-name">Clinical AI</span>
      </div>

      <button className="btn-new-chat" onClick={onNewChat}>
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
          <path d="M12 5v14M5 12h14" />
        </svg>
        New chat
      </button>

      <div>
        <div className="sidebar-section-label">Suggested</div>
        <div className="sidebar-starters">
          {STARTERS.map((q, i) => (
            <button key={i} className="starter-btn" onClick={() => onSelectPrompt(q)}>
              <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M9 10l-5 5 5 5" />
                <path d="M20 4v7a4 4 0 0 1-4 4H4" />
              </svg>
              <span>{q}</span>
            </button>
          ))}
        </div>
      </div>
    </aside>
  );
}
