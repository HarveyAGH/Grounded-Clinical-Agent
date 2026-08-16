document.addEventListener('DOMContentLoaded', () => {
  const chatForm = document.getElementById('chat-form');
  const queryInput = document.getElementById('query-input');
  const btnSubmit = document.getElementById('btn-submit');
  const messagesList = document.getElementById('messages-list');
  const welcomeCard = document.getElementById('welcome-card');
  const btnClearChat = document.getElementById('btn-clear-chat');
  
  // Evidence panel elements
  const evidencePanel = document.getElementById('evidence-panel');
  const evidenceContent = document.getElementById('evidence-content');
  const evidenceEmptyState = document.getElementById('evidence-empty-state');
  const evidenceCountBadge = document.getElementById('evidence-count-badge');
  
  // Modal elements
  const citationModal = document.getElementById('citation-modal');
  const modalBackdrop = document.getElementById('modal-backdrop');
  const modalClose = document.getElementById('modal-close');
  const modalClaimText = document.getElementById('modal-claim-text');
  const modalConfidenceBar = document.getElementById('modal-confidence-bar');
  const modalConfidenceText = document.getElementById('modal-confidence-text');
  const modalSourceText = document.getElementById('modal-source-text');

  // Handle Enter key for textarea
  queryInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      if (queryInput.value.trim()) {
        chatForm.requestSubmit();
      }
    }
  });

  // Auto-resize textarea
  queryInput.addEventListener('input', () => {
    queryInput.style.height = 'auto';
    queryInput.style.height = `${Math.min(queryInput.scrollHeight, 120)}px`;
  });

  // Sample prompt pills
  document.querySelectorAll('.pill-btn').forEach(pill => {
    pill.addEventListener('click', () => {
      const query = pill.getAttribute('data-query');
      if (query) {
        queryInput.value = query;
        queryInput.dispatchEvent(new Event('input'));
        chatForm.requestSubmit();
      }
    });
  });

  // Reset Session
  btnClearChat.addEventListener('click', () => {
    messagesList.innerHTML = '';
    if (welcomeCard) {
      messagesList.appendChild(welcomeCard);
      welcomeCard.style.display = 'block';
    }
    resetEvidencePanel();
  });

  // Modal close handlers
  const closeModal = () => citationModal.classList.add('hidden');
  modalClose.addEventListener('click', closeModal);
  modalBackdrop.addEventListener('click', closeModal);

  // Form Submit
  chatForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const query = queryInput.value.trim();
    if (!query) return;

    // Hide welcome card once chat starts
    if (welcomeCard) {
      welcomeCard.style.display = 'none';
    }

    // Append User Message
    appendUserMessage(query);
    queryInput.value = '';
    queryInput.style.height = 'auto';
    btnSubmit.disabled = true;

    // Show loading skeleton
    const loadingCardId = appendLoadingIndicator();

    try {
      const response = await fetch('/query', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query })
      });

      if (!response.ok) {
        throw new Error(`Server error (${response.status})`);
      }

      const data = await response.json();
      removeLoadingIndicator(loadingCardId);
      renderAgentResponse(data);

      if (data.retrieved_chunks && data.retrieved_chunks.length > 0) {
        renderEvidenceChunks(data.retrieved_chunks);
      }
    } catch (err) {
      removeLoadingIndicator(loadingCardId);
      appendErrorMessage(`Failed to communicate with agent: ${err.message}`);
    } finally {
      btnSubmit.disabled = false;
      queryInput.focus();
    }
  });

  function appendUserMessage(text) {
    const row = document.createElement('div');
    row.className = 'message-row user-row';
    row.innerHTML = `<div class="user-bubble">${escapeHtml(text)}</div>`;
    messagesList.appendChild(row);
    scrollToBottom();
  }

  function appendLoadingIndicator() {
    const id = `loading-${Date.now()}`;
    const row = document.createElement('div');
    row.className = 'message-row';
    row.id = id;
    row.innerHTML = `
      <div class="agent-response-card">
        <div class="agent-response-header">
          <div class="agent-tag-group">
            <span class="badge badge-medical">Clinical Graph</span>
          </div>
          <span style="font-size: 0.72rem; color: var(--text-muted); font-family: var(--font-mono);">Retrieving & Verifying...</span>
        </div>
        <div class="typing-dots">
          <div class="dot"></div>
          <div class="dot"></div>
          <div class="dot"></div>
        </div>
      </div>
    `;
    messagesList.appendChild(row);
    scrollToBottom();
    return id;
  }

  function removeLoadingIndicator(id) {
    const el = document.getElementById(id);
    if (el) el.remove();
  }

  function renderAgentResponse(data) {
    const row = document.createElement('div');
    row.className = 'message-row';

    const isMedical = Boolean(data.medical_output);
    const isEscalated = data.status === 'escalated';
    
    let badgeHtml = isMedical 
      ? `<span class="badge badge-medical">Clinical Agent</span>`
      : `<span class="badge badge-conversational">General Agent</span>`;

    if (isEscalated) {
      badgeHtml += ` <span class="badge badge-escalated">Escalated to Human</span>`;
    } else if (isMedical && data.groundness_verdict === 'claim_is_tracable') {
      badgeHtml += ` <span class="badge badge-verified">Verified Grounded</span>`;
    }

    let bodyHtml = '';

    if (isMedical && data.medical_output) {
      const med = data.medical_output;
      
      // Main Answer
      bodyHtml += `<div class="response-answer-text">${formatMarkdownSimple(med.answer)}</div>`;

      // Claims with interactive citations
      if (med.claims && med.claims.length > 0) {
        bodyHtml += `
          <div class="claims-container">
            <div class="claims-title">
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <polyline points="9 11 12 14 22 4"></polyline>
                <path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"></path>
              </svg>
              Extracted & Cited Claims (${med.claims.length})
            </div>
            <ul class="claims-list">
        `;

        med.claims.forEach((c) => {
          const confidencePct = Math.round((c.confidence || 1.0) * 100);
          bodyHtml += `
            <li class="claim-item">
              <div class="claim-text">${escapeHtml(c.claim)}</div>
              <button 
                class="citation-chip" 
                data-claim="${escapeHtml(c.claim)}" 
                data-citation="${escapeHtml(c.citation)}" 
                data-confidence="${confidencePct}"
              >
                ${escapeHtml(c.citation)} • ${confidencePct}%
              </button>
            </li>
          `;
        });

        bodyHtml += `</ul></div>`;
      }

      // Disclaimer Banner
      if (med.disclaimer) {
        bodyHtml += `
          <div class="disclaimer-banner">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="flex-shrink: 0;">
              <circle cx="12" cy="12" r="10"></circle>
              <line x1="12" y1="8" x2="12" y2="12"></line>
              <line x1="12" y1="16" x2="12.01" y2="16"></line>
            </svg>
            <span>${escapeHtml(med.disclaimer)}</span>
          </div>
        `;
      }

      // Groundness Feedback footer
      if (data.feedback) {
        bodyHtml += `
          <div class="verification-summary">
            <span>Groundness Verdict: <strong>${escapeHtml(data.groundness_verdict || 'Verified')}</strong></span>
            <span>Retries: ${data.retry_count || 0}</span>
          </div>
        `;
      }

    } else {
      // Conversational / Fallback text
      const content = data.conversational_output || 'No response generated.';
      bodyHtml += `<div class="response-answer-text">${formatMarkdownSimple(content)}</div>`;
    }

    row.innerHTML = `
      <div class="agent-response-card">
        <div class="agent-response-header">
          <div class="agent-tag-group">${badgeHtml}</div>
          <span style="font-size: 0.72rem; color: var(--text-muted); font-family: var(--font-mono);">Evidence RAG Engine</span>
        </div>
        ${bodyHtml}
      </div>
    `;

    messagesList.appendChild(row);

    // Attach click events to citation chips in this card
    row.querySelectorAll('.citation-chip').forEach(chip => {
      chip.addEventListener('click', () => {
        openCitationModal({
          claim: chip.getAttribute('data-claim'),
          citation: chip.getAttribute('data-citation'),
          confidence: chip.getAttribute('data-confidence')
        });
      });
    });

    scrollToBottom();
  }

  function appendErrorMessage(errorText) {
    const row = document.createElement('div');
    row.className = 'message-row';
    row.innerHTML = `
      <div class="agent-response-card" style="border-color: var(--danger-primary);">
        <div class="agent-response-header">
          <span class="badge badge-escalated">System Alert</span>
        </div>
        <p style="color: var(--danger-primary); font-size: 0.88rem;">${escapeHtml(errorText)}</p>
      </div>
    `;
    messagesList.appendChild(row);
    scrollToBottom();
  }

  function renderEvidenceChunks(chunks) {
    if (!chunks || chunks.length === 0) {
      resetEvidencePanel();
      return;
    }

    evidenceEmptyState.classList.add('hidden');
    evidenceContent.classList.remove('hidden');
    evidenceCountBadge.textContent = `${chunks.length} Chunk${chunks.length > 1 ? 's' : ''}`;

    evidenceContent.innerHTML = chunks.map((chunk, i) => {
      return `
        <div class="chunk-card">
          <div class="chunk-header">
            <span class="badge badge-medical">Chunk ${i + 1}</span>
          </div>
          <div class="chunk-body">${escapeHtml(chunk)}</div>
        </div>
      `;
    }).join('');
  }

  function resetEvidencePanel() {
    evidenceEmptyState.classList.remove('hidden');
    evidenceContent.classList.add('hidden');
    evidenceContent.innerHTML = '';
    evidenceCountBadge.textContent = '0 Chunks';
  }

  function openCitationModal(details) {
    modalClaimText.textContent = details.claim;
    modalSourceText.textContent = details.citation;
    modalConfidenceText.textContent = `${details.confidence}% confidence`;
    modalConfidenceBar.style.width = `${details.confidence}%`;
    citationModal.classList.remove('hidden');
  }

  function scrollToBottom() {
    messagesList.scrollTop = messagesList.scrollHeight;
  }

  function escapeHtml(str) {
    if (!str) return '';
    return str
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  function formatMarkdownSimple(text) {
    if (!text) return '';
    let parsed = escapeHtml(text);
    parsed = parsed.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
    parsed = parsed.replace(/\*(.*?)\*/g, '<em>$1</em>');
    parsed = parsed.replace(/\n\n/g, '<br><br>').replace(/\n/g, '<br>');
    return parsed;
  }
});
