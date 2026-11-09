/* Ramus interactive prototype. Local, deterministic state; no backend or model calls. */
(function () {
  'use strict';
  const M = window.RamusModel;
  const P = window.RamusPanels;
  const STORAGE = 'ramus-first-purchase-demo-v1';
  const PEOPLE = {
    mason: { name: 'Mason', initials: 'M', role: 'Coupon policy' },
    hayden: { name: 'Hayden', initials: 'H', role: 'Cart experience' },
    jenny: { name: 'Jenny', initials: 'J', role: 'Checkout flow' },
    ai: { name: 'Ramus AI', initials: '', role: 'Shared context' },
  };
  const PATHS = {
    branch: '<path d="M7 3v12a4 4 0 0 0 4 4h6M7 7h6a4 4 0 0 0 4-4"/><circle cx="7" cy="3" r="2"/><circle cx="17" cy="3" r="2"/><circle cx="17" cy="19" r="2"/>',
    chat: '<path d="M21 11.5a8.5 8.5 0 0 1-8.5 8.5H4l-2 2V11.5a9.5 9.5 0 0 1 19 0Z"/><path d="M7 9h9M7 13h6"/>',
    file: '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8Z"/><path d="M14 2v6h6M8 13h8M8 17h5"/>',
    spark: '<path d="m12 3 2.4 6.6L21 12l-6.6 2.4L12 21l-2.4-6.6L3 12l6.6-2.4Z"/>',
    arrow: '<path d="M4 12h16m-6-6 6 6-6 6"/>',
    send: '<path d="m21 3-7 18-4-7-7-4Z"/><path d="m10 14 11-11"/>',
    check: '<path d="m5 12 4 4L19 6"/>',
    chevron: '<path d="m9 5 7 7-7 7"/>',
    down: '<path d="m6 9 6 6 6-6"/>',
    search: '<circle cx="10.5" cy="10.5" r="7"/><path d="m16 16 5 5"/>',
    graph: '<rect x="9" y="2" width="6" height="5" rx="1"/><rect x="2" y="17" width="6" height="5" rx="1"/><rect x="16" y="17" width="6" height="5" rx="1"/><path d="M12 7v5M5 17v-5h14v5"/>',
    play: '<path d="m8 4 13 8-13 8Z"/>',
    pause: '<path d="M8 4v16M16 4v16"/>',
    reset: '<path d="M3 10a9 9 0 1 1 1 7M3 3v7h7"/>',
    close: '<path d="m6 6 12 12M6 18 18 6"/>',
    users: '<circle cx="9" cy="7" r="4"/><path d="M2 21v-2a7 7 0 0 1 14 0v2M17 3a4 4 0 0 1 0 8M22 21v-2a7 7 0 0 0-4-6"/>',
    link: '<path d="m10 13 4-4M8 16l-2 2a4 4 0 0 1-6-6l5-5a4 4 0 0 1 6 0M16 8l2-2a4 4 0 0 1 6 6l-5 5a4 4 0 0 1-6 0" transform="translate(1 0) scale(.9)"/>',
    clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
    info: '<circle cx="12" cy="12" r="9"/><path d="M12 11v6M12 7h.01"/>',
    menu: '<path d="M4 6h16M4 12h16M4 18h16"/>',
    more: '<circle cx="5" cy="12" r="1"/><circle cx="12" cy="12" r="1"/><circle cx="19" cy="12" r="1"/>',
  };
  const icon = (name) => `<svg class="icon" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${PATHS[name] || PATHS.file}</svg>`;
  const esc = (value) => String(value ?? '').replace(/[&<>"']/g, (char) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[char]);
  const formatText = (value) => esc(value).replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>').replace(/\n/g, '<br>');
  let state = M.createInitialState();
  let drafts = {};
  let autoplay = null;
  let aiPending = {};
  let taskTimers = [];
  let epoch = 0;
  let toastTimer;
  let modalOpener;
  let lastPanelType = null;
  try {
    const saved = JSON.parse(localStorage.getItem(STORAGE) || 'null');
    if (saved?.state?.schemaVersion === 1 && saved.state.conversations?.planning && Array.isArray(saved.state.tasks) && saved.state.convention?.versions) {
      state = saved.state;
      state.panel = null;
      drafts = saved.drafts && typeof saved.drafts === 'object' ? saved.drafts : {};
    }
  } catch (_) { /* Storage is optional, including file:// and private browsing. */ }

  const app = document.getElementById('app');
  const modalLayer = document.getElementById('modal-layer');
  const demoBar = document.getElementById('demo-bar');
  const person = (id) => PEOPLE[id] || { name: id || 'Team member', initials: String(id || 'T')[0] };
  const avatar = (id, small = false) => `<span class="avatar ${esc(id)} ${small ? 'small' : ''}" aria-hidden="true">${id === 'ai' ? icon('spark') : esc(person(id).initials)}</span>`;
  const button = (action, label, variant = 'secondary', attrs = '') => `<button class="btn ${variant}" data-action="${action}" ${attrs}>${label}</button>`;
  const openPanel = (type, sourceId) => dispatch({ type: 'SET_PANEL', panel: { type, ...(sourceId ? { sourceId } : {}) } });

  function persist() {
    try { localStorage.setItem(STORAGE, JSON.stringify({ state: { ...state, panel: null }, drafts })); } catch (_) { /* Full/blocked storage does not prevent the demo. */ }
  }
  function toast(text) {
    const target = document.getElementById('toast');
    target.textContent = text;
    target.classList.add('toast-visible');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => target.classList.remove('toast-visible'), 3200);
  }
  function dispatch(intent) {
    state = M.reduce(state, intent);
    persist();
    render();
  }
  function stopPlayback() {
    clearInterval(autoplay);
    autoplay = null;
  }
  function cancelTimers() {
    epoch++;
    taskTimers.forEach(clearTimeout);
    taskTimers = [];
    aiPending = {};
  }
  function jump(index) {
    cancelTimers();
    dispatch({ type: 'SCENE', index: Math.max(0, Math.min(8, index)) });
    document.body.classList.remove('show-sidebar', 'show-inspector');
  }
  function reset() {
    stopPlayback();
    cancelTimers();
    drafts = {};
    dispatch({ type: 'RESET' });
    toast('Demo reset. Your team is ready to begin.');
  }

  function render() {
    const focused = document.activeElement;
    const focusId = focused?.id;
    const selection = focused instanceof HTMLTextAreaElement ? [focused.selectionStart, focused.selectionEnd] : null;
    const oldMessages = document.querySelector('.messages');
    const oldScroll = oldMessages?.scrollTop || 0;
    const atBottom = !oldMessages || oldMessages.scrollHeight - oldMessages.scrollTop - oldMessages.clientHeight < 90;
    const conversation = state.conversations[state.active];
    const ready = state.tasks.filter((task) => state.results[task.id]).length;
    app.innerHTML = `
      <header class="topbar">
        <button class="brand btn ghost" data-action="open-panel" data-panel="intro" aria-label="About Ramus"><span class="brand-mark">${icon('branch')}</span><span>ramus</span></button>
        <div class="breadcrumb"><span>Commerce team</span>${icon('chevron')}<strong>First purchase</strong></div>
        <div class="top-actions"><span class="prototype-label"><span class="presence-dot"></span>Interactive prototype</span>${button('open-panel', `${icon('graph')} Project map`, 'ghost small', 'data-panel="graph"')}${button('open-panel', `${icon('info')} The story`, 'ghost small', 'data-panel="before"')}<div class="team-avatars" aria-label="Mason, Hayden and Jenny are in this workspace">${avatar('mason', true)}${avatar('hayden', true)}${avatar('jenny', true)}</div></div>
      </header>
      <div class="workspace">
        <aside class="sidebar" aria-label="Workspace navigation">
          <div class="project-card"><span class="project-symbol">${icon('branch')}</span><div><strong>First purchase</strong><span>Commerce workspace</span></div></div>
          <div class="sidebar-goal"><span class="nav-label">Our shared goal</span><p>Make the first purchase feel effortless.</p><div class="progress-track"><span class="progress-fill" style="width:${state.goalComplete ? 100 : ready ? 25 + ready * 20 : state.branched ? 28 : state.convention.latest ? 16 : 5}%"></span></div><span class="goal-subtext">${state.goalComplete ? 'Purchase flow connected' : `${ready} of 3 outcomes reviewed`}</span></div>
          <span class="nav-label">Conversations</span>
          <button class="nav-item ${state.active === 'planning' ? 'active' : ''}" data-action="navigate" data-id="planning">${icon('chat')}<span>Shared planning</span>${state.convention.latest ? '<span class="nav-dot"></span>' : ''}</button>
          ${state.branched ? `<div class="nav-children">${['coupons', 'cart', 'checkout'].map((id) => `<button class="nav-item ${state.active === id ? 'active' : ''}" data-action="navigate" data-id="${id}">${icon('branch')}<span>${esc(state.conversations[id].title)}</span>${state.results[id] ? icon('check') : '<span class="nav-dot muted"></span>'}</button>`).join('')}</div>` : '<p class="sidebar-hint">Branch the work when your team is ready.</p>'}
          <div class="sidebar-divider"></div><span class="nav-label">Workspace</span>
          <button class="nav-item" data-action="open-panel" data-panel="resources">${icon('file')}<span>Shared conventions</span>${state.convention.latest ? `<span class="count">${state.convention.latest}</span>` : ''}</button>
          <button class="nav-item" data-action="open-panel" data-panel="graph">${icon('graph')}<span>Project map</span></button>
          <button class="nav-item" data-action="open-results">${icon('link')}<span>Reviewed results</span><span class="count">${Object.keys(state.results).length}</span></button>
          <div class="sidebar-bottom"><label class="person-switch">${avatar(state.user)}<span><strong>Presenting as</strong><select id="demo-person" aria-label="Present as a team member">${['mason', 'hayden', 'jenny'].map((id) => `<option value="${id}" ${state.user === id ? 'selected' : ''}>${person(id).name}</option>`).join('')}</select></span>${icon('down')}</label><span class="local-note">Local demo · no account needed</span></div>
        </aside>
        <main class="conversation" aria-label="${esc(conversation.title)} conversation">
          <div class="goal-strip">${icon(state.goalComplete ? 'check' : 'branch')}<span>${state.goalComplete ? 'A shared goal. Three connected outcomes.' : 'Team goal: design a clear first-purchase experience'}</span><button class="icon-btn mobile-nav" data-action="toggle-sidebar" aria-label="Toggle conversations">${icon('menu')}</button><button class="icon-btn mobile-nav" data-action="toggle-inspector" aria-label="Toggle task panel">${icon('more')}</button></div>
          <header class="conversation-header"><div><div class="conversation-eyebrow">${state.active === 'planning' ? 'The starting point for every branch' : `Branched from Shared planning · ${person(conversation.owner).name}`}</div><h1 class="conversation-title">${esc(conversation.title)}</h1></div>${state.active === 'planning' ? button('branch', `${icon('branch')} Branch work`, 'secondary small') : button('open-task', `${icon('file')} Open task`, 'secondary small', `data-id="${state.active}"`)}</header>
          <div class="context-row">${conventionPill(conversation)}${conversation.inputs.map((input) => `<button class="pill purple" data-action="open-panel" data-panel="result" data-source="${esc(input.sourceId)}">${icon('link')}${esc(input.title)} v${input.version}</button>`).join('')}${!conversation.appliedVersion ? '<span class="context-hint">Shared context travels with your work.</span>' : ''}</div>
          <div class="messages" id="messages" role="log" aria-label="Conversation messages">${conversation.messages.map((message) => renderMessage(message, state.active)).join('')}${aiPending[state.active] ? `<div class="message ai">${avatar('ai')}<div class="message-main"><div class="message-meta"><strong>Ramus AI</strong><span>Working with your shared context</span></div><div class="typing" role="status" aria-label="AI is preparing a response"><i></i><i></i><i></i></div></div></div>` : ''}<div class="message-end"></div></div>
          ${renderComposer(state.active)}
        </main>
        ${renderInspector()}
      </div>`;
    renderDemoBar();
    if (state.panel?.type === 'task') modalLayer.innerHTML = renderTaskModal();
    else if (state.panel?.type === 'library') modalLayer.innerHTML = renderLibrary();
    else modalLayer.innerHTML = P.renderPanel({ ...state,
      conventionDraft: drafts[`convention:${state.convention.latest + 1}`],
      resultDrafts: Object.fromEntries(['coupons', 'cart', 'checkout'].filter((id) => typeof drafts[`result:${id}`] === 'string').map((id) => [id, drafts[`result:${id}`]])),
    }) || '';
    const panelKey = state.panel ? `${state.panel.type}:${state.panel.sourceId || ''}:${state.panel.tab || ''}` : null;
    if (panelKey && panelKey !== lastPanelType) {
      if (!lastPanelType) modalOpener = focused;
      requestAnimationFrame(() => modalLayer.querySelector('button, input, textarea, [tabindex="0"]')?.focus({ preventScroll: true }));
    } else if (!panelKey && lastPanelType && modalOpener?.isConnected) modalOpener.focus({ preventScroll: true });
    lastPanelType = panelKey;
    if (focusId && document.getElementById(focusId) && panelKey === null) {
      const replacement = document.getElementById(focusId);
      replacement.focus({ preventScroll: true });
      if (selection && replacement.setSelectionRange) replacement.setSelectionRange(...selection);
    }
    const messages = document.getElementById('messages');
    if (messages) messages.scrollTop = atBottom ? messages.scrollHeight : oldScroll;
    app.inert = Boolean(state.panel);
  }

  function conventionPill(conversation) {
    const applied = conversation.appliedVersion;
    if (!applied) return button('open-panel', `${icon('file')} Add shared convention`, 'ghost small', 'data-panel="convention-edit"');
    return `<button class="pill teal" data-action="open-panel" data-panel="resources">${icon('file')}Service convention v${applied}</button>${state.convention.latest > applied ? `<button class="pill amber" data-action="open-panel" data-panel="resources">v${state.convention.latest} available ${icon('arrow')}</button>` : ''}`;
  }

  function renderMessage(message, conversationId) {
    const ai = message.author === 'ai';
    const result = state.results[conversationId];
    return `<article class="message ${ai ? 'ai' : ''}">${avatar(message.author)}<div class="message-main"><div class="message-meta"><strong>${esc(person(message.author).name)}</strong>${ai ? '<span class="ai-label">AI</span>' : ''}<time>${ai ? 'Just now' : 'Today'}</time></div><div class="message-body ${ai ? 'ai-card' : ''}">${formatText(message.text)}</div>${ai ? `<div class="message-actions">${conversationId === 'planning' ? button('open-panel', `${icon('file')} ${state.convention.latest ? 'View shared convention' : 'Save as shared convention'}`, 'ghost small', `data-panel="${state.convention.latest ? 'resources' : 'convention-edit'}"`) : button('open-panel', `${icon('file')} ${result ? 'View reviewed result' : 'Review & save result'}`, 'ghost small', `data-panel="result" data-source="${conversationId}"`)}<span class="context-used">${icon('check')}${state.conversations[conversationId].appliedVersion ? `Convention v${state.conversations[conversationId].appliedVersion}` : 'Team discussion'}${state.conversations[conversationId].inputs.length ? ` + ${state.conversations[conversationId].inputs.length} linked result` : ''}</span></div>` : ''}</div></article>`;
  }

  function suggestions(id) {
    if (id === 'planning') return [state.convention.latest ? 'Divide coupon, cart, and checkout work' : 'Compare how other stores explain benefits and extra costs'];
    if (id === 'coupons') return ['@AI Review coupon conditions and edge cases.'];
    if (id === 'cart') return [state.conversations.cart.inputs.length ? state.conversations.cart.appliedVersion >= 2 ? '@AI Update the cart with shipping included in the estimated total.' : '@AI Use the received coupon policy to finalize the price breakdown.' : '@AI Draft the cart layout and flag any missing policy decisions.'];
    return ['@AI Use the coupon policy and cart result to design the order review screen.'];
  }
  function renderComposer(id, modal = false) {
    const key = modal ? `task-${id}` : id;
    return `<div class="composer-wrap ${modal ? 'modal-composer' : ''}"><div class="suggestions">${suggestions(id).map((text) => button('suggest', `${icon('spark')}${esc(text)}`, 'suggestion', `data-id="${id}" data-text="${esc(text)}" ${modal ? 'data-modal="true"' : ''}`)).join('')}</div><form class="composer" data-conversation="${id}" data-draft="${key}"><label class="sr-only" for="composer-${key}">Message ${esc(state.conversations[id].title)}</label><textarea id="composer-${key}" rows="2" placeholder="Message your team, or mention @AI…" data-draft="${key}">${esc(drafts[key] || '')}</textarea><div class="composer-footer"><span>${icon('spark')}<strong>@AI</strong> works with this conversation’s context</span><button class="icon-btn send-button" type="submit" aria-label="Send message" ${aiPending[id] ? 'disabled' : ''}>${icon('send')}</button></div></form><p class="composer-note">Enter to send · Shift + Enter for a new line</p></div>`;
  }

  function renderInspector() {
    const inputs = state.conversations[state.active].inputs;
    return `<aside class="inspector" aria-label="AI tasks and shared context"><section><div class="section-header"><h2>AI tasks</h2><span class="count">${state.tasks.length}</span></div>${state.tasks.length ? state.tasks.map((task) => `<button class="task-card ${task.status}" data-action="open-task" data-id="${esc(task.id)}"><span class="task-card-top">${icon(state.results[task.id] ? 'check' : task.status === 'ready' ? 'file' : 'clock')}<span class="status ${task.status}">${state.results[task.id] ? 'Reviewed' : task.status === 'ready' ? 'Ready to review' : 'In progress'}</span>${icon('chevron')}</span><strong>${esc(task.title)}</strong><span class="task-owner">${avatar(task.owner, true)}${esc(person(task.owner).name)}<span>Convention v${state.conversations[task.id].appliedVersion}</span></span></button>`).join('') : `<div class="empty-state"><div class="empty-icon">${icon('branch')}</div><strong>Good work starts together.</strong><p>Agree on a shared convention, then let AI take on the parallel work.</p>${button('branch', 'Divide the work', 'secondary small')}</div>`}</section><section><div class="section-header"><h2>Received results</h2><span class="count">${inputs.length}</span></div>${inputs.length ? inputs.map((input) => `<button class="result-card" data-action="open-panel" data-panel="result" data-source="${esc(input.sourceId)}">${icon('link')}<span><strong>${esc(input.title)}</strong><small>Version ${input.version} · linked to AI input</small></span>${icon('chevron')}</button>`).join('') : '<div class="empty-inline">Reviewed results sent here will become context for your next AI request.</div>'}</section><section><div class="section-header"><h2>Shared convention</h2>${state.convention.latest ? `<span class="version-label">v${state.convention.latest}</span>` : ''}</div><button class="resource-card" data-action="open-panel" data-panel="resources">${icon('file')}<strong>Our store’s service convention</strong><p>One shared standard. Every branch starts with the same context.</p><span class="text-link">${state.convention.latest ? 'View convention & versions' : 'Create the first version'} ${icon('arrow')}</span></button></section>${state.activity.length ? `<section><div class="section-header"><h2>Workspace activity</h2></div><div class="timeline">${state.activity.slice(-3).reverse().map((item) => `<div class="timeline-item"><span></span><p>${esc(typeof item === 'string' ? item : item.text)}</p></div>`).join('')}</div></section>` : ''}</aside>`;
  }

  function renderTaskModal() {
    const id = state.panel.sourceId || 'coupons';
    const conversation = state.conversations[id];
    const task = state.tasks.find((item) => item.id === id);
    if (!conversation) return '';
    const tab = state.panel.tab || 'conversation';
    const result = state.results[id];
    return `<div class="modal-backdrop"><section class="modal task-modal wide" role="dialog" aria-modal="true" aria-labelledby="modal-title"><header class="modal-header"><div><span class="modal-kicker">${icon('branch')}Shared planning / AI task</span><h2 id="modal-title">${esc(conversation.title)}</h2></div><button class="icon-btn" data-action="close-panel" aria-label="Close task">${icon('close')}</button></header><div class="task-modal-context">${avatar(conversation.owner, true)}<span>${person(conversation.owner).name}</span><span class="status ${task?.status || 'ready'}">${task?.status === 'running' ? 'In progress' : result ? 'Reviewed' : 'Ready to review'}</span>${conventionPill(conversation)}</div><div class="modal-tabs"><button class="modal-tab ${tab === 'conversation' ? 'active' : ''}" data-action="task-tab" data-tab="conversation">Conversation</button><button class="modal-tab ${tab === 'result' ? 'active' : ''}" data-action="task-tab" data-tab="result">Result ${result ? `<span class="count">v${result.version}</span>` : ''}</button></div><div class="modal-body">${tab === 'conversation' ? `<div class="task-messages">${conversation.messages.map((message) => renderMessage(message, id)).join('')}</div>${renderComposer(id, true)}` : `<div class="document-meta"><span>Human-reviewed outcome</span>${result ? `<span>Version ${result.version}</span>` : ''}</div><h3>${esc(result?.title || `${conversation.title} result`)}</h3><div class="result-document">${formatText(result?.body || M.RESULT_COPY?.[id] || conversation.messages.filter((message) => message.author === 'ai').at(-1)?.text || 'Review the task conversation, then save a result for your team.')}</div><div class="notice teal">${icon('info')}Saving a result makes it available to other conversations. AI completion alone does not approve it.</div>`}</div><footer class="modal-footer"><span class="footer-hint">Closing this task keeps the parent conversation in place.</span>${result ? button('open-panel', `${icon('send')} Send to another conversation`, 'primary', `data-panel="share" data-source="${id}"`) : button('open-panel', 'Review & save result', 'primary', `data-panel="result" data-source="${id}"`)}</footer></section></div>`;
  }

  function renderLibrary() {
    return `<div class="modal-backdrop"><section class="modal" role="dialog" aria-modal="true" aria-labelledby="modal-title"><header class="modal-header"><div><h2 id="modal-title">Reviewed results</h2><p>Decisions your team can build on.</p></div><button class="btn ghost" data-action="close-panel">Close</button></header><div class="modal-body">${Object.keys(state.results).length ? Object.entries(state.results).map(([id, result]) => `<button class="result-card" data-action="open-panel" data-panel="result" data-source="${id}">${icon('file')}<span><strong>${esc(result.title)}</strong><small>Saved version ${result.version} · ${esc(state.conversations[id].title)}</small></span>${icon('chevron')}</button>`).join('') : '<div class="empty-state"><strong>No reviewed results yet</strong><p>Open an AI task, review its conclusion, and save it for your team.</p></div>'}</div><footer class="modal-footer"><span class="footer-hint">Opening a result never runs AI or changes a conversation’s inputs.</span></footer></section></div>`;
  }

  function renderDemoBar() {
    const scene = M.scenes[state.scene] || M.scenes[0];
    demoBar.innerHTML = `<div class="demo-caption"><span class="demo-step">${String(state.scene + 1).padStart(2, '0')} / 09</span><div><strong>${esc(scene.title)}</strong><span>${esc(scene.description)}</span></div></div><div class="demo-progress" aria-label="Story chapters">${M.scenes.map((item, index) => `<button class="step-dot ${state.scene === index ? 'active' : index < state.scene ? 'done' : ''}" data-action="scene" data-index="${index}" aria-label="Scene ${index + 1}: ${esc(item.title)}" ${state.scene === index ? 'aria-current="step"' : ''}></button>`).join('')}</div><div class="demo-controls"><button class="icon-btn" data-action="reset" aria-label="Reset demo" title="Reset demo">${icon('reset')}</button><button class="icon-btn" data-action="autoplay" aria-label="${autoplay ? 'Pause' : 'Play'} guided demo" title="${autoplay ? 'Pause' : 'Play'} guided demo">${icon(autoplay ? 'pause' : 'play')}</button><button class="btn secondary small" data-action="previous" ${state.scene === 0 ? 'disabled' : ''}>Back</button><button class="btn primary small" data-action="next">${state.scene === 8 ? 'Replay story' : 'Next scene'}${icon('arrow')}</button></div>`;
  }

  function branch() {
    if (!state.convention.latest) { openPanel('convention-edit'); toast('Save a shared convention before branching the work.'); return; }
    if (state.branched) { openPanel('graph'); return; }
    dispatch({ type: 'BRANCH' });
    toast('Three parallel tasks created. Each inherits the exact convention version.');
    const current = epoch;
    ['coupons', 'cart', 'checkout'].forEach((id, index) => taskTimers.push(setTimeout(() => {
      if (current !== epoch) return;
      dispatch({ type: 'AI_REPLY', conversationId: id });
      dispatch({ type: 'COMPLETE_TASK', conversationId: id });
      toast(`${state.conversations[id].title} is ready to review.`);
    }, 1800 + index * 1200)));
  }
  function sendMessage(conversationId, text, draftKey) {
    if (!text.trim() || aiPending[conversationId]) return;
    if (draftKey) drafts[draftKey] = '';
    dispatch({ type: 'POST_MESSAGE', conversationId, text: text.trim(), user: state.user });
    if (/@ai\b/i.test(text)) {
      aiPending[conversationId] = true;
      render();
      const current = epoch;
      taskTimers.push(setTimeout(() => {
        if (current !== epoch) return;
        delete aiPending[conversationId];
        dispatch({ type: 'AI_REPLY', conversationId });
      }, 950));
    }
  }

  document.addEventListener('click', (event) => {
    if (event.target.classList.contains('modal-backdrop')) { dispatch({ type: 'SET_PANEL', panel: null }); return; }
    const target = event.target.closest('[data-action]');
    if (!target || target.disabled) return;
    if (target.type === 'submit' && target.form) return;
    event.preventDefault();
    const { action, id, panel, source, target: targetId, version, index, text, modal } = target.dataset;
    if (action !== 'autoplay') stopPlayback();
    switch (action) {
      case 'navigate': dispatch({ type: 'NAVIGATE', id }); dispatch({ type: 'SET_PANEL', panel: null }); document.body.classList.remove('show-sidebar'); break;
      case 'open-panel': openPanel(panel, source); break;
      case 'close-panel': case 'begin-demo': dispatch({ type: 'SET_PANEL', panel: null }); break;
      case 'branch': branch(); break;
      case 'open-task': openPanel('task', id); break;
      case 'task-tab': dispatch({ type: 'SET_PANEL', panel: { ...state.panel, tab: target.dataset.tab } }); break;
      case 'suggest': {
        if (state.active === 'planning' && state.convention.latest) { branch(); break; }
        sendMessage(id, /^@AI/i.test(text) ? text : `@AI ${text}`, modal ? `task-${id}` : id);
        break;
      }
      case 'apply-convention': dispatch({ type: 'APPLY_CONVENTION', conversationId: targetId || state.active, version: Number(version) }); toast(`Convention v${version} applied. Other conversations keep their current version.`); break;
      case 'save-convention': saveConvention(target.closest('.modal')?.querySelector('[name="convention"]')?.value); break;
      case 'save-result': saveResult(source || state.active, target.closest('.modal')?.querySelector('[name="result"]')?.value); break;
      case 'share-result': shareResult(source, target.closest('.modal')?.querySelector('[name="share-target"]:checked')?.value || target.closest('.modal')?.querySelector('select[name="share-target"]')?.value || targetId); break;
      case 'scene': jump(Number(index)); break;
      case 'next': if (state.scene === 8) reset(); else jump(state.scene + 1); break;
      case 'previous': jump(state.scene - 1); break;
      case 'reset': reset(); break;
      case 'autoplay':
        if (autoplay) stopPlayback();
        else { if (state.scene === 8) jump(0); autoplay = setInterval(() => { if (state.scene >= 8) { stopPlayback(); renderDemoBar(); } else jump(state.scene + 1); }, 6500); }
        renderDemoBar(); break;
      case 'open-results': openPanel('library'); break;
      case 'toggle-sidebar': document.body.classList.toggle('show-sidebar'); break;
      case 'toggle-inspector': document.body.classList.toggle('show-inspector'); break;
      default: break;
    }
    if (!['autoplay'].includes(action)) renderDemoBar();
  });

  function saveConvention(body) {
    if (!body?.trim()) { toast('Add a convention before saving.'); return; }
    delete drafts[`convention:${state.convention.latest + 1}`];
    dispatch({ type: 'SAVE_CONVENTION', body: body.trim() });
    dispatch({ type: 'SET_PANEL', panel: { type: 'resources' } });
    toast(`Convention v${state.convention.latest} saved. Existing branches keep their pinned version.`);
  }
  function saveResult(sourceId, body) {
    if (!body?.trim()) { toast('Add a conclusion before saving.'); return; }
    const inputs = state.conversations[sourceId]?.inputs || [];
    if ((sourceId === 'cart' && !inputs.some((input) => input.sourceId === 'coupons')) || (sourceId === 'checkout' && !['coupons', 'cart'].every((source) => inputs.some((input) => input.sourceId === source)))) {
      toast('Connect the required reviewed results before finalizing this outcome.'); return;
    }
    if (!state.conversations[sourceId] || sourceId === 'planning') return;
    delete drafts[`result:${sourceId}`];
    dispatch({ type: 'SAVE_RESULT', conversationId: sourceId, body: body.trim() });
    dispatch({ type: 'SET_PANEL', panel: { type: 'result', sourceId } });
    toast(`${state.results[sourceId].title} v${state.results[sourceId].version} saved for your team.`);
  }
  function shareResult(sourceId, targetId) {
    if (!sourceId || !targetId || sourceId === targetId || !state.results[sourceId]) { toast('Choose another conversation for this saved result.'); return; }
    dispatch({ type: 'SHARE_RESULT', sourceId, targetId });
    dispatch({ type: 'SET_PANEL', panel: { type: 'result', sourceId } });
    toast(`Sent to ${state.conversations[targetId].title}. It will be used in the next AI request.`);
  }
  document.addEventListener('submit', (event) => {
    const form = event.target;
    if (!(form instanceof HTMLFormElement)) return;
    event.preventDefault();
    if (form.classList.contains('composer')) {
      sendMessage(form.dataset.conversation, form.querySelector('textarea').value, form.dataset.draft);
      return;
    }
    const action = form.dataset.action || event.submitter?.dataset.action;
    const values = new FormData(form);
    if (action === 'save-convention') saveConvention(String(values.get('convention') || ''));
    if (action === 'save-result') saveResult(form.dataset.source || event.submitter?.dataset.source || state.panel?.sourceId || state.active, String(values.get('result') || ''));
    if (action === 'share-result') shareResult(form.dataset.source || state.panel?.sourceId, String(values.get('share-target') || ''));
  });
  document.addEventListener('input', (event) => {
    const target = event.target;
    if (target.dataset?.draft) { drafts[target.dataset.draft] = target.value; persist(); }
    if (target.name === 'convention') { drafts[`convention:${state.convention.latest + 1}`] = target.value; persist(); }
    if (target.name === 'result') { drafts[`result:${target.dataset.source || state.panel?.sourceId || state.active}`] = target.value; persist(); }
  });
  document.addEventListener('change', (event) => {
    if (event.target.id === 'demo-person') { dispatch({ type: 'SET_USER', user: event.target.value }); toast(`You are now presenting as ${person(state.user).name}.`); }
  });
  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && state.panel) { dispatch({ type: 'SET_PANEL', panel: null }); return; }
    if (event.target.matches('textarea[data-draft]') && event.key === 'Enter' && !event.shiftKey && !event.isComposing) { event.preventDefault(); event.target.closest('form').requestSubmit(); return; }
    if (event.key === 'Tab' && state.panel) {
      const focusable = [...modalLayer.querySelectorAll('button:not(:disabled),input,textarea,select,[tabindex="0"]')].filter((item) => !item.hidden);
      const first = focusable[0], last = focusable.at(-1);
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); }
    }
    if (!event.target.matches('input,textarea,select') && !state.panel) {
      if (event.key === 'ArrowRight') { stopPlayback(); jump(state.scene + 1); }
      if (event.key === 'ArrowLeft') { stopPlayback(); jump(state.scene - 1); }
    }
  });

  window.RamusDemo = { getState: () => state, dispatch, jump, reset };
  render();
})();
