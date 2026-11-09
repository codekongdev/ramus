const test = require('node:test');
const assert = require('node:assert/strict');
const { createInitialState, reduce, scenes, CONVENTION_V1, CONVENTION_V2 } = require('./model.js');

function deepFreeze(value) {
  if (value && typeof value === 'object') {
    Object.values(value).forEach(deepFreeze);
    Object.freeze(value);
  }
  return value;
}
const scene = index => reduce(createInitialState(), { type: 'SCENE', index });

test('initial state is independent and contains the English team brief', () => {
  const a = createInitialState();
  const b = createInitialState();
  a.conversations.planning.messages.push({ id: 'local', author: 'mason', text: 'Local draft' });
  assert.equal(b.conversations.planning.messages.length, 3);
  assert.equal(b.schemaVersion, 1);
  assert.equal(b.branched, false);
  assert.match(b.conversations.planning.messages[0].text, /Design a clear first-purchase experience/);
  assert.equal(b.conversations.coupons.owner, 'mason');
  assert.equal(b.conversations.cart.owner, 'hayden');
  assert.equal(b.conversations.checkout.owner, 'jenny');
});

test('parent research compares benefits, conditions and costs with a shared convention proposal', () => {
  const state = reduce(createInitialState(), { type: 'AI_REPLY', conversationId: 'planning' });
  const text = state.conversations.planning.messages.at(-1).text;
  assert.match(text, /Benefit copy:/);
  assert.match(text, /Conditions:/);
  assert.match(text, /Additional costs:/);
  assert.match(text, /Proposed team convention:/);
  assert.match(text, /\$94\.90/);
});

test('branches require a convention, inherit its exact version and are idempotent', () => {
  let state = createInitialState();
  assert.strictEqual(reduce(state, { type: 'BRANCH' }), state);
  state = reduce(state, { type: 'SAVE_CONVENTION' });
  state = reduce(deepFreeze(state), { type: 'BRANCH' });
  assert.equal(state.tasks.length, 3);
  assert.ok(state.tasks.every(task => task.status === 'running'));
  assert.ok(['coupons', 'cart', 'checkout'].every(id => state.conversations[id].appliedVersion === 1));
  assert.strictEqual(reduce(state, { type: 'BRANCH' }), state);
});

test('publishing v2 leaves applied versions and previous snapshots unchanged', () => {
  const before = deepFreeze(scene(5));
  const state = reduce(before, { type: 'SAVE_CONVENTION', body: CONVENTION_V2 });
  assert.equal(state.convention.latest, 2);
  assert.equal(state.convention.versions[0].body, CONVENTION_V1);
  assert.equal(state.conversations.cart.appliedVersion, 1);
  assert.equal(state.conversations.checkout.appliedVersion, 1);
  assert.strictEqual(state.results.cart, before.results.cart);
});

test('sharing attaches a fixed result version without starting AI or duplicating inputs', () => {
  const before = deepFreeze(scene(3));
  const state = reduce(before, { type: 'SHARE_RESULT', sourceId: 'coupons', targetId: 'cart' });
  assert.equal(state.conversations.cart.inputs[0].version, 1);
  assert.equal(state.conversations.cart.messages.length, before.conversations.cart.messages.length);
  assert.deepEqual(state.tasks, before.tasks);
  assert.strictEqual(reduce(state, { type: 'SHARE_RESULT', sourceId: 'coupons', targetId: 'cart' }), state);
  const revised = reduce(state, { type: 'SAVE_RESULT', conversationId: 'coupons', body: 'Revised approved policy' });
  assert.equal(revised.results.coupons.version, 2);
  assert.equal(revised.conversations.cart.inputs[0].version, 1);
  assert.notEqual(revised.conversations.cart.inputs[0].body, revised.results.coupons.body);
  const sharedAgain = reduce(revised, { type: 'SHARE_RESULT', sourceId: 'coupons', targetId: 'cart' });
  assert.equal(sharedAgain.conversations.cart.inputs.length, 1);
  assert.equal(sharedAgain.conversations.cart.inputs[0].version, 2);
});

test('cart waits for approved coupon input and then uses the policy and correct totals', () => {
  const state = reduce(scene(2), { type: 'AI_REPLY', conversationId: 'cart' });
  assert.match(state.conversations.cart.messages.at(-1).text, /waiting for an approved Coupon policy/);
  assert.strictEqual(reduce(state, { type: 'SAVE_RESULT', conversationId: 'cart' }), state);
  const refined = scene(5);
  const text = refined.conversations.cart.messages.at(-1).text;
  assert.match(text, /10% off orders \$50\+/);
  assert.match(text, /maximum \$15, no stacking/);
  assert.match(text, /total \$94\.90/);
});

test('applying v2 changes only the selected conversation and a newly saved result', () => {
  const published = deepFreeze(scene(6));
  const applied = reduce(published, { type: 'APPLY_CONVENTION', conversationId: 'cart', version: 2 });
  assert.equal(applied.conversations.cart.appliedVersion, 2);
  assert.equal(applied.conversations.coupons.appliedVersion, 1);
  assert.strictEqual(applied.results.cart, published.results.cart);
  const reply = reduce(applied, { type: 'AI_REPLY', conversationId: 'cart' });
  assert.match(reply.conversations.cart.messages.at(-1).text, /Total including shipping: \$94\.90/);
  const saved = reduce(reply, { type: 'SAVE_RESULT', conversationId: 'cart' });
  assert.equal(saved.results.cart.version, 2);
  assert.strictEqual(reduce(saved, { type: 'SAVE_RESULT', conversationId: 'cart' }), saved);
});

test('all guided checkpoints are deterministic, independent and satisfy the final goal', () => {
  assert.equal(scenes.length, 9);
  for (let index = 0; index < scenes.length; index += 1) {
    assert.deepEqual(scene(index), reduce(deepFreeze(scene(8)), { type: 'SCENE', index }));
    assert.equal(scene(index).scene, index);
    assert.deepEqual(scene(index).panel, scenes[index].panel ? { type: scenes[index].panel, sourceId: scenes[index].active } : null);
  }
  const final = scene(8);
  assert.equal(final.goalComplete, true);
  assert.ok(final.tasks.every(task => task.status === 'ready'));
  assert.deepEqual(final.conversations.checkout.inputs.map(input => input.sourceId), ['coupons', 'cart']);
  assert.match(final.results.checkout.body, /\$94\.90/);
  assert.deepEqual(reduce(final, { type: 'RESET' }), createInitialState());
});

test('read-only navigation and panels cannot create results, tasks or AI messages', () => {
  const before = deepFreeze(scene(5));
  let state = reduce(before, { type: 'NAVIGATE', id: 'coupons' });
  state = reduce(state, { type: 'SET_PANEL', panel: 'result' });
  assert.strictEqual(state.results, before.results);
  assert.strictEqual(state.tasks, before.tasks);
  assert.strictEqual(state.conversations, before.conversations);
});

test('invalid selections and blank requests leave domain state intact', () => {
  const state = deepFreeze(scene(3));
  for (const action of [
    { type: 'NAVIGATE', id: 'missing' },
    { type: 'SCENE', index: -1 },
    { type: 'SCENE', index: '1' },
    { type: 'SET_USER', user: 'unknown' },
    { type: 'POST_MESSAGE', text: '   ' },
    { type: 'APPLY_CONVENTION', conversationId: 'cart', version: 90 },
    { type: 'SHARE_RESULT', sourceId: 'coupons', targetId: 'coupons' },
  ]) assert.strictEqual(reduce(state, action), state);
});
