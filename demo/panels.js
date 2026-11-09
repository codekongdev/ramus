/* Read-only panel rendering. State changes belong to the demo's event handler. */
(function () {
  'use strict';

  const escape = (value) => String(value == null ? '' : value).replace(/[&<>"']/g, (char) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  }[char]));
  const ids = ['planning', 'coupons', 'cart', 'checkout'];
  const names = { planning: 'Product planning', coupons: 'Coupon policy', cart: 'Cart experience', checkout: 'Checkout flow' };
  const fallbackResults = {
    coupons: 'Apply one eligible coupon to the merchandise subtotal before shipping.\n\nA $10 coupon on a $100 subtotal produces a $90 discounted subtotal. Add $4.90 shipping afterwards: the customer pays $94.90.\n\nKeep the same calculation and naming in cart and checkout. Explain why a coupon cannot be applied, and preserve the cart while customers choose another coupon.',
    cart: 'Display the merchandise subtotal, coupon discount, and shipping as separate rows.\n\nMerchandise subtotal: $100.00\nCoupon discount: −$10.00\nShipping: $4.90\nTotal: $94.90\n\nUse the saved coupon policy as the input for checkout. Recalculate the total when the coupon changes and retain the customer’s choices.',
    checkout: 'Use the reviewed cart and coupon decisions without re-entering their content.\n\nShow the same subtotal, coupon discount, shipping, and $94.90 total as the cart. Revalidate coupon eligibility before order confirmation and explain any change.',
    planning: 'Build one connected shopping flow: the coupon policy defines the calculation, the cart presents it, and checkout carries the reviewed decision forward.',
  };
  const conversation = (state, id) => (state.conversations || {})[id] || {};
  const title = (state, id) => conversation(state, id).title || names[id] || 'Conversation';
  const result = (state, id) => (state.results || {})[id] || null;
  const resultBody = (state, id) => {
    const saved = result(state, id);
    const drafts = state.resultDrafts || state.drafts || {};
    const copy = window.RamusModel && window.RamusModel.RESULT_COPY;
    return typeof drafts[id] === 'string' ? drafts[id] : saved && typeof saved.body === 'string' ? saved.body : copy && copy[id] || fallbackResults[id] || '';
  };
  const latestVersion = (state) => Number((state.convention || {}).latest) || 0;
  const versions = (state) => Array.isArray((state.convention || {}).versions) ? state.convention.versions : [];
  const revision = (state, version) => versions(state).find((item) => Number(item.version) === Number(version));
  const paragraphs = (body) => String(body || '').split(/\n\s*\n/).map((paragraph) => `<p>${escape(paragraph).replace(/\n/g, '<br>')}</p>`).join('');
  const button = (label, action, attributes, variant) => `<button type="button" class="btn ${variant || 'secondary'}" data-action="${escape(action)}" ${attributes || ''}>${escape(label)}</button>`;
  const sourceAttributes = (id) => `data-source="${escape(id)}"`;
  const open = (label, panel, source, variant) => button(label, 'open-panel', `data-panel="${escape(panel)}" ${source ? sourceAttributes(source) : ''}`, variant);
  const close = () => button('Close', 'close-panel', '', 'ghost');

  function shell(titleText, subtitle, body, footer, wide) {
    return `<div class="modal-backdrop"><section class="modal${wide ? ' wide' : ''}" role="dialog" aria-modal="true" aria-labelledby="modal-title" tabindex="-1">
      <header class="modal-header"><div><h2 id="modal-title">${escape(titleText)}</h2>${subtitle ? `<p>${escape(subtitle)}</p>` : ''}</div>${close()}</header>
      <div class="modal-body">${body}</div>${footer ? `<footer class="modal-footer">${footer}</footer>` : ''}
    </section></div>`;
  }

  function resources(state) {
    const active = state.active || 'planning';
    const latest = latestVersion(state);
    const applied = Number(conversation(state, active).appliedVersion) || 0;
    const shown = revision(state, latest);
    const current = applied ? `This conversation uses v${applied}.` : 'No convention is applied to this conversation yet.';
    const versionRows = versions(state).slice().sort((a, b) => Number(b.version) - Number(a.version)).map((item) => {
      const version = Number(item.version);
      return `<div class="version-row"><div><strong>v${escape(version)}${version === latest ? ' · Latest' : ''}</strong><p>${version === applied ? 'Applied to this conversation' : version === latest ? 'Available to apply explicitly' : 'Saved version · unchanged'}</p></div>${version === applied ? '<span class="notice teal">Applied</span>' : button(`Apply v${version}`, 'apply-convention', `data-version="${escape(version)}" data-target="${escape(active)}"`, version === latest ? 'primary' : 'secondary')}</div>`;
    }).join('');
    const body = `<div class="document-meta"><span>Shared skill / convention</span><span>${escape(title(state, active))}</span></div>
      <h3>Shopping flow convention</h3>
      <p class="notice ${applied && applied < latest ? 'amber' : 'teal'}">${escape(current)} ${latest ? `The latest saved version is v${escape(latest)}.` : 'Create a first version to give every specialist the same starting point.'}</p>
      ${shown ? `<article class="result-document" aria-label="Latest convention">${paragraphs(shown.body)}</article>` : '<p>Define a common calculation, shared vocabulary, and handoff rules before splitting the work.</p>'}
      <h3>Saved versions</h3>${versionRows || '<p>No saved versions yet.</p>'}
      <p class="notice">Saving a new version does not update existing conversations. Each conversation keeps its selected version until someone applies another one.</p>`;
    return shell('Shared convention', 'One common starting point. Explicit versions for every conversation.', body, `${close()}${open(latest ? `Create v${latest + 1}` : 'Create v1', 'convention-edit', active, 'primary')}`, false);
  }

  function editConvention(state) {
    const latest = latestVersion(state);
    const current = revision(state, latest);
    const next = latest + 1;
    const defaultBody = 'Use one shared shopping calculation across coupon, cart, and checkout.\n\nApply an eligible coupon to the merchandise subtotal before shipping. Show subtotal, coupon discount, shipping, and final total separately.\n\nExample: $100.00 subtotal − $10.00 coupon + $4.90 shipping = $94.90 total.\n\nSave a reviewed conclusion before another conversation uses it.';
    const model = window.RamusModel;
    const suggested = latest === 0 ? model?.CONVENTION_V1 : latest === 1 ? model?.CONVENTION_V2 : current?.body;
    const body = typeof state.conventionDraft === 'string' ? state.conventionDraft : suggested || defaultBody;
    return shell(`Save convention v${next}`, 'Previous versions stay unchanged. Applying this version is a separate step.', `<form id="convention-form" data-action="save-convention">
      <label class="field-label" for="convention-body">Team instructions</label>
      <textarea class="textarea" id="convention-body" name="convention" rows="12" required>${escape(body)}</textarea>
      <p class="notice amber">A conversation using an older version will continue using it after this save.</p>
    </form>`, `${open('Back to convention', 'resources', state.active, 'secondary')}<button class="btn primary" type="submit" form="convention-form" data-action="save-convention">Save v${next}</button>`, false);
  }

  function resultPanel(state, panel) {
    const source = ids.includes(panel.sourceId) ? panel.sourceId : state.active || 'coupons';
    const saved = result(state, source);
    const version = saved && Number(saved.version) || 0;
    const required = source === 'cart' ? ['coupons'] : source === 'checkout' ? ['coupons', 'cart'] : [];
    const received = (conversation(state, source).inputs || []).map(input => inputSource(state, input));
    const missing = required.filter(id => !received.includes(id));
    const blocked = missing.length > 0;
    const waiting = blocked ? `Waiting for the approved ${missing.map(id => title(state, id)).join(' and ')} ${missing.length === 1 ? 'result' : 'results'}. Send the saved conclusions here before approving this result. No unconfirmed coupon terms or totals will be assumed.` : '';
    const body = blocked ? waiting + (source === 'cart' ? '\n\nCurrent unconfirmed cart: item subtotal $100.00 + shipping $4.90 = $104.90 before any approved discount.' : '') : resultBody(state, source);
    return shell(saved && saved.title || `${title(state, source)} conclusion`, 'Review the conclusion before you save or pass it to another conversation.', `<div class="document-meta"><span>Source: ${escape(title(state, source))}</span><span>${blocked ? 'Waiting for required inputs' : version ? `Saved v${escape(version)}` : 'Unsaved draft'}</span></div>
      ${blocked ? `<p class="notice amber" role="status">${escape(waiting)}</p>` : ''}
      <form id="result-form" data-action="save-result" ${sourceAttributes(source)}>
        <label class="field-label" for="result-body">${blocked ? 'Pending research' : 'Reviewed conclusion'}</label>
        <textarea class="textarea result-document" id="result-body" name="result" rows="13" ${sourceAttributes(source)} ${blocked ? 'readonly' : 'required'}>${escape(body)}</textarea>
      </form>
      <p class="notice">${blocked ? 'A result can be approved after its required saved inputs are connected.' : 'Saving creates a reviewed version. Other conversations use the exact saved version you send them.'}</p>`, `${close()}${saved && !blocked ? open('Send to conversation', 'share', source, 'secondary') : ''}<button class="btn primary" type="submit" form="result-form" data-action="save-result" ${sourceAttributes(source)} ${blocked ? 'disabled aria-disabled="true"' : ''}>Save${version ? ` v${version + 1}` : ' conclusion'}</button>`, true);
  }

  function sharePanel(state, panel) {
    const source = ids.includes(panel.sourceId) ? panel.sourceId : state.active || 'coupons';
    const saved = result(state, source);
    if (!saved) return shell('Save the conclusion first', 'Only reviewed, saved conclusions can be passed on.', '<p>Return to the result, review its content, and save a version before connecting it to another conversation.</p>', open('Review conclusion', 'result', source, 'primary'), false);
    const targets = ids.filter((id) => id !== source);
    const defaultTarget = source === 'coupons' ? 'cart' : source === 'cart' ? 'checkout' : targets.includes('cart') ? 'cart' : targets[0];
    const choices = targets.map((id) => `<label class="choice"><input type="radio" name="share-target" value="${escape(id)}" ${id === defaultTarget ? 'checked' : ''}><span><strong>${escape(title(state, id))}</strong><small>${escape(conversation(state, id).owner || (id === 'planning' ? 'Team' : 'Specialist'))}</small></span></label>`).join('');
    return shell('Send a saved conclusion', 'Connect an exact version as input to the next conversation.', `<div class="document-meta"><span>${escape(saved.title || title(state, source))}</span><span>Saved v${escape(saved.version)}</span></div>
      <article class="result-document">${paragraphs(saved.body)}</article>
      <fieldset class="share-targets"><legend class="field-label">Choose a destination</legend>${choices}</fieldset>
      <p class="notice teal">Sending connects this saved version as AI input. It does not automatically run AI in the destination conversation.</p>`, `${open('Back to conclusion', 'result', source, 'secondary')}${button('Send conclusion', 'share-result', `${sourceAttributes(source)} data-target="${escape(defaultTarget)}"`, 'primary')}`, false);
  }

  function inputSource(state, input) {
    if (input && typeof input === 'object') {
      if (ids.includes(input.sourceId)) return input.sourceId;
      if (ids.includes(input.sourceConversationId)) return input.sourceConversationId;
      if (ids.includes(input.source)) return input.source;
      const resultId = input.resultId || input.id;
      return Object.keys(state.results || {}).find((id) => state.results[id] && state.results[id].id === resultId) || null;
    }
    return null;
  }

  function graph(state) {
    const positions = { planning: [440, 66], coupons: [150, 250], cart: [440, 250], checkout: [730, 250] };
    const relationship = (from, to) => (conversation(state, to).inputs || []).some((input) => inputSource(state, input) === from);
    const line = (from, to, dashed) => {
      const [x1, y1] = positions[from], [x2, y2] = positions[to];
      const d = dashed ? `M ${x1 + 108} ${y1} L ${x2 - 108} ${y2}` : `M ${x1} ${y1 + 35} V 155 H ${x2} V ${y2 - 35}`;
      return `<path d="${d}" fill="none" stroke="${dashed ? '#157d72' : '#b8c8d0'}" stroke-width="2" ${dashed ? 'stroke-dasharray="6 6"' : ''} marker-end="url(#graph-arrow${dashed ? '-input' : ''})" />`;
    };
    const directCouponInput = relationship('coupons', 'checkout') ? '<path d="M 150 285 C 150 337 730 337 730 285" fill="none" stroke="#157d72" stroke-width="2" stroke-dasharray="6 6" marker-end="url(#graph-arrow-input)" />' : '';
    const edges = state.branched ? ['coupons', 'cart', 'checkout'].map((id) => line('planning', id, false)).join('') + (relationship('coupons', 'cart') ? line('coupons', 'cart', true) : '') + (relationship('cart', 'checkout') ? line('cart', 'checkout', true) : '') + directCouponInput : '';
    const visibleIds = state.branched ? ids : ['planning'];
    const nodes = visibleIds.map((id) => {
      const [x, y] = positions[id];
      const task = (state.tasks || []).find((item) => item.id === id);
      const subtitle = id === 'planning' ? 'Shared parent conversation' : `${conversation(state, id).owner || 'Specialist'}${task ? ` · ${task.status}` : ''}`;
      return `<a href="#${escape(id)}" data-action="navigate" data-id="${escape(id)}" aria-label="Open ${escape(title(state, id))}"><g class="graph-node" transform="translate(${x - 108},${y - 35})"><rect width="216" height="70" rx="12" fill="${id === state.active ? '#e1f3ee' : '#ffffff'}" stroke="${id === state.active ? '#157d72' : '#d5dfe3'}"/><text x="108" y="29" text-anchor="middle" fill="#18313c" font-size="14" font-weight="600">${escape(title(state, id))}</text><text x="108" y="48" text-anchor="middle" fill="#617581" font-size="11">${escape(subtitle)}</text></g></a>`;
    }).join('');
    return shell('Connected work', 'Follow where work branches and where reviewed conclusions are reused.', `<div class="graph-shell"><svg class="graph-svg" viewBox="0 0 880 345" role="img" aria-labelledby="graph-title graph-description"><title id="graph-title">Project conversation relationships</title><desc id="graph-description">${state.branched ? 'Shared planning branches into coupon policy, cart experience, and checkout flow.' : 'The shared planning conversation is open. No specialist tasks have been branched yet.'} Dashed arrows appear only where a saved conclusion has been sent.</desc><defs><marker id="graph-arrow" markerWidth="8" markerHeight="8" refX="6" refY="4" orient="auto"><path d="M 0 0 L 8 4 L 0 8" fill="none" stroke="#b8c8d0" /></marker><marker id="graph-arrow-input" markerWidth="8" markerHeight="8" refX="6" refY="4" orient="auto"><path d="M 0 0 L 8 4 L 0 8" fill="none" stroke="#157d72" /></marker></defs>${edges}${nodes}</svg></div>
      <div class="graph-legend"><span>━━ Task branch</span><span>┄┄ Saved conclusion used as input</span></div>
      <p class="notice">Select a conversation to open it. Connections reflect saved handoffs; opening a result alone does not create a connection.</p>`, close(), true);
  }

  function before() {
    return shell('Before: three separate AI conversations', 'The team shares files, but context still has to be carried by hand.', `<div class="welcome-grid before-grid">
      <article class="result-document"><div class="document-meta">Coupon specialist · private AI</div><h3>“What counts as the subtotal?”</h3><p>One person applies the coupon before shipping. Their instructions and reasoning stay in a private conversation.</p><p class="notice amber">Copy the policy into a message.</p></article>
      <article class="result-document"><div class="document-meta">Cart specialist · private AI</div><h3>“Which policy is current?”</h3><p>Another person repeats the investigation and works from an older convention.</p><p class="notice amber">Re-explain the calculation and find the latest file.</p></article>
      <article class="result-document"><div class="document-meta">Checkout specialist · private AI</div><h3>“Can I reuse that decision?”</h3><p>The next person receives a summary without a clear version or its original context.</p><p class="notice amber">Paste the result and reconstruct the reasoning.</p></article>
    </div><div class="notice teal"><strong>With Ramus:</strong> one shared convention → parallel specialist conversations → reviewed conclusions → connected follow-up work.</div>`, `${close()}${button('Explore the shared workspace', 'begin-demo', '', 'primary')}`, true);
  }

  function intro() {
    return shell('Welcome to Ramus', '', `<div class="welcome"><div class="document-meta">A shared workspace for people and AI</div><h1 class="hero-title">Divide the work.<br>Connect the outcomes.</h1><p class="hero-lead">Three specialists shape one shopping experience. Give them the same convention, keep their work independent, and carry reviewed conclusions into the next conversation.</p>
      <div class="welcome-grid"><article><h3>01 · Align</h3><p>Pin a shared convention to an exact version.</p></article><article><h3>02 · Work in parallel</h3><p>Split coupon, cart, and checkout decisions into focused conversations.</p></article><article><h3>03 · Connect</h3><p>Save a conclusion and reuse it as input without copying its content.</p></article></div>
      <p class="notice">Interactive front-end demonstration. AI responses are scripted and progress is saved locally in this browser.</p></div>`, `${open('See the before / after', 'before', null, 'secondary')}${button('Enter the workspace', 'begin-demo', '', 'primary')}`, true);
  }

  function guide(state) {
    const chapters = window.RamusModel && window.RamusModel.scenes || [];
    return shell('Demo guide', 'Nine moments to explore. Each step opens a prepared scene.', `<div class="guide-chapters">${chapters.map(({ title: heading, description }, index) => `<button type="button" class="choice guide-chapter" data-action="scene" data-index="${index}"><span class="chapter-number">${String(index + 1).padStart(2, '0')}</span><span><strong>${escape(heading)}</strong><small>${escape(description)}</small></span></button>`).join('')}</div><p class="notice">Scene controls prepare local demonstration data. You can also explore the workspace and perform the actions yourself.</p>`, close(), false);
  }

  function renderPanel(state) {
    if (!state || !state.panel) return '';
    const panel = typeof state.panel === 'string' ? { type: state.panel } : state.panel;
    switch (panel.type) {
      case 'resources': return resources(state);
      case 'convention-edit': return editConvention(state);
      case 'result': return resultPanel(state, panel);
      case 'share': return sharePanel(state, panel);
      case 'graph': return graph(state);
      case 'before': return before();
      case 'guide': return guide(state);
      case 'intro': return intro();
      default: return '';
    }
  }

  window.RamusPanels = Object.freeze({ renderPanel });
}());
