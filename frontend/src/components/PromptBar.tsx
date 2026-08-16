interface PromptBarProps {
  value: string;
  onChange: (v: string) => void;
  onSend: () => void;
  disabled: boolean;
}

export function PromptBar({ value, onChange, onSend, disabled }: PromptBarProps) {
  return (
    <div className="prompt-dock">
      <form
        className="prompt-form"
        onSubmit={(e) => {
          e.preventDefault();
          if (value.trim() && !disabled) onSend();
        }}
      >
        <div className="prompt-frame">
          <textarea
            className="prompt-textarea"
            rows={1}
            placeholder="Ask a clinical question..."
            value={value}
            onChange={(e) => onChange(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                if (value.trim() && !disabled) onSend();
              }
            }}
          />
          <button
            type="submit"
            className="btn-send"
            disabled={!value.trim() || disabled}
            aria-label="Send"
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <path d="M12 19V5M5 12l7-7 7 7" />
            </svg>
          </button>
        </div>
        <div className="prompt-footer">
          Responses are verified against clinical guidelines
        </div>
      </form>
    </div>
  );
}
