# Ramus presentation demo

English-only, frontend-only interactive prototype based on the supplied first-purchase planning script. No installation, API, account, or AI key is required. Responses are scripted; changes stay in this browser.

## Open

Open **`ramus-demo.html`** directly in a browser. This standalone file includes its styles, scripts, and font and works offline.

Alternatively, from the repository root:

```sh
python3 demo/serve.py
```

Open <http://127.0.0.1:5199>. The source entry is `demo/index.html`.

## Present

Use **Next scene** for nine prepared story checkpoints. You can also select the progress dots, use the left/right arrow keys, or press **Play guided demo**. **Reset demo** returns to the beginning.

1. Align Mason, Hayden, and Jenny around the shared purchase-flow goal.
2. Save service convention v1.
3. Branch coupon, cart, and checkout work; each inherits v1.
4. Review and save the coupon policy: 10% off orders of $50+, capped at $15, with no stacking.
5. Send that result to the cart as a version-pinned input. Sending does not run AI.
6. Ask AI to refine the cart: $100 − $10 + $4.90 shipping = $94.90.
7. Publish convention v2. Existing conversations retain v1.
8. Explicitly apply v2 to the cart and highlight the shipping-inclusive total.
9. Carry the coupon and cart results into checkout and inspect the relationship map.

The workspace also supports manual messages, team-member switching, task review, editable conclusions, destination selection, result snapshots, convention versions, and an explanation of the previous separate-AI workflow. Use `@AI` in a message for a scripted response. The project map uses solid branches and dashed result dependencies.

## Verify and rebuild

```sh
node --test demo/model.test.cjs
node demo/build.mjs
node --test demo/smoke.test.cjs
```

The browser smoke test uses the repository's Playwright dependency and starts its own local server. It never calls a model or changes shared databases. Inter is included under the SIL Open Font License in `assets/Inter-OFL-1.1.txt`.
