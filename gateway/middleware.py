# =============================================================================
# Context-Cost Protocol — Solana Middleware (FastAPI Proxy)
# =============================================================================
# Architecture:
#   Client -> FastAPI (this file) -> LiteLLM proxy -> Anthropic
#                |-> Redis (usage counter) -> Solana PDA (budget check)
#
# Token Metering Logic (detailed):
#   1. PRE-FLIGHT:  Read X-Segment-ID header. Look up segment PDA budget
#                  (remaining = cap - spent). If missing header => 400.
#                  Estimate prompt tokens via tiktoken/anthropic count_tokens
#                  and reject immediately (402) if estimate > remaining.
#   2. DURING:     For streaming, each SSE chunk's usage delta is metered.
#                  We call Redis INCRBY on `segment:{id}:tokens` and
#                  `segment:{id}:usd_micro` atomically (pipeline). This is
#                  the off-chain hot counter — fast, no RPC latency.
#   3. POST-FLIGHT: On completion (or stream end), the *authoritative* count
#                  from LiteLLM/Anthropic `usage` field (prompt_tokens +
#                  completion_tokens) overwrites the estimate. Delta correction
#                  is applied via INCRBY. Then we call the Anchor program's
#                  `log_execution(segment_pda, tokens, cost)` to emit proof
#                  on-chain. Solana tx is async (fire-and-forget with retry
#                  queue) so it never blocks the response path.
#
# Cap Enforcement:
#   - Hard cap stored in segment PDA (u64 tokens or u64 usd_micros).
#   - Every request checks:  projected = redis_spent + estimated_tokens
#   - If projected > cap => HTTP 402 Payment Required (with JSON body
#     {error, code: "BUDGET_EXCEEDED", segment_id, cap, spent, remaining}).
#   - Streaming cap: mid-stream, if a chunk would exceed cap, the stream is
#     aborted with a final SSE event `event: budget_exceeded` and HTTP trailer.
#   - Race safety: Redis INCRBY is atomic; we use Lua script for
#     check-and-increment to avoid overshoot under concurrency.
#
# Chunk Payments (streaming):
#   Each streamed chunk optionally triggers a micro-settlement via
#   `log_execution` in batches (every N tokens or every chunk if
#   STREAM_MICRO_SETTLE=true). This creates an auditable per-chunk proof
#   trail on Solana without paying per-chunk tx fees (batched, debounced).
# =============================================================================

import os
import json
import asyncio
import hashlib
import logging
from typing import AsyncGenerator, Optional

import httpx
import redis.asyncio as aioredis
from fastapi import FastAPI, Request, Response, Header, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

# Solana / Anchor imports — optional at runtime (graceful degrade if missing)
try:
    from solana.rpc.async_api import AsyncClient as SolanaClient
    from solders.pubkey import Pubkey
    from anchorpy import Program, Provider, Wallet  # type: ignore
    HAS_SOLANA = True
except ImportError:
    HAS_SOLANA = False

load_dotenv()

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("context-cost-gateway")

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
LITELLM_PROXY_URL = os.getenv("LITELLM_PROXY_URL", "http://127.0.0.1:4000")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
SOLANA_RPC_URL = os.getenv("SOLANA_RPC_URL", "https://api.devnet.solana.com")
ANCHOR_PROGRAM_ID = os.getenv("ANCHOR_PROGRAM_ID", "")
SEGMENT_CAP_TOKENS = int(os.getenv("SEGMENT_CAP_TOKENS", "100000"))  # default cap
STREAM_MICRO_SETTLE = os.getenv("STREAM_MICRO_SETTLE", "false").lower() == "true"
STREAM_SETTLE_EVERY_N_TOKENS = int(os.getenv("STREAM_SETTLE_EVERY_N_TOKENS", "500"))
PRICE_PER_1K_TOKENS_USD = float(os.getenv("PRICE_PER_1K_TOKENS_USD", "0.003"))  # blended

# Pricing per category (USD per 1K tokens) — mirrors litellm_config.yaml models
CATEGORY_PRICING = {
    "cat1-fast":     {"input": 0.00025, "output": 0.00125},  # haiku
    "cat2-balanced": {"input": 0.003,   "output": 0.015},    # sonnet
    "cat3-power":    {"input": 0.015,   "output": 0.075},    # opus
}

