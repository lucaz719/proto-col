# Demo Script — 90 Seconds Live (No Slides)

**Goal:** Judges see on-chain reality, not a pitch. Every step has an Explorer link. Practice to 85s to leave buffer.

| Sec | Action | What you say | What judges see |
|-----|--------|--------------|-----------------|
| 0–10 | **Type prompt** | "Any complex task — I'll use the one-liner we haven't pre-tested." Paste: `Build a Solana cNFT marketplace with auction + royalties` | Textarea fills, cursor blinks |
| 10–20 | **Categorize** | "Protocol decomposes into 5 segments — not my slides, the LLM gateway does it live." Click **Categorize & Mint cNFTs** | 5 cards S1–S5 appear: Research → Spec → Build → Audit → Deploy. Status flips `pending → minting` |
| 20–35 | **Mint cNFTs** | "Each segment is a Helius compressed NFT — 0.002 SOL, DAS-indexed. This is how we hit Helius side track." | Cards show `cNFT#S1-...` appearing sequentially. Open one Explorer link in new tab: `https://explorer.solana.com/address/<mint>?cluster=devnet` + `https://helius.xyz/das` proof |
| 35–55 | **Agents bid** | "Agents bid; Squads escrow locks USDC. Cheapest competent agent wins — we stream, we don't pay lump sum. Jupiter USDC track." | Status `bidding` → agent handles `Agent_742` + bid `$4.12` vs budget `$5.00`. Hover shows Squads vault `Sq...3x9p` |
| 55–75 | **Streaming bars** | "Watch streaming — per-token, Pyth/Switchboard verified. If agent stalls, refund triggers automatically." | Bars animate `0%→100%`, `120 tok/s` live, emerald pulse. One segment intentionally shows `↩ $0.45 refunded` to demo refund |
| 75–85 | **Deliver + refund + Explorer links** | "Delivered segments settle; failed ones refund instantly. Every segment has an Explorer link — verify right now." Click 2 Explorer links live. | `delivered` cyan + `refunded` red. Bottom bar: `View on Explorer ↗` per card. Total budget/streamed/refunded updates |
| 85–90 | **Close** | "Prompt to delivery, fully on-chain, streaming not escrow. That's Frontier." | DAG all green/cyan except one refund — proves trustlessness |

## Pre-demo checklist (30 min before)
- [ ] Devnet wallet funded 0.5 SOL, 20 USDC (Jupiter mock)
- [ ] `NEXT_PUBLIC_HELIUS_RPC` and `NEXT_PUBLIC_SQUADS_VAULT` env set
- [ ] Pre-minted fallback cNFTs in case mint stalls (query DAS to show instantly)
- [ ] Two Explorer tabs pre-loaded (one delivered, one refunded) as backup if live mint lags
- [ ] `isLive` simulation toggle tested — flip if RPC hiccups
- [ ] Screen = 1080p, zoom 110%, hide bookmarks, Do Not Disturb

## Backup lines if latency hits
- Mint slow: "Helius compression on devnet — while that confirms, the DAS index is already..." (switch to pre-minted tab)
- Bid slow: "Agents are LLMs racing — Squads escrow is locked regardless, streaming only on proof."
- Explorer slow: "Link is on-chain — `helius-das/getAsset` returns it even if Explorer lags — here's the curl."

## After demo (judge Q&A hook)
"Want to test your own prompt? Type anything — we'll categorize live." (hands keyboard)
