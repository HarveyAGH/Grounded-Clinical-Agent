import { useEffect, useState } from 'react';

const CHEVRON_DELAYS = [90, 180, 270, 0, 90, 180, 90, 180, 270];

function useElapsed() {
  const [ds, setDs] = useState(0);
  useEffect(() => {
    const t = setInterval(() => setDs((d) => d + 1), 100);
    return () => clearInterval(t);
  }, []);
  const total = ds / 10;
  if (total < 60) return `${total.toFixed(1)}s`;
  return `${Math.floor(total / 60)}m ${(total % 60).toFixed(1)}s`;
}

export function LoadingIndicator() {
  const elapsed = useElapsed();

  return (
    <div className="msg-row">
      <div className="loading-row">
        <span aria-hidden className="pixel-grid">
          {CHEVRON_DELAYS.map((delay, i) => (
            <span
              key={i}
              className="pixel-cell animated"
              style={{ animationDelay: `${delay}ms` }}
            />
          ))}
        </span>
        <span className="shimmer-label">Thinking</span>
        <span className="elapsed-time">{elapsed}</span>
      </div>
    </div>
  );
}