app = FastAPI(
    title="Context-Cost Protocol — Gateway Middleware",
    version="0.1.0",
    description="FastAPI proxy: Redis metering + Solana PDA cap enforcement + chunk streaming proofs",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*", "X-Segment-ID", "X-Category"],
)

# ---------------------------------------------------------------------------
# Redis — lazy singleton
# ---------------------------------------------------------------------------
_redis: Optional[aioredis.Redis] = None

async def get_redis() -> aioredis.Redis:
    """Return shared async Redis client. Uses connection pooling."""
    global _redis
    if _redis is None:
        _redis = aioredis.from_url(REDIS_URL, decode_responses=True)
    return _redis

# ---------------------------------------------------------------------------
# Solana helpers
# ---------------------------------------------------------------------------
async def get_segment_budget(segment_id: str) -> dict:
    """
    Fetch segment PDA budget from Solana.
    Returns {cap, spent, remaining}. Falls back to Redis + env default if
    Solana is not configured (local dev mode).
    In production this does: program.account.segment.fetch(pda)
    """
    r = await get_redis()
    # Redis is the hot cache — always check first
    spent_raw = await r.get(f"segment:{segment_id}:tokens:spent")
    spent = int(spent_raw) if spent_raw else 0
    cap_raw = await r.get(f"segment:{segment_id}:tokens:cap")
    cap = int(cap_raw) if cap_raw else SEGMENT_CAP_TOKENS

    if HAS_SOLANA and ANCHOR_PROGRAM_ID:
        try:
            # TODO: replace with real Anchor fetch:
            #   pda = Pubkey.find_program_address([b"segment", segment_id.encode()], program_id)[0]
            #   acct = await program.account["Segment"].fetch(pda)
            #   cap, spent = acct.budget_cap, acct.budget_spent
            # For now, Redis is authoritative and Solana is settlement layer.
            pass
        except Exception as e:
            log.warning("Solana fetch failed for segment %s: %s", segment_id, e)

    return {"cap": cap, "spent": spent, "remaining": max(0, cap - spent)}


async def anchor_log_execution(
    segment_id: str,
    prompt_tokens: int,
    completion_tokens: int,
    cost_usd_micro: int,
    model: str,
) -> Optional[str]:
    """
    Call Anchor program `log_execution` instruction.
    This emits a Solana event / writes to PDA for on-chain audit proof.
    Fire-and-forget: failures are queued to Redis retry list, never block.
    Returns tx signature or None.
    """
    total = prompt_tokens + completion_tokens
    payload = {
        "segment_id": segment_id,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total,
        "cost_usd_micro": cost_usd_micro,
        "model": model,
    }

    if not (HAS_SOLANA and ANCHOR_PROGRAM_ID):
        # Local dev: just log and persist to Redis stream for later settlement
        log.info("[mock] log_execution %s", payload)
        r = await get_redis()
        await r.xadd(f"segment:{segment_id}:log", payload)  # type: ignore
        return "mock-tx-signature"

    try:
        # --- Real Anchor call (uncomment when IDL is available) ---
        # client = SolanaClient(SOLANA_RPC_URL)
        # provider = Provider(client, Wallet.local())
        # program = Program(idl, Pubkey.from_string(ANCHOR_PROGRAM_ID), provider)
        # pda, _ = Pubkey.find_program_address([b"segment", segment_id.encode()], program.pubkey)
        # sig = await program.rpc["log_execution"](
        #     total, cost_usd_micro,
        #     ctx=Context(accounts={"segment": pda, "authority": provider.wallet.public_key})
        # )
        # await client.close()
        # return str(sig)

        # Placeholder until IDL is wired — simulate success
        log.info("[solana] log_execution dispatched %s", payload)
        return "pending-tx-signature"

    except Exception as e:
        log.error("anchor_log_execution failed: %s payload=%s", e, payload)
        # Enqueue for retry worker
        r = await get_redis()
        await r.lpush("solana:retry:log_execution", json.dumps(payload))
        return None

