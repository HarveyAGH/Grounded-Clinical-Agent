import { useState, useEffect } from 'react';
import type { RequestOutput } from '../types';

interface ChatMessageProps {
  role: 'user' | 'assistant';
  userText?: string;
  response?: RequestOutput;
  followUps?: string[];
  onFollowUp: (q: string) => void;
}

const WORD_MS = 30;

export function ChatMessage({ role, userText, response, followUps, onFollowUp }: ChatMessageProps) {
  const [sourcesOpen, setSourcesOpen] = useState(false);
  const [toolsOpen, setToolsOpen] = useState(false);
  const [wordCount, setWordCount] = useState(0);

  const isMedical = response?.status === 'medical_agent' && Boolean(response?.medical_output);
  const med = response?.medical_output;

  // Detect if the claims are actually system fallbacks/refusals
  const isRefusal = med?.claims?.every(c => 
    c.citation === 'System Fallback' || 
    c.citation === '[Technical Error]' || 
    c.confidence === 0 || 
    c.claim.includes('Escalated') ||
    c.claim.includes('Unable to') ||
    c.claim.includes('does not contain')
  ) ?? false;

  const showVerificationUI = isMedical && med && med.claims && med.claims.length > 0 && !isRefusal;
  
  // Streaming text logic
  const answerText = isMedical && med ? med.answer : (response?.conversational_output || '');
  const tokens = answerText.split(' ');
  const done = wordCount >= tokens.length;

  useEffect(() => {
    if (role === 'assistant' && !done) {
      const t = setTimeout(() => {
        setWordCount(c => c + 1);
      }, WORD_MS);
      return () => clearTimeout(t);
    }
  }, [wordCount, done, role]);

  useEffect(() => {
    if (role === 'assistant') {
      // Auto-open sources if not grounded
      if (response?.groundness_verdict !== 'claim_is_tracable' && med?.claims && med.claims.length > 0) {
        setSourcesOpen(true);
      }
    }
  }, [role, response, med]);

  if (role === 'user') {
    return (
      <div className="msg-row user">
        <div className="msg-user-bubble">{userText}</div>
      </div>
    );
  }

  if (!response) return null;
  const isGrounded = response.groundness_verdict === 'claim_is_tracable';

  return (
    <div className="msg-row">
      <div className="msg-assistant">
        {/* Answer text with streaming reveal */}
        <div className="msg-answer-text">
          {tokens.slice(0, wordCount).map((token, i) => (
             <span
               key={i}
               className="inline [will-change:filter,opacity]"
               style={{ animation: "stream-in 320ms cubic-bezier(0.22,0.61,0.25,1) both" }}
             >
               {token}{" "}
             </span>
          ))}
          {!done && (
            <span
              className="ml-0.5 rounded-full"
              style={{ display: 'inline-block', width: '2px', height: '14px', background: 'var(--ink)', verticalAlign: 'middle', animation: 'fade-in 150ms ease-out both, pixel-on 650ms infinite' }}
            />
          )}
        </div>

        {/* Action / Source row - only show when streaming finishes */}
        <div style={{ opacity: done ? 1 : 0, transition: 'opacity 400ms ease', pointerEvents: done ? 'auto' : 'none', display: 'flex', flexDirection: 'column', gap: '8px' }}>
          
          {/* Tool Chips */}
          {response.retrieved_chunks && response.retrieved_chunks.length > 0 && (
            <div>
              <button
                className="tool-chips-toggle"
                data-open={toolsOpen}
                onClick={() => setToolsOpen(!toolsOpen)}
              >
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M6 9l6 6 6-6" />
                </svg>
                {response.retrieved_chunks.length} chunks retrieved
              </button>
              <div className="tool-chips-panel" data-open={toolsOpen}>
                <div className="tool-chips-inner">
                  <div className="tool-chip">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M17 8l-5-5-5 5M12 3v12" />
                    </svg>
                    <span>Vector DB query executed ({response.retrieved_chunks.length} results)</span>
                  </div>
                </div>
              </div>
            </div>
          )}

          <div style={{ display: 'flex', alignItems: 'center', gap: '12px', flexWrap: 'wrap' }}>
            {/* Verification status */}
            {showVerificationUI && (
              <span className={`verified-badge ${isGrounded ? 'grounded' : 'review'}`}>
                {isGrounded ? (
                  <>
                    <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M20 6L9 17l-5-5" />
                    </svg>
                    Verified
                  </>
                ) : (
                  'Review needed'
                )}
              </span>
            )}

            {/* Expandable sources/claims */}
            {showVerificationUI && (
              <button
                className="sources-toggle"
                data-open={sourcesOpen}
                onClick={() => setSourcesOpen(!sourcesOpen)}
              >
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M6 9l6 6 6-6" />
                </svg>
                {med!.claims.length} source{med!.claims.length === 1 ? '' : 's'}
              </button>
            )}
          </div>

          {/* Sources Dropdown */}
          {showVerificationUI && (
            <div className="sources-panel" data-open={sourcesOpen}>
              <div className="sources-panel-inner">
                <div style={{ display: 'flex', flexDirection: 'column', background: 'var(--inset)', borderRadius: '10px', padding: '4px', boxShadow: 'var(--shadow-hairline)', gap: '2px', marginTop: '4px' }}>
                  {med.claims.map((c, i) => (
                    <div 
                      key={i} 
                      style={{ 
                        display: 'flex', 
                        alignItems: 'flex-start', 
                        gap: '8px', 
                        padding: '6px 8px', 
                        borderRadius: '6px', 
                        fontSize: '12px', 
                        color: 'var(--ink-2)',
                        transition: 'background 150ms ease, color 150ms ease'
                      }}
                      onMouseEnter={(e) => { e.currentTarget.style.background = 'var(--hover)'; e.currentTarget.style.color = 'var(--ink)'; }}
                      onMouseLeave={(e) => { e.currentTarget.style.background = 'transparent'; e.currentTarget.style.color = 'var(--ink-2)'; }}
                    >
                      <span style={{ fontFamily: 'var(--font-mono)', fontSize: '10.5px', color: 'var(--ink-3)', marginTop: '2px', flexShrink: 0 }}>[{i + 1}]</span>
                      <span style={{ flex: 1, lineHeight: 1.5, wordBreak: 'break-word' }}>{c.claim}</span>
                      <span style={{ marginLeft: 'auto', fontFamily: 'var(--font-mono)', fontSize: '10.5px', color: 'var(--ink-3)', flexShrink: 0, maxWidth: '140px', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', marginTop: '2px' }} title={c.citation}>{c.citation}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* Disclaimer */}
          {isMedical && med && med.disclaimer && (
            <div className="msg-disclaimer">{med.disclaimer}</div>
          )}

          {/* Follow-ups */}
          {followUps && followUps.length > 0 && (
            <div className="followups">
              <div className="followup-label">Follow-ups</div>
              {followUps.map((fq, i) => (
                <button 
                  key={i} 
                  className="followup-btn" 
                  onClick={() => onFollowUp(fq)}
                  style={{ animation: `fade-up 350ms cubic-bezier(0.23,1,0.32,1) ${i * 90}ms both` }}
                >
                  <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M9 10l-5 5 5 5" />
                    <path d="M20 4v7a4 4 0 0 1-4 4H4" />
                  </svg>
                  {fq}
                </button>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
