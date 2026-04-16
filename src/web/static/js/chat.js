/* Velora Chat — SSE-Client + Thread-Management + Markdown-Rendering */

(function () {
  'use strict';

  const state = {
    threads: [],
    currentThreadId: null,
    messages: [],
    streaming: false,
    currentAssistantEl: null,
    currentAssistantText: '',
    activeToolCards: new Map(), // tool_use_id -> card element
    abortController: null,
    pinnedIds: new Set(), // lokaler Cache für "gepinnt"-Badge
  };

  // ── DOM-Refs (werden bei DOMContentLoaded gefüllt) ──
  let $threadList, $messages, $input, $sendBtn, $headerTitle, $pinToggle,
      $deleteBtn, $search, $newBtn, $emptyState;

  // ── Utilities ───────────────────────────────────────
  const el = (tag, attrs = {}, ...children) => {
    const node = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs)) {
      if (k === 'class') node.className = v;
      else if (k === 'dataset') Object.assign(node.dataset, v);
      else if (k.startsWith('on') && typeof v === 'function') node.addEventListener(k.slice(2), v);
      else if (v !== undefined && v !== null) node.setAttribute(k, v);
    }
    for (const c of children) {
      if (c === null || c === undefined) continue;
      node.appendChild(typeof c === 'string' ? document.createTextNode(c) : c);
    }
    return node;
  };

  const formatRelTime = (iso) => {
    if (!iso) return '';
    const d = new Date(iso.replace(' ', 'T'));
    const now = new Date();
    const diffSec = Math.floor((now - d) / 1000);
    if (diffSec < 60) return 'gerade';
    if (diffSec < 3600) return `${Math.floor(diffSec / 60)} Min`;
    if (diffSec < 86400) return `${Math.floor(diffSec / 3600)} Std`;
    if (diffSec < 604800) return `${Math.floor(diffSec / 86400)} T`;
    return d.toLocaleDateString('de-DE', { day: '2-digit', month: '2-digit' });
  };

  const renderMarkdown = (text) => {
    if (typeof marked === 'undefined') return escapeHtml(text);
    try {
      marked.setOptions({ breaks: true, gfm: true });
      return marked.parse(text || '');
    } catch {
      return escapeHtml(text);
    }
  };

  const escapeHtml = (s) => (s || '').replace(/[&<>"']/g, c =>
    ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));

  const scrollToBottom = () => {
    requestAnimationFrame(() => {
      $messages.scrollTop = $messages.scrollHeight;
    });
  };

  // ── API-Calls ───────────────────────────────────────
  const api = {
    listThreads: () => fetch('/api/chat/threads').then(r => r.json()),
    createThread: (title) => fetch('/api/chat/threads', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ title: title || 'Neuer Chat' })
    }).then(r => r.json()),
    getThread: (id) => fetch(`/api/chat/threads/${id}`).then(r => r.json()),
    patchThread: (id, body) => fetch(`/api/chat/threads/${id}`, {
      method: 'PATCH',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(body),
    }).then(r => r.json()),
    deleteThread: (id) => fetch(`/api/chat/threads/${id}`, { method: 'DELETE' }).then(r => r.json()),
    listPins: (threadId) => fetch(`/api/chat/pins?thread_id=${threadId || ''}`).then(r => r.json()),
    createPin: (body) => fetch('/api/chat/pins', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(body),
    }).then(r => r.json()),
    deletePin: (id) => fetch(`/api/chat/pins/${id}`, { method: 'DELETE' }).then(r => r.json()),
  };

  // ── Thread-Liste rendern ────────────────────────────
  const renderThreadList = () => {
    $threadList.innerHTML = '';
    const q = ($search.value || '').trim().toLowerCase();
    const filtered = q ? state.threads.filter(t => (t.title || '').toLowerCase().includes(q)) : state.threads;

    if (filtered.length === 0) {
      $threadList.appendChild(el('div', { class: 'chat-thread-empty' },
        state.threads.length === 0 ? 'Noch keine Chats — starte einen neuen.' : 'Keine Treffer'));
      return;
    }

    for (const t of filtered) {
      const isActive = t.id === state.currentThreadId;
      const item = el('div', {
        class: 'chat-thread-item' + (isActive ? ' active' : ''),
        dataset: { id: t.id },
        onclick: (e) => {
          if (e.target.closest('.chat-thread-delete')) return;
          selectThread(t.id);
        },
      },
        el('div', { class: 'chat-thread-title' },
          t.is_pinned ? el('span', { class: 'chat-thread-pin-indicator' }, '★ ') : null,
          t.title || 'Neuer Chat'),
        el('div', { class: 'chat-thread-meta' },
          `${t.message_count || 0} Nachr.`,
          ' · ',
          formatRelTime(t.updated_at)),
        el('button', {
          class: 'chat-thread-delete',
          title: 'Chat löschen',
          onclick: async (e) => {
            e.stopPropagation();
            if (!confirm(`Chat "${t.title}" wirklich löschen?`)) return;
            await api.deleteThread(t.id);
            if (state.currentThreadId === t.id) state.currentThreadId = null;
            await loadThreads();
            if (!state.currentThreadId) showEmptyState();
          },
        }, '×'),
      );
      $threadList.appendChild(item);
    }
  };

  const loadThreads = async () => {
    const { threads } = await api.listThreads();
    state.threads = threads || [];
    renderThreadList();
  };

  // ── Thread auswählen ────────────────────────────────
  const selectThread = async (threadId) => {
    state.currentThreadId = threadId;
    state.messages = [];
    renderThreadList();
    $messages.innerHTML = '';
    $headerTitle.textContent = 'Lade…';

    const { thread, messages } = await api.getThread(threadId);
    state.messages = messages || [];
    $headerTitle.textContent = thread.title || 'Chat';
    $pinToggle.classList.toggle('active', !!thread.is_pinned);
    $pinToggle.textContent = thread.is_pinned ? '★ Angeheftet' : '☆ Anheften';

    // Pins für diesen Thread laden
    const pinsResp = await api.listPins(threadId);
    state.pinnedIds = new Set();
    (pinsResp.pins || []).forEach(p => {
      if (p.key.startsWith('msg:')) state.pinnedIds.add(p.key.slice(4));
    });

    renderAllMessages();
    $input.focus();
    try { localStorage.setItem('velora_last_thread', threadId); } catch {}
  };

  const showEmptyState = () => {
    state.currentThreadId = null;
    $messages.innerHTML = '';
    $headerTitle.textContent = 'Velora';
    $pinToggle.textContent = '☆ Anheften';
    $pinToggle.classList.remove('active');

    const empty = el('div', { class: 'chat-empty-state' },
      el('h2', {}, 'Velora'),
      el('p', {}, 'Dein persönlicher KI-Vermögensberater. Frag mich alles zu deinem Portfolio, Märkten, Trades.'),
      el('div', { class: 'suggestion-row' },
        el('div', { class: 'suggestion', onclick: () => startWithPrompt('Wie ist mein Portfolio aktuell aufgestellt? Was fällt dir auf?') },
          'Wie ist mein Portfolio aktuell aufgestellt?'),
        el('div', { class: 'suggestion', onclick: () => startWithPrompt('Welche Risiken siehst du im Portfolio diese Woche?') },
          'Welche Risiken siehst du diese Woche?'),
        el('div', { class: 'suggestion', onclick: () => startWithPrompt('Gibt es gerade eine interessante Kaufgelegenheit, die zu meinem Portfolio passt?') },
          'Interessante Kaufgelegenheiten?'),
        el('div', { class: 'suggestion', onclick: () => startWithPrompt('Was sagt das aktuelle Makro-Umfeld für meine Positionen aus?') },
          'Makro-Umfeld für meine Positionen?'),
      ),
    );
    $messages.appendChild(empty);
  };

  const startWithPrompt = async (prompt) => {
    // Neuen Thread erzeugen und gleich die Suggestion abschicken
    const thread = await api.createThread('Neuer Chat');
    state.threads.unshift(thread);
    await selectThread(thread.id);
    $input.value = prompt;
    sendMessage();
  };

  // ── Messages rendern ────────────────────────────────
  const renderAllMessages = () => {
    $messages.innerHTML = '';
    if (state.messages.length === 0) {
      const hint = el('div', { class: 'chat-empty-state', style: 'margin-top: auto; margin-bottom: auto;' },
        el('p', {}, 'Stell deine Frage — Velora denkt mit.'));
      $messages.appendChild(hint);
      return;
    }
    for (const msg of state.messages) renderMessage(msg);
    scrollToBottom();
  };

  const renderMessage = (msg) => {
    if (msg.role === 'user' || msg.role === 'assistant') {
      const bubble = el('div', { class: 'msg-bubble' });
      bubble.innerHTML = msg.role === 'assistant' ? renderMarkdown(msg.content) : escapeHtml(msg.content).replace(/\n/g, '<br>');

      const pinned = state.pinnedIds.has(String(msg.id));
      const msgEl = el('div', { class: 'msg ' + msg.role, dataset: { id: msg.id } },
        bubble,
        el('div', { class: 'msg-footer' },
          el('button', {
            class: 'msg-footer-btn copy-btn',
            title: 'Kopieren',
            onclick: () => navigator.clipboard.writeText(msg.content),
          }, 'Kopieren'),
          msg.role === 'assistant' ? el('button', {
            class: 'msg-footer-btn pin-btn' + (pinned ? ' pinned' : ''),
            title: pinned ? 'Pin entfernen' : 'Pinnen (für künftige Chats merken)',
            onclick: async (e) => {
              const btn = e.currentTarget;
              if (btn.classList.contains('pinned')) {
                // Pin entfernen: Pins durchsuchen
                const { pins } = await api.listPins('');
                const p = pins.find(pp => pp.key === `msg:${msg.id}`);
                if (p) {
                  await api.deletePin(p.id);
                  state.pinnedIds.delete(String(msg.id));
                  btn.classList.remove('pinned');
                  btn.textContent = '☆ Pin';
                }
              } else {
                const value = msg.content.slice(0, 500);
                await api.createPin({ key: `msg:${msg.id}`, value });
                state.pinnedIds.add(String(msg.id));
                btn.classList.add('pinned');
                btn.textContent = '★ Gepinnt';
              }
            },
          }, pinned ? '★ Gepinnt' : '☆ Pin') : null,
        ),
      );
      $messages.appendChild(msgEl);
    } else if (msg.role === 'tool_use') {
      try {
        const d = JSON.parse(msg.content);
        const card = createToolCard(d.id, d.name, d.input);
        card.classList.add('done');
        const spinner = card.querySelector('.tool-card-spinner');
        if (spinner) spinner.replaceWith(el('span', { class: 'tool-card-icon' }, '✓'));
        $messages.appendChild(card);
      } catch {}
    }
  };

  const createToolCard = (toolUseId, name, input) => {
    const inputSummary = summarizeToolInput(name, input);
    return el('div', { class: 'tool-card', dataset: { id: toolUseId || '' } },
      el('span', { class: 'tool-card-spinner' }),
      el('span', { class: 'tool-card-name' }, name),
      inputSummary ? el('span', { class: 'tool-card-details' }, inputSummary) : null,
    );
  };

  const summarizeToolInput = (name, input) => {
    if (!input || typeof input !== 'object') return '';
    if (input.ticker) return `(${input.ticker})`;
    if (input.query) return `"${String(input.query).slice(0, 40)}"`;
    if (input.key) return `(${input.key})`;
    const keys = Object.keys(input);
    if (keys.length === 0) return '';
    return `(${keys.slice(0, 2).join(', ')})`;
  };

  // ── Senden / Streaming ──────────────────────────────
  const sendMessage = async () => {
    if (state.streaming) return;
    const text = $input.value.trim();
    if (!text) return;

    if (!state.currentThreadId) {
      const t = await api.createThread('Neuer Chat');
      state.threads.unshift(t);
      state.currentThreadId = t.id;
      renderThreadList();
    }

    // Leeren State clearen, falls wir auf Empty-State waren
    if ($messages.querySelector('.chat-empty-state')) $messages.innerHTML = '';

    // User-Bubble sofort rendern
    const userMsg = { id: 'tmp-u-' + Date.now(), role: 'user', content: text };
    state.messages.push(userMsg);
    renderMessage(userMsg);

    $input.value = '';
    $input.style.height = 'auto';
    setStreaming(true);

    // Assistant-Bubble vorbereiten
    state.currentAssistantText = '';
    const bubble = el('div', { class: 'msg-bubble' },
      el('span', { class: 'streaming-cursor' }));
    const assistantEl = el('div', { class: 'msg assistant' }, bubble);
    $messages.appendChild(assistantEl);
    state.currentAssistantEl = bubble;
    scrollToBottom();

    // Page-Context sammeln (für Widget + später context-aware Prompts)
    const pageContext = {
      page: document.body.dataset.page || null,
      focused_ticker: window.veloraFocusedTicker || null,
    };

    // POST an SSE-Endpoint: Fetch-Stream manuell parsen (EventSource unterstützt kein POST)
    const ctrl = new AbortController();
    state.abortController = ctrl;

    let response;
    try {
      response = await fetch(`/api/chat/threads/${state.currentThreadId}/message`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text, page_context: pageContext }),
        signal: ctrl.signal,
      });
    } catch (e) {
      finishAssistantWithError('Netzwerkfehler: ' + e.message);
      setStreaming(false);
      return;
    }

    if (!response.ok) {
      const errTxt = await response.text();
      finishAssistantWithError(`Fehler ${response.status}: ${errTxt.slice(0, 200)}`);
      setStreaming(false);
      return;
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder('utf-8');
    let buffer = '';

    try {
      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });

        // SSE-Events sind durch Leerzeile getrennt
        let idx;
        while ((idx = buffer.indexOf('\n\n')) !== -1) {
          const rawEvent = buffer.slice(0, idx);
          buffer = buffer.slice(idx + 2);
          handleSseEvent(rawEvent);
        }
      }
    } catch (e) {
      if (e.name !== 'AbortError') console.error('Stream error:', e);
    } finally {
      finalizeAssistant();
      setStreaming(false);
      state.abortController = null;
      // Thread-Liste neu laden (für updated_at + title)
      loadThreads();
    }
  };

  const handleSseEvent = (raw) => {
    const lines = raw.split('\n');
    let event = 'message', data = '';
    for (const line of lines) {
      if (line.startsWith('event:')) event = line.slice(6).trim();
      else if (line.startsWith('data:')) data += (data ? '\n' : '') + line.slice(5).trim();
    }
    let parsed = data;
    try { parsed = JSON.parse(data); } catch {}

    if (event === 'token') {
      const chunk = typeof parsed === 'string' ? parsed : (parsed.text || '');
      if (chunk) appendToAssistant(chunk);
    } else if (event === 'tool_use') {
      onToolUse(parsed);
    } else if (event === 'tool_result') {
      onToolResult(parsed);
    } else if (event === 'confirmation_required') {
      showConfirmDialog(parsed);
    } else if (event === 'error' || event === 'fatal') {
      finishAssistantWithError(parsed.message || String(parsed));
    } else if (event === 'done') {
      // wird in finalizeAssistant() ohnehin abgeschlossen
    }
  };

  const appendToAssistant = (chunk) => {
    state.currentAssistantText += chunk;
    if (state.currentAssistantEl) {
      state.currentAssistantEl.innerHTML = renderMarkdown(state.currentAssistantText)
        + '<span class="streaming-cursor"></span>';
      scrollToBottom();
    }
  };

  const onToolUse = (d) => {
    // Falls mitten in Assistant-Antwort ein Tool-Call kommt, Bubble vorerst belassen
    // (Claude setzt den Text später fort).
    const card = createToolCard(d.id, d.name, d.input);
    state.activeToolCards.set(d.id, card);
    // Tool-Card VOR der aktuellen Assistant-Bubble einfügen
    if (state.currentAssistantEl) {
      const parentMsg = state.currentAssistantEl.closest('.msg');
      $messages.insertBefore(card, parentMsg);
    } else {
      $messages.appendChild(card);
    }
    scrollToBottom();
  };

  const onToolResult = (d) => {
    const card = state.activeToolCards.get(d.tool_use_id);
    if (!card) return;
    card.classList.add('done');
    const spinner = card.querySelector('.tool-card-spinner');
    if (spinner) spinner.replaceWith(el('span', { class: 'tool-card-icon' }, '✓'));
    state.activeToolCards.delete(d.tool_use_id);
  };

  const finishAssistantWithError = (msg) => {
    if (state.currentAssistantEl) {
      state.currentAssistantEl.innerHTML =
        `<div style="color: var(--red); font-size: 13px;">⚠ ${escapeHtml(msg)}</div>`;
    }
  };

  const finalizeAssistant = () => {
    if (state.currentAssistantEl) {
      // Cursor entfernen, finaler HTML-State
      state.currentAssistantEl.innerHTML = renderMarkdown(state.currentAssistantText || '(keine Antwort)');
    }
    state.currentAssistantEl = null;
  };

  const setStreaming = (v) => {
    state.streaming = v;
    $sendBtn.disabled = v;
    $input.disabled = v;
  };

  // ── Confirmation-Dialog (Phase 4) ───────────────────
  const TOOL_LABELS = {
    'mcp__velora__log_trade': 'Trade loggen',
    'mcp__velora__update_watchlist': 'Watchlist ändern',
    'mcp__velora__close_recommendation': 'Empfehlung schließen',
  };

  const showConfirmDialog = (data) => {
    const label = TOOL_LABELS[data.tool_name] || 'Aktion bestätigen';
    const params = data.params || {};

    // Schöne Zusammenfassung abhängig vom Tool
    let detailRows = [];
    if (data.tool_name === 'mcp__velora__log_trade') {
      detailRows = [
        ['Aktion', params.action === 'buy' ? 'Kauf' : 'Verkauf'],
        ['Ticker', params.ticker],
        ['Stück', params.shares],
        ['Preis', params.price],
        ['Konto', params.account],
      ];
    } else if (data.tool_name === 'mcp__velora__update_watchlist') {
      detailRows = [
        ['Aktion', params.action === 'add' ? 'Hinzufügen' : 'Entfernen'],
        ['Ticker', params.ticker],
      ];
      if (params.name) detailRows.push(['Name', params.name]);
    } else if (data.tool_name === 'mcp__velora__close_recommendation') {
      detailRows = [
        ['Ticker', params.ticker],
        ['Outcome', params.outcome],
      ];
    }

    const detailTable = el('table', { style: 'width: 100%; border-collapse: collapse; font-size: 13px; margin: 10px 0;' });
    for (const [k, v] of detailRows) {
      if (v === undefined || v === null || v === '') continue;
      detailTable.appendChild(el('tr', {},
        el('td', { style: 'padding: 4px 8px; color: var(--text-muted); width: 90px;' }, k + ':'),
        el('td', { style: 'padding: 4px 8px; color: var(--text-primary); font-weight: 600;' }, String(v)),
      ));
    }

    let statusLine = null;
    let busy = false;

    const close = () => wrap.remove();

    const handle = async (approved) => {
      if (busy) return;
      busy = true;
      confirmBtn.disabled = cancelBtn.disabled = true;
      statusLine.textContent = approved ? 'Führe aus…' : 'Abbrechen…';

      let resp;
      try {
        resp = await fetch('/api/chat/confirm', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({ action_id: data.action_id, approved }),
        }).then(r => r.json());
      } catch (e) {
        statusLine.textContent = 'Netzwerkfehler: ' + e.message;
        busy = false;
        confirmBtn.disabled = cancelBtn.disabled = false;
        return;
      }

      // Resultat als kleine Tool-Result-Bubble in den Chat einfügen
      const msg = approved
        ? (resp.success ? `✓ ${resp.message || 'Erledigt'}` : `⚠ ${resp.message || 'Fehlgeschlagen'}`)
        : `✕ Aktion abgebrochen`;
      const resultColor = approved && resp.success ? 'var(--green)' : (approved ? 'var(--red)' : 'var(--text-muted)');
      const resultCard = el('div', {
        class: 'tool-card' + (approved && resp.success ? ' done' : (approved ? ' error' : '')),
        style: `border-left-color: ${resultColor};`,
      }, el('span', {}, msg));
      $messages.appendChild(resultCard);
      scrollToBottom();

      close();
    };

    const cancelBtn = el('button', { class: 'btn-cancel', onclick: () => handle(false) }, 'Abbrechen');
    const confirmBtn = el('button', { class: 'btn-confirm', onclick: () => handle(true) }, 'Ausführen');
    statusLine = el('div', { style: 'font-size: 11px; color: var(--text-muted); margin-top: 6px;' });

    const wrap = el('div', { class: 'chat-confirm-overlay', onclick: (e) => { if (e.target === wrap) close(); } },
      el('div', { class: 'chat-confirm-dialog' },
        el('div', { class: 'chat-confirm-title' }, label),
        el('div', { class: 'chat-confirm-body' },
          data.summary ? el('div', {}, data.summary) : null,
          detailRows.length ? detailTable : null,
          el('div', { style: 'font-size: 11px; color: var(--text-muted); margin-top: 8px;' },
            'Bestätigung dauerhaft in portfolio.json / watchlist.json / recommendations.json.'),
        ),
        el('div', { class: 'chat-confirm-actions' }, cancelBtn, confirmBtn),
        statusLine,
      ),
    );
    document.body.appendChild(wrap);
  };

  // ── Auto-resize Textarea ────────────────────────────
  const autoResize = () => {
    $input.style.height = 'auto';
    $input.style.height = Math.min($input.scrollHeight, 200) + 'px';
    $sendBtn.disabled = state.streaming || $input.value.trim().length === 0;
  };

  // ── Initialisierung ─────────────────────────────────
  const init = async () => {
    $threadList = document.getElementById('chat-thread-list');
    $messages = document.getElementById('chat-messages');
    $input = document.getElementById('chat-input');
    $sendBtn = document.getElementById('chat-send');
    $headerTitle = document.getElementById('chat-header-title');
    $pinToggle = document.getElementById('chat-pin-toggle');
    $deleteBtn = document.getElementById('chat-delete-btn');
    $search = document.getElementById('chat-search');
    $newBtn = document.getElementById('chat-new');
    $emptyState = document.getElementById('chat-empty');

    if (!$threadList) return; // nicht auf /chat-Seite

    $input.addEventListener('input', autoResize);
    $input.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
      }
    });
    $sendBtn.addEventListener('click', sendMessage);
    $newBtn.addEventListener('click', async () => {
      const t = await api.createThread('Neuer Chat');
      state.threads.unshift(t);
      await selectThread(t.id);
    });
    $search.addEventListener('input', renderThreadList);
    $pinToggle.addEventListener('click', async () => {
      if (!state.currentThreadId) return;
      const thread = state.threads.find(t => t.id === state.currentThreadId);
      const newState = !thread.is_pinned;
      await api.patchThread(state.currentThreadId, { is_pinned: newState });
      thread.is_pinned = newState ? 1 : 0;
      $pinToggle.classList.toggle('active', newState);
      $pinToggle.textContent = newState ? '★ Angeheftet' : '☆ Anheften';
      renderThreadList();
    });
    $deleteBtn.addEventListener('click', async () => {
      if (!state.currentThreadId) return;
      if (!confirm('Chat wirklich löschen?')) return;
      await api.deleteThread(state.currentThreadId);
      state.currentThreadId = null;
      await loadThreads();
      showEmptyState();
    });

    // Keyboard: Cmd/Ctrl+K → neuer Chat
    document.addEventListener('keydown', (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        $newBtn.click();
      }
    });

    await loadThreads();

    // Zuletzt genutzten Thread wieder öffnen, sonst Empty-State
    let openId = null;
    try {
      openId = localStorage.getItem('velora_last_thread');
    } catch {}
    const exists = state.threads.find(t => t.id === openId);
    if (exists) await selectThread(exists.id);
    else showEmptyState();

    autoResize();
    $input.focus();
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