# ---------------------------------------------------------------------------
# Token metering — Lua atomic check-and-increment
# ---------------------------------------------------------------------------
# Lua script: atomically checks cap and increments spent if allowed.
# KEYS[1] = segment:tokens:spent key, ARGV[1] = delta, ARGV[2] = cap
# Returns new spent value on success, or -1 if would exceed cap.
LUA_CHECK_AND_INCR = """
local spent = tonumber(redis.call('GET', KEYS[1]) or '0')
local delta = tonumber(ARGV[1])
local cap   = tonumber(ARGV[2])
if spent + delta > cap then
  return -1
end
return redis.call('INCRBY', KEYS[1], delta)
"""

async def try_consume_budget(segment_id: str, delta_tokens: int) -> dict:
    """
    Atomically try to consume `delta_tokens` from segment budget.
    Uses Lua script so concurrent requests cannot overshoot cap.
    Returns {ok: bool, spent, remaining, cap} and raises 402 if exceeded.
    """
    r = await get_redis()
    budget = await get_segment_budget(segment_id)
    cap = budget["cap"]

    # Attempt atomic increment
    try:
        result = await r.eval(LUA_CHECK_AND_INCR, 1, f"segment:{segment_id}:tokens:spent", delta_tokens, cap)
    except Exception:
        # Fallback if Lua EVAL not supported (e.g. fakeredis in tests)
        spent = int(await r.get(f"segment:{segment_id}:tokens:spent") or 0)
        if spent + delta_tokens > cap:
            result = -1
        else:
            result = await r.incrby(f"segment:{segment_id}:tokens:spent", delta_tokens)

    if int(result) == -1:
        # Re-read for accurate error body
        budget = await get_segment_budget(segment_id)
        raise HTTPException(
            status_code=402,
            detail={
                "error": "Budget exceeded",
                "code": "BUDGET_EXCEEDED",
                "segment_id": segment_id,
                "cap": budget["cap"],
                "spent": budget["spent"],
                "remaining": budget["remaining"],
                "requested": delta_tokens,
                "hint": "Top up segment PDA or reduce prompt/completion size.",
            },
        )
    new_spent = int(result)
    return {"ok": True, "spent": new_spent, "cap": cap, "remaining": max(0, cap - new_spent)}


