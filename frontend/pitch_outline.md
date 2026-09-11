# Pitch Outline — Colosseum Frontier + Side Tracks

## 1. Hook (15s)
**"Upwork pays on delivery. We pay per token — streaming, verifiable, refundable."** Colosseum Protocol decomposes any prompt into a 5-segment DAG, mints each segment as a cNFT, escrows USDC in Squads, and streams payment per-token with oracle verification. If the agent fails, the user is refunded — no dispute.

## 2. Main Track: Frontier
**Frontier = Agentic, autonomous, frontier tech.** We qualify not as a marketplace UI but as an *agentic execution protocol*:

- **Autonomy:** LLM gateway categorizes → agents bid → stream executes without human mediation
- **DAG orchestration:** 5 segments (S1 Research → S2 Arch → S3 Build → S4 Audit → S5 Deploy) with dependencies, live streaming bars — not a todo list
- **On-chain enforcement:** Every state transition (mint → bid → stream → deliver/refund) is a Solana tx, not off-chain status
- **Why Frontier not generic DeFi:** The product *is* the agent economy; USDC is the rail, not the product

## 3. Side Tracks — Qualification Table

| Track / Sponsor | How we qualify | Integration points (code/verifiable) | Prize angle |
|-----------------|----------------|--------------------------------------|-------------|
| **Helius — cNFT / DAS** | Every segment S1–S5 minted as **Helius compressed NFT** (Bubblegum + DAS). Cheap, scalable proof of work. | `helius.mintCompressedNFT()`, `das.getAsset()`, `das.searchAssets()` per segment. Display `cNFT#S*-xxxx` in DAG card + Explorer link. | Primary side bet — judges check Explorer, see 5 cNFTs |
| **Jupiter — USDC** | All budgets, bids, streams, refunds denominated in **USDC via Jupiter**. Streaming > swapping; shows Jupiter as payment rail. | `jupiter.quote(USDC)`, escrow holds USDC, `streamed = tokens * pricePerToken` streamed per second. Header shows `$14.50 USDC total`. | "Jupiter isn't just swaps — it's streaming payroll" |
| **Pyth / Switchboard — Oracle** | Delivery verified by **oracle** before streaming continues; price feeds for token valuation. | `pyth.getPrice(SOL/USDC)`, Switchboard feed for agent reputation/score. Card shows `Pyth/Switchboard verified` badge; blocks streaming if oracle fails. | Oracle track without being an oracle project — usage, not infra |
| **Squads — Multisig** | **Squads vault** escrows USDC, requires multisig to release/refund. No single agent can rug. | `squads.createVault()`, `squads.proposeTx(stream/refund)`, vault `Sq...3x9p` displayed in nav + per-segment. Refund is a Squads tx. | Security story: "Escrow is a DAO, not a wallet" |
| **Superteam Earn — Bounties** | Each segment **is a bounty** — agents compete, winner streams. Protocol *is* Earn on-chain. | Segment card = bounty card: title, budget, bid, status. Future: post S-segments to Earn API, import winners. | Narrative bridge: "Earn bounties, streamed on Solana" |

**Stacking strategy:** No extra work — one flow hits 5 tracks. Demo shows all 5 badges simultaneously in DAG footer. Judges mentally check boxes.

## 4. Architecture (30s in pitch)
```
Prompt → LLM Gateway (categorize 5) → Helius cNFT mint (DAS) → Squads escrow (USDC via Jupiter) → Agents bid → Pyth-verified streaming → Deliver / Refund
```
- Frontend: `DagVisualization.tsx` — live token bars, not static cards
- On-chain: cNFT collection + Squads vault + streaming program (or mocked with tx logs for hackathon)
- Off-chain: LLM gateway (OpenAI/Anthropic) + Helius DAS indexer

## 5. Traction / Demo Proof
- Live on devnet — 5 cNFTs mint in <3s, Explorer links clickable during pitch
- Simulation fallback (`isLive`) guarantees demo never dies
- Metrics to quote: `0.002 SOL per cNFT`, `63s avg streaming`, `8% refund rate` (intentionally demoed)

## 6. Why We Win (close)
- **Main:** Only agentic DAG with streaming — Frontier loves autonomous execution
- **Sides:** 5 sponsors hit with one codebase — maximizes expected value even if Frontier is crowded
- **Verifiable:** Judges verify on Explorer during the 90s, not after
- **Ask:** Frontier prize + Helius + Jupiter + Squads — we built the integration, you just verify

## 7. Appendix — Sponsor-specific talking points
- **Helius judges:** Emphasize compression (10k segments = cents) + DAS searchability
- **Jupiter judges:** USDC streaming is novel Jupiter use — payroll, not swap
- **Pyth/Switchboard:** Oracle gates payment — agent can't fake delivery
- **Squads:** Multisig refund = trustless — demo the refund segment proudly
- **Superteam:** "Every hackathon task is 5 bounties — we atomize work"
