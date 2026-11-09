(function (root) {
  'use strict';

  const CONVENTION_V1 = [
    'Shared experience convention',
    '1. Use clear, concise English and a calm, helpful voice.',
    '2. Explain a discount together with its eligibility, minimum spend and maximum saving.',
    '3. Keep item subtotal, discount, shipping and final total transparent. Never invent an unapproved policy.',
    '4. Use the same approved policy across coupon, cart and checkout. Keep the exact version applied to each conversation.',
  ].join('\n');
  const CONVENTION_V2 = CONVENTION_V1 + '\n5. In the cart, show the shipping-inclusive total before the customer continues to checkout.';
  const RESULT_COPY = Object.freeze({
    coupons: [
      'Approved first-purchase coupon policy',
      'First-time customers receive 10% off an eligible item subtotal of $50 or more.',
      'Maximum discount: $15. The coupon cannot be combined with another discount.',
      'Apply the discount to the item subtotal before shipping. Show the saving and eligibility together.',
      'Example: $100.00 item subtotal − $10.00 discount + $4.90 shipping = $94.90 total.',
    ].join('\n'),
    cart: [
      'Approved cart experience',
      'Use the shared Coupon policy result: 10% off orders $50+, maximum $15, no stacking.',
      'Show a clear price breakdown: item subtotal $100.00; first-purchase discount −$10.00; shipping $4.90; total $94.90.',
      'Keep coupon conditions next to the discount. Preserve the approved result version when this decision is shared.',
    ].join('\n'),
    checkout: [
      'First-purchase checkout plan',
      'Use the approved Coupon policy and Cart experience results as inputs.',
      'Confirm eligibility: first purchase, $50 minimum, 10% off, $15 maximum, no stacking.',
      'Order summary: subtotal $100.00 − discount $10.00 + shipping $4.90 = total $94.90.',
      'Show this shipping-inclusive total before payment, explain any change, and keep the checkout copy clear and reassuring.',
      'Team goal complete: a consistent first-purchase journey from coupon to cart to checkout.',
    ].join('\n'),
  });
  const scenes = Object.freeze([
    { index: 0, title: 'One shared goal', description: 'Bring the team into the same planning conversation.', active: 'planning', panel: null },
    { index: 1, title: 'A shared convention', description: 'Publish v1 and apply it to shared planning.', active: 'planning', panel: 'resources' },
    { index: 2, title: 'Work in parallel', description: 'Branch coupon, cart and checkout work with the same pinned convention.', active: 'planning', panel: null },
    { index: 3, title: 'Save an approved result', description: 'Review the coupon research and save a reusable decision.', active: 'coupons', panel: 'result' },
    { index: 4, title: 'Share a decision', description: 'Share the coupon result to the cart without starting an AI run.', active: 'cart', panel: null },
    { index: 5, title: 'Refine the cart', description: 'Ask AI to use the approved coupon input and save the cart result.', active: 'cart', panel: 'result' },
    { index: 6, title: 'Publish without overwriting', description: 'Publish convention v2 while the cart remains pinned to v1.', active: 'cart', panel: 'resources' },
    { index: 7, title: 'Apply a version explicitly', description: 'Apply v2 to the cart and emphasize the shipping-inclusive total.', active: 'cart', panel: 'resources' },
    { index: 8, title: 'Continue with shared results', description: 'Combine the approved coupon and cart decisions in checkout.', active: 'checkout', panel: 'graph' },
  ].map(Object.freeze));

  const people = ['mason', 'hayden', 'jenny'];
  const ids = ['planning', 'coupons', 'cart', 'checkout'];
  function conversation(id, title, owner, messages) {
    return { id, title, owner, messages: messages || [], appliedVersion: 0, inputs: [] };
  }
  function createInitialState() {
    return {
      schemaVersion: 1, scene: 0, active: 'planning', user: 'mason', branched: false,
      convention: { latest: 0, versions: [] },
      conversations: {
        planning: conversation('planning', 'Shared planning', 'mason', [
          { id: 'planning-message-1', author: 'mason', text: 'Team goal: Design a clear first-purchase experience. We need a consistent coupon policy, cart experience and checkout flow for our online store.' },
          { id: 'planning-message-2', author: 'hayden', text: 'I’ll design the cart experience. Let’s agree on a shared writing and pricing convention, then share approved coupon decisions instead of copying AI answers between tools.' },
          { id: 'planning-message-3', author: 'jenny', text: 'I’ll design the checkout flow. Use a $100.00 item subtotal and $4.90 shipping so we can verify that customers see consistent totals.' },
        ]),
        coupons: conversation('coupons', 'Coupon policy', 'mason'),
        cart: conversation('cart', 'Cart experience', 'hayden'),
        checkout: conversation('checkout', 'Checkout flow', 'jenny'),
      },
      tasks: [], results: {}, panel: null, goalComplete: false, activity: [],
    };
  }

  function appendMessage(state, id, author, text, kind) {
    const current = state.conversations[id];
    if (!current || typeof text !== 'string' || !text.trim()) return state;
    const message = { id: id + '-message-' + (current.messages.length + 1), author, text: text.trim() };
    if (kind) message.kind = kind;
    return { ...state, conversations: { ...state.conversations, [id]: { ...current, messages: [...current.messages, message] } } };
  }
  function log(state, text) {
    return { ...state, activity: [...state.activity, text] };
  }
  function hasInput(conversationState, sourceId) {
    return conversationState.inputs.some(input => input.sourceId === sourceId);
  }
  function aiReply(state, id) {
    const current = state.conversations[id];
    if (!current) return '';
    if (id === 'planning') {
      const research = [
        'A short comparison of three first-purchase experience patterns:',
        '1. Benefit copy: a headline such as “Save 10% on your first order” is clearer than a vague welcome reward. State the saving in the same words from coupon to checkout.',
        '2. Conditions: display “orders $50+ · maximum $15 · no stacking” beside the offer, rather than hiding the conditions behind a separate link.',
        '3. Additional costs: show shipping before payment and label the final shipping-inclusive total. For our $100.00 example, a $10.00 discount plus $4.90 shipping gives a $94.90 total.',
        'Proposed team convention: use concise, reassuring English; put conditions beside the benefit; separate subtotal, discount and shipping; and explicitly apply the same approved convention version to each specialist conversation.',
      ].join('\n');
      return state.branched
        ? research + '\nThe team is working in parallel on Coupon policy, Cart experience and Checkout flow. This parent conversation stays open while the tasks run. Share each approved result to the conversation that needs it.'
        : research + '\nLet’s publish this shared convention, then assign coupon research, cart design and checkout planning as three parallel tasks. Keep the approved policy and result versions attached to each conversation.';
    }
    if (id === 'coupons') return RESULT_COPY.coupons + '\nRecommendation: show “Save 10% on your first order of $50+ · up to $15 · no stacking” near the coupon action.';
    if (id === 'cart') {
      if (!hasInput(current, 'coupons')) {
        return 'Cart research is waiting for an approved Coupon policy result. For now, show item subtotal $100.00 and shipping $4.90, for $104.90 before any unconfirmed discount. Do not guess the discount or eligibility. Share the coupon result here, then ask again.';
      }
      const coupon = current.inputs.find(input => input.sourceId === 'coupons');
      return RESULT_COPY.cart + '\nInput: Coupon policy result v' + coupon.version + '.' + (current.appliedVersion >= 2
        ? '\nConvention v2 applied: emphasize “Total including shipping: $94.90” beside the checkout button. The previous v1 result remains unchanged until a new result is saved.'
        : '\nConvention v1 applied: use concise copy and keep each price component visible. A newer convention is never applied automatically.');
    }
    const missing = ['coupons', 'cart'].filter(source => !hasInput(current, source));
    return missing.length
      ? 'Checkout planning is waiting for approved ' + missing.map(source => state.conversations[source].title).join(' and ') + ' results. Share those decisions here before finalizing the first-purchase flow. No coupon terms or totals will be guessed.'
      : RESULT_COPY.checkout + '\nInputs: ' + current.inputs.map(input => input.title + ' v' + input.version).join('; ') + '.';
  }

  function reduce(state, action) {
    if (!state || state.schemaVersion !== 1) state = createInitialState();
    if (!action || typeof action.type !== 'string') return state;
    const id = action.conversationId || state.active;
    switch (action.type) {
      case 'RESET': return createInitialState();
      case 'NAVIGATE': return ids.includes(action.id) ? { ...state, active: action.id, panel: null } : state;
      case 'SET_PANEL': return { ...state, panel: action.panel == null ? null : action.panel };
      case 'SET_USER': return people.includes(action.user) ? { ...state, user: action.user } : state;
      case 'POST_MESSAGE': {
        if (!people.includes(action.user || state.user)) return state;
        return appendMessage(state, id, action.user || state.user, action.text);
      }
      case 'SAVE_CONVENTION': {
        const body = typeof action.body === 'string' ? action.body.trim() : (state.convention.latest ? CONVENTION_V2 : CONVENTION_V1);
        if (!body || state.convention.versions.at(-1)?.body === body) return state;
        const version = state.convention.latest + 1;
        const saved = Object.freeze({ id: 'convention-v' + version, version, title: 'Shared experience convention', body });
        const next = { ...state, convention: { latest: version, versions: [...state.convention.versions, saved] } };
        if (version === 1) next.conversations = { ...state.conversations, planning: { ...state.conversations.planning, appliedVersion: 1 } };
        return log(next, state.user + ' published shared convention v' + version + '. Existing conversations keep their applied version.');
      }
      case 'APPLY_CONVENTION': {
        const current = state.conversations[id];
        const version = Number(action.version);
        if (!current || !state.convention.versions.some(item => item.version === version) || current.appliedVersion === version) return state;
        return log({ ...state, conversations: { ...state.conversations, [id]: { ...current, appliedVersion: version } } }, 'Applied convention v' + version + ' to ' + current.title + '.');
      }
      case 'BRANCH': {
        if (state.branched || !state.conversations.planning.appliedVersion) return state;
        const version = state.conversations.planning.appliedVersion;
        const conversations = { ...state.conversations };
        const goals = { coupons: 'Research and agree on a clear first-purchase coupon policy.', cart: 'Design a transparent cart experience using the approved coupon decision.', checkout: 'Design checkout using the approved coupon and cart results.' };
        for (const child of ['coupons', 'cart', 'checkout']) {
          conversations[child] = { ...conversations[child], appliedVersion: version, messages: [
            { id: child + '-message-1', author: conversations[child].owner, text: goals[child] + ' Use the shared convention pinned to v' + version + '.' },
          ] };
        }
        let next = { ...state, branched: true, conversations, tasks: ['coupons', 'cart', 'checkout'].map(child => ({ id: child, conversationId: child, title: conversations[child].title, owner: conversations[child].owner, status: 'running' })) };
        next = appendMessage(next, 'planning', 'ai', 'I’ve started three parallel tasks: Coupon policy, Cart experience and Checkout flow. Each inherits shared convention v' + version + '. Keep discussing here while the tasks progress.', 'branch');
        return log(next, 'Three parallel tasks started with convention v' + version + '.');
      }
      case 'COMPLETE_TASK': {
        const task = state.tasks.find(item => item.id === id);
        if (!task || task.status === 'ready') return state;
        return log({ ...state, tasks: state.tasks.map(item => item.id === id ? { ...item, status: 'ready' } : item) }, state.conversations[id].title + ' is ready for review.');
      }
      case 'AI_REPLY': {
        if (!state.conversations[id]) return state;
        return appendMessage(state, id, 'ai', aiReply(state, id), 'ai');
      }
      case 'SAVE_RESULT': {
        if (!state.conversations[id] || id === 'planning') return state;
        const current = state.conversations[id];
        const hasDependencies = id === 'coupons' || (id === 'cart' ? hasInput(current, 'coupons') : hasInput(current, 'coupons') && hasInput(current, 'cart'));
        if (!hasDependencies) return state;
        let body = typeof action.body === 'string' ? action.body.trim() : RESULT_COPY[id];
        if (!body) return state;
        if (action.body == null && id === 'cart' && current.appliedVersion >= 2) body += '\nConvention v2: show “Total including shipping: $94.90” beside the checkout button.';
        const previous = state.results[id];
        if (previous && previous.body === body) return state;
        const result = Object.freeze({ id: 'result-' + id, title: current.title, version: previous ? previous.version + 1 : 1, body, sourceId: id });
        return log({ ...state, results: { ...state.results, [id]: result }, goalComplete: id === 'checkout' ? true : state.goalComplete }, state.user + ' saved ' + result.title + ' result v' + result.version + '.');
      }
      case 'SHARE_RESULT': {
        const source = state.results[action.sourceId];
        const target = state.conversations[action.targetId];
        if (!source || !target || source.sourceId === action.targetId) return state;
        const previous = target.inputs.find(input => input.sourceId === source.sourceId);
        if (previous && previous.version === source.version && previous.body === source.body) return state;
        const snapshot = Object.freeze({ ...source });
        const inputs = previous ? target.inputs.map(input => input.sourceId === source.sourceId ? snapshot : input) : [...target.inputs, snapshot];
        return log({ ...state, conversations: { ...state.conversations, [action.targetId]: { ...target, inputs } } }, 'Shared ' + source.title + ' v' + source.version + ' to ' + target.title + '. No AI run started.');
      }
      case 'SCENE': return Number.isInteger(action.index) && action.index >= 0 && action.index < scenes.length ? buildScene(action.index) : state;
      default: return state;
    }
  }

  function buildScene(index) {
    if (!Number.isInteger(index) || index < 0 || index >= scenes.length) return createInitialState();
    let state = createInitialState();
    const steps = [
      [],
      [{ type: 'SAVE_CONVENTION', body: CONVENTION_V1 }],
      [{ type: 'BRANCH' }, { type: 'AI_REPLY', conversationId: 'cart' }],
      [{ type: 'AI_REPLY', conversationId: 'coupons' }, { type: 'COMPLETE_TASK', conversationId: 'coupons' }, { type: 'SAVE_RESULT', conversationId: 'coupons' }],
      [{ type: 'SHARE_RESULT', sourceId: 'coupons', targetId: 'cart' }],
      [{ type: 'AI_REPLY', conversationId: 'cart' }, { type: 'COMPLETE_TASK', conversationId: 'cart' }, { type: 'SAVE_RESULT', conversationId: 'cart' }],
      [{ type: 'SAVE_CONVENTION', body: CONVENTION_V2 }],
      [{ type: 'APPLY_CONVENTION', conversationId: 'cart', version: 2 }, { type: 'AI_REPLY', conversationId: 'cart' }, { type: 'SAVE_RESULT', conversationId: 'cart' }],
      [{ type: 'SHARE_RESULT', sourceId: 'coupons', targetId: 'checkout' }, { type: 'SHARE_RESULT', sourceId: 'cart', targetId: 'checkout' }, { type: 'APPLY_CONVENTION', conversationId: 'checkout', version: 2 }, { type: 'AI_REPLY', conversationId: 'checkout' }, { type: 'COMPLETE_TASK', conversationId: 'checkout' }, { type: 'SAVE_RESULT', conversationId: 'checkout' }],
    ];
    for (let step = 1; step <= index; step += 1) for (const action of steps[step]) state = reduce(state, action);
    return { ...state, scene: index, active: scenes[index].active, panel: scenes[index].panel ? { type: scenes[index].panel, sourceId: scenes[index].active } : null };
  }

  const api = { createInitialState, reduce, scenes, CONVENTION_V1, CONVENTION_V2, RESULT_COPY };
  root.RamusModel = api;
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
})(typeof window === 'undefined' ? globalThis : window);