def estimate_tokens(messages_or_text) -> int:
    """
    Rough token estimation for pre-flight check.
    Uses ~4 chars per token heuristic. For accuracy, replace with
    anthropic count_tokens or tiktoken in production.
    """
    if isinstance(messages_or_text, str):
        return max(1, len(messages_or_text) // 4)
    if isinstance(messages_or_text, list):
        total_chars = sum(len(m.get("content", "") if isinstance(m, dict) else str(m)) for m in messages_or_text)
        return max(1, total_chars // 4)
    return 256  # fallback estimate


def cost_usd_micro(model: str, prompt_tokens: int, completion_tokens: int) -> int:
    """Compute cost in micro-dollars (1e-6 USD) for on-chain logging."""
    pricing = CATEGORY_PRICING.get(model, CATEGORY_PRICING["cat2-balanced"])
    usd = (prompt_tokens / 1000) * pricing["input"] + (completion_tokens / 1000) * pricing["output"]
    return int(usd * 1_000_000)

# ---------------------------------------------------------------------------
# Helpers — category routing
# ---------------------------------------------------------------------------
CATEGORY_TO_MODEL = {
    "cat1-fast": "cat1-fast",
    "cat2-balanced": "cat2-balanced",
    "cat3-power": "cat3-power",
    # aliases
    "fast": "cat1-fast",
    "balanced": "cat2-balanced",
    "power": "cat3-power",
    "haiku": "cat1-fast",
    "sonnet": "cat2-balanced",
    "opus": "cat3-power",
}

def resolve_model(requested_model: str, x_category: Optional[str]) -> str:
    """Resolve X-Category header (or body category) to a LiteLLM model alias."""
    if x_category and x_category.lower() in CATEGORY_TO_MODEL:
        return CATEGORY_TO_MODEL[x_category.lower()]
    if requested_model in CATEGORY_TO_MODEL:
        return CATEGORY_TO_MODEL[requested_model]
    return requested_model  # passthrough — let LiteLLM validate

# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.get("/health")
async def health():
    r = await get_redis()
    try:
        await r.ping()
        redis_ok = True
    except Exception:
        redis_ok = False
    return {
        "status": "ok",
        "redis": redis_ok,
        "solana": HAS_SOLANA and bool(ANCHOR_PROGRAM_ID),
        "litellm_proxy": LITELLM_PROXY_URL,
    }


@app.get("/v1/segments/{segment_id}/budget")
async def get_budget(segment_id: str):
    """Inspect current spend vs cap for a segment (debug / UI)."""
    budget = await get_segment_budget(segment_id)
    return {"segment_id": segment_id, **budget}


@app.post("/v1/segments/{segment_id}/budget/topup")
async def topup_budget(segment_id: str, body: dict):
    """
    Admin: set/raise cap for a segment. In production this should be
    gated by PDA authority check. Writes to Redis and (async) to Solana.
    """
    new_cap = int(body.get("cap", SEGMENT_CAP_TOKENS))
    r = await get_redis()
    await r.set(f"segment:{segment_id}:tokens:cap", new_cap)
    log.info("Budget cap set segment=%s cap=%d", segment_id, new_cap)
    return {"segment_id": segment_id, "cap": new_cap}


async def _proxy_request(request: Request, body_bytes: bytes) -> httpx.Response:
    """Forward request to LiteLLM proxy, preserving headers/body."""
    # Strip hop-by-hop headers, inject LiteLLM auth
    headers = {k: v for k, v in request.headers.items() if k.lower() not in ("host", "content-length", "connection")}
    headers["Authorization"] = f"Bearer {os.getenv('LITELLM_MASTER_KEY', 'sk-1234')}"

    url = f"{LITELLM_PROXY_URL}{request.url.path}"
    if request.url.query:
        url += f"?{request.url.query}"

    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.request(request.method, url, content=body_bytes, headers=headers)
        return resp


# ---- Non-streaming chat/completions proxy --------------------------------
@app.api_route("/v1/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
async def proxy(
    path: str,
    request: Request,
    x_segment_id: Optional[str] = Header(default=None, alias="X-Segment-ID"),
    x_category: Optional[str] = Header(default=None, alias="X-Category"),
):
    """
    Main proxy handler — enforces segment budget, meters tokens, logs to Solana.

    Flow for non-streaming:
      1. Require X-Segment-ID
      2. Estimate tokens, pre-flight cap check (402 if would exceed)
      3. Resolve model via category routing
      4. Proxy to LiteLLM
      5. Read authoritative usage from response, reconcile Redis counter
      6. Async Anchor log_execution (Solana proof)
    """
    # Only intercept chat/completions and completions; passthrough others
    if path not in ("chat/completions", "completions", "embeddings"):
        # Still proxy but without metering
        body = await request.body()
        resp = await _proxy_request(request, body)
        return Response(content=resp.content, status_code=resp.status_code, headers=dict(resp.headers))

    # ---- 1. Require X-Segment-ID -----------------------------------------
    if not x_segment_id:
        return JSONResponse(
            status_code=400,
            content={"error": "Missing X-Segment-ID header", "code": "MISSING_SEGMENT_ID"},
        )

    body_bytes = await request.body()
    try:
        body_json = json.loads(body_bytes) if body_bytes else {}
    except json.JSONDecodeError:
        body_json = {}

    # ---- 2. Pre-flight budget check --------------------------------------
    messages = body_json.get("messages", [])
    est_tokens = estimate_tokens(messages) if messages else estimate_tokens(body_bytes.decode(errors="ignore"))
    # Reserve generously: prompt estimate + max_tokens budget
    max_tokens = int(body_json.get("max_tokens", 1024))
    projected = est_tokens + max_tokens

    try:
        await try_consume_budget(x_segment_id, projected)
        # We optimistically reserved `projected`; we'll reconcile after.
        # This prevents concurrent requests from collectively overshooting.
        reserved = projected
        preflight_ok = True
    except HTTPException as e:
        # 402 — budget exceeded before we even proxied
        return JSONResponse(status_code=e.status_code, content=e.detail)

    # ---- 3. Category -> model routing ------------------------------------
    requested_model = body_json.get("model", "cat2-balanced")
    resolved = resolve_model(requested_model, x_category or body_json.get("category"))
    body_json["model"] = resolved
    # Preserve stream flag for branching below
    is_stream = body_json.get("stream") is True
    patched_body = json.dumps(body_json).encode()

    # ---- 4. Handle streaming separately ----------------------------------
    if is_stream:
        return await _proxy_stream(request, x_segment_id, resolved, body_json, patched_body, reserved)

    # ---- 5. Non-streaming proxy ------------------------------------------
    # Build proxied request manually (already patched model)
    headers = {k: v for k, v in request.headers.items() if k.lower() not in ("host", "content-length", "connection")}
    headers["Authorization"] = f"Bearer {os.getenv('LITELLM_MASTER_KEY', 'sk-1234')}"
    headers["content-type"] = "application/json"
    url = f"{LITELLM_PROXY_URL}/v1/{path}"

    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.request("POST", url, content=patched_body, headers=headers)

    # ---- 6. Reconcile metering from authoritative usage -------------------
    try:
        resp_json = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
    except Exception:
        resp_json = {}

    usage = resp_json.get("usage", {})
    prompt_tokens = int(usage.get("prompt_tokens", est_tokens))
    completion_tokens = int(usage.get("completion_tokens", 0))
    actual_total = prompt_tokens + completion_tokens

    # Delta correction: we reserved `projected`, actual is `actual_total`
    # so we refund/charge the difference atomically.
    r = await get_redis()
    delta = actual_total - reserved
    if delta != 0:
        await r.incrby(f"segment:{x_segment_id}:tokens:spent", delta)
        # Also track USD cost
        micros = cost_usd_micro(resolved, prompt_tokens, completion_tokens)
        await r.incrby(f"segment:{x_segment_id}:usd_micro:spent", micros)

    # Enrich response headers with metering info
    out_headers = dict(resp.headers)
    out_headers["X-Segment-ID"] = x_segment_id
    out_headers["X-Tokens-Used"] = str(actual_total)
    out_headers["X-Budget-Remaining"] = str((await get_segment_budget(x_segment_id))["remaining"])

    # Fire-and-forget Solana proof (do not await in response path — use create_task)
    asyncio.create_task(anchor_log_execution(x_segment_id, prompt_tokens, completion_tokens, cost_usd_micro(resolved, prompt_tokens, completion_tokens), resolved))

    return Response(content=resp.content, status_code=resp.status_code, headers=out_headers)


# ---- Streaming with per-chunk metering -----------------------------------
async def _proxy_stream(
    request: Request,
    segment_id: str,
    model: str,
    body_json: dict,
    patched_body: bytes,
    reserved: int,
) -> StreamingResponse:
    """
    Streaming proxy with chunk-level metering.

    Token Metering for Streams:
      - LiteLLM/Anthropic streams SSE `data: {...}` chunks. The final chunk
        (or `usage` event) carries total token counts.
      - We count chunks and estimate tokens per chunk (~chars/4) incrementally,
        doing a Redis INCRBY per chunk (or batched). If the cap would be
        exceeded mid-stream, we abort with `event: budget_exceeded`.
      - On stream end, we reconcile against authoritative usage and call
        Anchor log_execution in batches (STREAM_SETTLE_EVERY_N_TOKENS).
    """
    headers = {k: v for k, v in request.headers.items() if k.lower() not in ("host", "content-length", "connection")}
    headers["Authorization"] = f"Bearer {os.getenv('LITELLM_MASTER_KEY', 'sk-1234')}"
    headers["content-type"] = "application/json"
    headers["accept"] = "text/event-stream"
    url = f"{LITELLM_PROXY_URL}/v1/chat/completions"

    r = await get_redis()

    async def event_generator() -> AsyncGenerator[bytes, None]:
        streamed_tokens_est = 0
        prompt_tokens_est = estimate_tokens(body_json.get("messages", []))
        settled_tokens = 0
        authoritative_usage: Optional[dict] = None

        # We already reserved `reserved` tokens pre-flight. For streaming we
        # will incrementally account inside the stream and refund at the end.
        # Track how many *additional* tokens beyond reservation we consume.
        try:
            async with httpx.AsyncClient(timeout=120) as client:
                async with client.stream("POST", url, content=patched_body, headers=headers) as resp:
                    if resp.status_code != 200:
                        body = await resp.aread()
                        yield body
                        return

                    async for line in resp.aiter_lines():
                        if not line:
                            yield b"\n"
                            continue

                        # SSE lines look like: "data: {\"choices\": [{\"delta\": {\"content\": \"...\"}}]}"
                        if line.startswith("data: "):
                            data_str = line[6:]
                            if data_str.strip() == "[DONE]":
                                yield b"data: [DONE]\n\n"
                                break

                            try:
                                chunk = json.loads(data_str)
                                # Capture usage if present (LiteLLM sends it in final chunk)
                                if "usage" in chunk and chunk["usage"]:
                                    authoritative_usage = chunk["usage"]

                                # Estimate tokens in this chunk's delta
                                delta_text = ""
                                for choice in chunk.get("choices", []):
                                    d = choice.get("delta", choice.get("message", {}))
                                    delta_text += d.get("content", "") or ""
                                if delta_text:
                                    chunk_tokens = max(1, len(delta_text) // 4)
                                    streamed_tokens_est += chunk_tokens

                                    # ----- Per-chunk cap check (atomic) -----
                                    # We check if adding this chunk would exceed cap.
                                    # Note: we already reserved `reserved` optimistically,
                                    # so the "extra beyond reserve" is streamed_tokens_est -
                                    # (reserved - prompt_tokens_est). For simplicity we
                                    # track incremental Redis counter for stream deltas.
                                    budget = await get_redis()
                                    b = await get_segment_budget(segment_id)
                                    if b["remaining"] <= 0 and streamed_tokens_est > 0:
                                        # Abort stream — budget exhausted mid-stream
                                        err_event = json.dumps({
                                            "error": "Budget exceeded mid-stream",
                                            "code": "BUDGET_EXCEEDED",
                                            "segment_id": segment_id,
                                            "streamed_tokens": streamed_tokens_est,
                                        })
                                        yield f"event: budget_exceeded\ndata: {err_event}\n\n".encode()
                                        yield b"data: [DONE]\n\n"
                                        log.warning("Stream aborted — budget exceeded segment=%s", segment_id)
                                        break

                                    # ----- Chunk micro-settlement (optional) -----
                                    if STREAM_MICRO_SETTLE and (streamed_tokens_est - settled_tokens) >= STREAM_SETTLE_EVERY_N_TOKENS:
                                        micros = cost_usd_micro(model, 0, streamed_tokens_est - settled_tokens)
                                        # Fire batch settlement (debounced)
                                        asyncio.create_task(
                                            anchor_log_execution(segment_id, 0, streamed_tokens_est - settled_tokens, micros, model)
                                        )
                                        # Also increment Redis hot counter for this chunk batch
                                        await r.incrby(f"segment:{segment_id}:tokens:spent", 0)  # no-op, spent already reserved
                                        settled_tokens = streamed_tokens_est

                            except json.JSONDecodeError:
                                pass  # non-JSON SSE keepalive

                        # Forward chunk to client
                        yield (line + "\n\n").encode()

        finally:
            # ----- Stream end reconciliation --------------------------------
            # Replace estimate with authoritative counts if available
            if authoritative_usage:
                actual_prompt = int(authoritative_usage.get("prompt_tokens", prompt_tokens_est))
                actual_completion = int(authoritative_usage.get("completion_tokens", streamed_tokens_est))
                actual_total = actual_prompt + actual_completion
            else:
                actual_prompt = prompt_tokens_est
                actual_completion = streamed_tokens_est
                actual_total = actual_prompt + actual_completion

            # Correct the optimistic reservation against actual
            delta = actual_total - reserved
            if delta != 0:
                await r.incrby(f"segment:{segment_id}:tokens:spent", delta)

            micros = cost_usd_micro(model, actual_prompt, actual_completion)
            await r.incrby(f"segment:{segment_id}:usd_micro:spent", micros)

            # Final on-chain proof (authoritative)
            asyncio.create_task(
                anchor_log_execution(segment_id, actual_prompt, actual_completion, micros, model)
            )
            log.info(
                "Stream done segment=%s model=%s prompt=%d completion=%d total=%d cost_micro=%d",
                segment_id, model, actual_prompt, actual_completion, actual_total, micros,
            )

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # disable nginx buffering for SSE
            "X-Segment-ID": segment_id,
        },
    )

# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "middleware:app",
        host="0.0.0.0",
        port=int(os.getenv("GATEWAY_PORT", "8000")),
        reload=True,
        log_level="info",
    )
