# proto-col — Context-Cost Protocol
### X402 for Agent Labor on Solana | Colosseum Frontier

> **Upwork pays on delivery. We pay per token — streaming, verifiable, refundable.**  
> Prompt → 5-segment DAG → cNFTs (Helius) → Squads escrow (USDC via Jupiter) → Agents stream per-token → Pyth-verified delivery → Refund.

**Live repo for Colosseum Arena Copilot** — `anchor` + `next.js` + `litellm gateway` scaffold, built to win main + 5 side tracks with one flow.

---

## 90-Second Demo

0-10s: Type prompt `Build SPL token launchpad MVP`  
10-20s: Categorizer splits into 5 segments S1-S5 (Cat1-3) with token budgets  
20-35s: Mint 5 child cNFTs via Helius Bubblegum — show 5 Explorer links  
35-55s: Agents bid via gateway — Squads vault `Sq...3x9p` holds USDC (Jupiter)  
55-75s: Live streaming bars — `42k/70k tokens (60%) $0.21` — Pyth verified badge  
75-90s: Deliver + refund `8%` + `Deliverable NFT` + `Reputation SBT` — all verifiable on Explorer

`frontend/demo_script.md` has the exact table + backup lines.

---

## Architecture

```
Prompt → LLM Gateway (cat1-fast/haiku, cat2/sonnet, cat3/opus, usage-based-routing-v2)
       → Helius cNFT mint (DAS) : 5 child cNFTs per parent
       → Squads vault escrow (USDC via Jupiter quote)
       → Agents bid (Bid PDA per bidder)
       → log_execution streaming every 30s (Redis Lua atomic cap check, 402 on exceed, 90% auto-pause)
       → Pyth/Switchboard oracle gate
       → Deliver (SPL Transfer via PDA signer) / Refund remainder + mint SBT
```

**Seeds:** `job=[b"job",authority,job_id]`, `escrow=[b"escrow",job]`, `segment=[b"segment",job,idx]`, `bid=[b"bid",job,bidder]`  
**Constants:** `CHILDREN_PER_JOB=5`, `STREAM_INTERVAL=30s`, `PAUSE_THRESHOLD=90%`, `USDC_MINT=EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v`

---

## Quick Start

### 1. Gateway ( metering )

```bash
cd gateway
cp .env.example .env # set ANTHROPIC_KEY, REDIS_URL, COLOSSEUM_COPILOT_PAT
pip install -r requirements.txt
uvicorn middleware:app --port 8000 --reload
```

### 2. Anchor

```bash
cd anchor
anchor build
anchor deploy --provider.cluster devnet
# Program ID CCP111111111111111111111111111111111111111
```

### 3. Frontend

```bash
cd frontend
npm install
npm run dev # localhost:3000
```

---

## Side Tracks — One Flow, Five Badges

| Track | How you qualify | Verifiable proof |
|-------|-----------------|------------------|
| **Helius** | Every S1-S5 minted as compressed NFT | `cNFT#S*-xxxx` + Explorer link per card |
| **Jupiter** | All budgets in USDC via Jupiter | `$14.50 USDC total` header |
| **Pyth / Switchboard** | Oracle gates streaming | `Pyth verified` badge |
| **Squads** | Squads vault escrows USDC | Vault `Sq...3x9p` in nav |
| **Superteam Earn** | Each segment = bounty | Segment card = bounty card |

---

## Improvisation

- Categorizer fails → fallback cache + Simulate Live
- Helius blocked → pre-minted DAS + curl proof
- Agent stalls → manual refund as feature

Full pivots in `frontend/improvisation.md`.

---

Built by `lucaz719` for Colosseum Frontier — improvise where needed, win the stacking.
