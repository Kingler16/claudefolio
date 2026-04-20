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
    activeToolCards: new Map(), // tool_use_id -> {item, startTs}
    abortController: null,
    pinnedIds: new Set(), // lokaler Cache für "gepinnt"-Badge
    currentToolPanel: null, // konsolidiertes Panel pro Assistant-Turn
    currentToolPanelStart: 0,
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

  // Code-Blocks in einer gerenderten Assistant-Bubble mit Header + Copy-Button + hljs
  // anreichern. Idempotent: markiert Elemente mit data-enhanced="1".
  const enhanceCodeBlocks = (root) => {
    if (!root) return;
    root.querySelectorAll('pre > code').forEach((code) => {
      const pre = code.parentElement;
      if (!pre || pre.dataset.enhanced === '1') return;
      pre.dataset.enhanced = '1';
      const langMatch = (code.className.match(/language-(\w+)/) || [,''])[1];
      if (typeof hljs !== 'undefined') {
        try { hljs.highlightElement(code); } catch (_) { /* noop */ }
      }
      const wrap = document.createElement('div');
      wrap.className = 'code-block';
      const header = document.createElement('div');
      header.className = 'code-block-header';
      header.innerHTML =
        '<span class="code-block-lang">' + (langMatch || 'code') + '</span>' +
        '<button class="code-block-copy" type="button">Kopieren</button>';
      pre.parentNode.insertBefore(wrap, pre);
      wrap.appendChild(header);
      wrap.appendChild(pre);
      const btn = header.querySelector('.code-block-copy');
      btn.addEventListener('click', () => {
        const txt = code.innerText;
        if (navigator.clipboard && navigator.clipboard.writeText) {
          navigator.clipboard.writeText(txt).then(() => {
            btn.textContent = 'Kopiert';
            setTimeout(() => { btn.textContent = 'Kopieren'; }, 1500);
          });
        } else {
          btn.textContent = 'Kopiert';
          setTimeout(() => { btn.textContent = 'Kopieren'; }, 1500);
        }
      });
    });
  };

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

  const I18N = (window.VELORA_I18N || {});
  const SUGGESTIONS = I18N.suggestions || [
    { label: 'Wie diversifiziert bin ich?', prompt: 'Wie diversifiziert bin ich? Gib mir eine ehrliche Einschätzung.' },
    { label: 'Top 5 analysieren',            prompt: 'Analysiere meine Top 5 Holdings.' },
    { label: 'Red Flags?',                   prompt: 'Gibt es Red Flags in meinem Portfolio?' },
    { label: 'Tax-Loss-Chancen',             prompt: 'Gibt es Tax-Loss-Harvesting-Chancen?' },
    { label: 'Sektor-Exposure',              prompt: 'Erkläre mein Sektor-Exposure.' },
    { label: 'Markt-Sentiment',              prompt: 'Wie ist das aktuelle Markt-Sentiment?' },
  ];
  const WELCOME_TITLE = I18N.welcome || 'Willkommen bei Velora';
  const WELCOME_SUB = I18N.welcome_sub || 'Frag alles zu deinem Portfolio, Markt-Sentiment oder Trade-Strategie.';

  const showEmptyState = () => {
    state.currentThreadId = null;
    $messages.innerHTML = '';
    $headerTitle.textContent = 'Velora';
    $pinToggle.textContent = '☆ Anheften';
    $pinToggle.classList.remove('active');
    renderEmpty($messages);
  };

  // Empty-State mit 2x3-Suggestion-Grid. Wird in leeres Messages-Panel
  // gerendert (wahlweise im Empty-State-Modus oder wenn Thread 0 Messages hat).
  const renderEmpty = (container) => {
    const wrap = el('div', { class: 'chat-empty-state' });
    wrap.innerHTML =
      '<h2>' + escapeHtml(WELCOME_TITLE) + '</h2>' +
      '<p>' + escapeHtml(WELCOME_SUB) + '</p>' +
      '<div class="suggestion-row suggestion-grid-2x3">' +
        SUGGESTIONS.map(s =>
          '<button class="suggestion" type="button" data-prompt="' + escapeHtml(s.prompt) + '">' +
          escapeHtml(s.label) + '</button>'
        ).join('') +
      '</div>';
    container.appendChild(wrap);
    wrap.querySelectorAll('.suggestion').forEach(b => {
      b.addEventListener('click', () => {
        const prompt = b.dataset.prompt || '';
        if (!state.currentThreadId) {
          startWithPrompt(prompt);
        } else {
          $input.value = prompt;
          autoResize();
          sendMessage();
        }
      });
    });
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
      renderEmpty($messages);
      return;
    }
    for (const msg of state.messages) renderMessage(msg);
    scrollToBottom();
  };

  const renderMessage = (msg) => {
    if (msg.role === 'user' || msg.role === 'assistant') {
      const bubble = el('div', { class: 'msg-bubble' });
      bubble.innerHTML = msg.role === 'assistant' ? renderMarkdown(msg.content) : escapeHtml(msg.content).replace(/\n/g, '<br>');
      if (msg.role === 'assistant') enhanceCodeBlocks(bubble);

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
        // Historische Tool-Calls: jeder als fertig-Item in ein gemeinsames Panel
        // anhängen, falls der unmittelbare Nachbar bereits ein Panel ist.
        let panel = $messages.lastElementChild;
        if (!panel || !panel.classList || !panel.classList.contains('tool-panel')) {
          panel = createToolPanelEl();
          $messages.appendChild(panel);
        }
        addToolItemToPanel(panel, { name: d.name || 'tool', status: 'done', duration: null });
        finalizeHistoricalPanelTitle(panel);
      } catch (_) { /* noop */ }
    }
  };

  // Erzeugt leeres Tool-Panel mit Header + Liste. Click-Handler toggelt open.
  const createToolPanelEl = () => {
    const panel = document.createElement('div');
    panel.className = 'tool-panel';
    panel.setAttribute('open', '');
    panel.innerHTML =
      '<div class="tool-panel-header">' +
        '<span class="tool-panel-chev">&#9662;</span>' +
        '<span class="tool-panel-title">Velora nutzt <strong>Tools</strong>&hellip;</span>' +
        '<span class="tool-panel-duration tabular-nums">&hellip;</span>' +
      '</div>' +
      '<ul class="tool-panel-list"></ul>';
    const header = panel.querySelector('.tool-panel-header');
    header.addEventListener('click', () => {
      if (panel.hasAttribute('open')) panel.removeAttribute('open');
      else panel.setAttribute('open', '');
    });
    return panel;
  };

  // Fügt einen Item-Eintrag in das Panel ein und gibt das <li> zurück.
  const addToolItemToPanel = (panel, { name, status, duration }) => {
    const list = panel.querySelector('.tool-panel-list');
    const li = document.createElement('li');
    li.className = 'tool-panel-item ' + (status || 'running');
    const icon = status === 'done' ? '\u2713' : status === 'error' ? '\u00d7' : '\u2026';
    li.innerHTML =
      '<span class="tool-panel-icon">' + icon + '</span>' +
      '<span class="tool-panel-name">' + escapeHtml(name || '') + '</span>' +
      '<span class="tool-panel-time tabular-nums">' +
        (duration != null ? duration.toFixed(1) + 's' : '') +
      '</span>';
    list.appendChild(li);
    return li;
  };

  // Titel auf Basis der enthaltenen Items aktualisieren (historisch/live finalize).
  const finalizeHistoricalPanelTitle = (panel) => {
    const items = panel.querySelectorAll('.tool-panel-item');
    const hasError = Array.from(items).some(i => i.classList.contains('error'));
    panel.classList.add(hasError ? 'has-error' : 'all-done');
    const title = panel.querySelector('.tool-panel-title');
    const n = items.length;
    title.innerHTML = 'Velora hat <strong>' + n + ' Tool' + (n === 1 ? '' : 's') + '</strong> genutzt';
    const dur = panel.querySelector('.tool-panel-duration');
    if (dur) dur.textContent = '';
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
    state.currentToolPanel = null; // neues Turn-Panel bei Bedarf
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

  // Live-Streaming: alle Tool-Calls eines Assistant-Turns landen in einem
  // konsolidierten Panel vor der aktuellen Assistant-Bubble.
  const ensureLiveToolPanel = () => {
    if (state.currentToolPanel && state.currentToolPanel.isConnected) return state.currentToolPanel;
    const panel = createToolPanelEl();
    state.currentToolPanel = panel;
    state.currentToolPanelStart = performance.now();
    if (state.currentAssistantEl) {
      const parentMsg = state.currentAssistantEl.closest('.msg');
      if (parentMsg && parentMsg.parentNode === $messages) {
        $messages.insertBefore(panel, parentMsg);
      } else {
        $messages.appendChild(panel);
      }
    } else {
      $messages.appendChild(panel);
    }
    return panel;
  };

  const onToolUse = (d) => {
    const panel = ensureLiveToolPanel();
    const item = addToolItemToPanel(panel, { name: d.name, status: 'running', duration: null });
    state.activeToolCards.set(d.id, { item, startTs: performance.now() });
    scrollToBottom();
  };

  const onToolResult = (d) => {
    const rec = state.activeToolCards.get(d.tool_use_id);
    if (!rec) return;
    const { item, startTs } = rec;
    const duration = (performance.now() - startTs) / 1000;
    item.classList.remove('running');
    const isError = d.is_error === true || d.error === true;
    item.classList.add(isError ? 'error' : 'done');
    const icon = item.querySelector('.tool-panel-icon');
    if (icon) icon.textContent = isError ? '\u00d7' : '\u2713';
    const t = item.querySelector('.tool-panel-time');
    if (t) t.textContent = duration.toFixed(1) + 's';
    state.activeToolCards.delete(d.tool_use_id);
  };

  const finalizeToolPanel = () => {
    const panel = state.currentToolPanel;
    if (!panel || !panel.isConnected) { state.currentToolPanel = null; return; }
    const items = panel.querySelectorAll('.tool-panel-item');
    // Falls Tools noch "running" sind (z.B. Stream-Abbruch), sauber abhaken.
    items.forEach(li => {
      if (li.classList.contains('running')) {
        li.classList.remove('running');
        li.classList.add('done');
        const icon = li.querySelector('.tool-panel-icon');
        if (icon) icon.textContent = '\u2713';
      }
    });
    const hasError = Array.from(items).some(i => i.classList.contains('error'));
    panel.classList.add(hasError ? 'has-error' : 'all-done');
    const title = panel.querySelector('.tool-panel-title');
    const n = items.length;
    if (title) title.innerHTML = 'Velora hat <strong>' + n + ' Tool' + (n === 1 ? '' : 's') + '</strong> genutzt';
    const totalSec = (performance.now() - state.currentToolPanelStart) / 1000;
    const dur = panel.querySelector('.tool-panel-duration');
    if (dur) dur.textContent = totalSec.toFixed(1) + 's';
    state.currentToolPanel = null;
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
      enhanceCodeBlocks(state.currentAssistantEl);
    }
    state.currentAssistantEl = null;
    finalizeToolPanel();
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
