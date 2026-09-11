# Improvisation — 3 Pivot Points

## Pivot 1: Categorization Fails (LLM gateway timeout / bad JSON)
**Signal:** `Categorize & Mint` spins >4s, no S1–S5 appears, console shows gateway 429/500.

**Pivot (10s):**
1. Say: "Gateway is rate-limited — this is why we have deterministic fallback." Click **Simulate Live** (or press `D` hotkey).
2. Frontend instantly populates 5 well-formed segments from local fallback prompt cache — same titles, budgets, but labeled `SIMULATED` pill.
3. Narrate: "Fallback still mints cNFTs — categorization is off-chain, execution is on-chain. The DAG doesn't care who categorized — the chain verifies delivery." Proceed to mint step; judges see DAG regardless.

**Prevention:**
- Cache last 3 successful categorizations; fallback = most recent.
- Gateway call wrapped in `Promise.race([fetch, 3000ms timeout])` → fallback on timeout.
- Keep fallback segments realistic (not lorem ipsum) — use the marketplace example.

**Line to judges:** "In production we'd retry with a second model — for the demo, the protocol survives even if the LLM doesn't."

---

## Pivot 2: Gateway Blocked / Helius Mint Blocked (RPC 403, CORS, devnet down)
**Signal:** Cards stuck on `minting` amber pulse, no `cNFT#` appears, Explorer link 404.

**Pivot (15s):**
1. Say: "Devnet Helius is throttled — let's verify via DAS directly." Open pre-loaded tab with `helius-das/getAsset` response for 5 pre-minted cNFTs (minted 1h before pitch).
2. Toggle DAG to `preMinted=true` — cards instantly show `cNFT#S*-xxxx` from cache + `DAS indexed ✓` badge. Streaming continues from there.
3. Offer: "Every cNFT here was minted with the same `mintCompressedNFT` call — here's the tx sig `5x...9p` from an hour ago — same code path, just not this second."

**Prevention:**
- Mint 5 backup cNFTs before venue; store mint addresses in `NEXT_PUBLIC_FALLBACK_MINTS`.
- DAS query `searchAssets` works even when mint stalls — show indexed assets, not just new mints.
- Have `curl` snippet ready: `curl $HELIUS_RPC -d '{"method":"getAsset","params":{"id":"..."}}'`

**Line to judges:** "Compression means we could mint 10k — devnet throttling is the bottleneck, not the protocol. DAS proves it."

---

## Pivot 3: Agent Stalls (bidding never resolves / streaming flatlines)
**Signal:** Cards stuck on `bidding` purple or `streaming` 0% for >8s, `tok/s` stays 0.

**Pivot (10s):**
1. Say: "Perfect — watch the refund." Click the stalled card → trigger manual `Refund` (or wait for auto 10s timeout which flips to `refunded` red).
2. Narrate the win: "This is the feature — agent stalled, Squads escrow refunded `$X` instantly. On Upwork you'd dispute for days. Here it's a tx." Point to refund amount + vault.
3. Advance remaining 4 segments normally — DAG still delivers 80% to show partial fulfillment is valid.

**Prevention:**
- Mock agents have 92% success; one segment intentionally refunded in simulation to normalize failure.
- Auto-refund timer: if `streaming` <5% after 10s → `refunded` + USDC returned (Squads tx).
- Keep agent bids in local array so bidding never actually waits on LLM — animate then resolve.

**Line to judges:** "We demo the failure case on purpose — trustless means refunds must be as smooth as delivery. That's the Jupiter + Squads track."

---

## General Recovery Rules
- **Never apologize, narrate:** "This is what happens on-chain when..." turns bugs into features.
- **Keep Explorer visible:** Even if live fails, open 2 pre-loaded Explorer tabs — judges remember links, not latency.
- **Keyboard shortcuts:** `D`=demo simulation, `R`=refund, `M`=pre-minted — practice without mouse.
- **Time box:** If any pivot costs >15s, skip to streaming bars — bars are the visual judges photograph.
