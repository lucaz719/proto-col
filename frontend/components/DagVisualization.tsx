'use client';

import { useEffect, useState, useRef } from 'react';

export type SegmentStatus = 'pending' | 'minting' | 'bidding' | 'streaming' | 'delivered' | 'refunded';

export interface Segment {
  id: string; // S1-S5
  title: string;
  budget: number; // USDC
  refunded: number;
  streamed: number; // 0-100 %
  status: SegmentStatus;
  agent?: string;
  bid?: number;
  cNFT?: string;
  tokensPerSec: number;
}

const DEFAULT_SEGMENTS: Segment[] = [
  { id: 'S1', title: 'Research & Spec', budget: 2.0, refunded: 0, streamed: 0, status: 'pending', tokensPerSec: 0 },
  { id: 'S2', title: 'Architecture', budget: 3.5, refunded: 0, streamed: 0, status: 'pending', tokensPerSec: 0 },
  { id: 'S3', title: 'Core Build', budget: 5.0, refunded: 0, streamed: 0, status: 'pending', tokensPerSec: 0 },
  { id: 'S4', title: 'Audit & Test', budget: 2.5, refunded: 0, streamed: 0, status: 'pending', tokensPerSec: 0 },
  { id: 'S5', title: 'Deploy & Docs', budget: 1.5, refunded: 0, streamed: 0, status: 'pending', tokensPerSec: 0 },
];

const STATUS_COLOR: Record<SegmentStatus, string> = {
  pending: 'bg-zinc-800 text-zinc-400 border-zinc-700',
  minting: 'bg-amber-500/20 text-amber-400 border-amber-500/50 animate-pulse',
  bidding: 'bg-purple-500/20 text-purple-400 border-purple-500/50',
  streaming: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/50',
  delivered: 'bg-cyan-500/20 text-cyan-400 border-cyan-500/50',
  refunded: 'bg-red-500/20 text-red-400 border-red-500/50',
};

const STATUS_DOT: Record<SegmentStatus, string> = {
  pending: 'bg-zinc-600',
  minting: 'bg-amber-400 animate-pulse',
  bidding: 'bg-purple-400 animate-bounce',
  streaming: 'bg-emerald-400 animate-pulse',
  delivered: 'bg-cyan-400',
  refunded: 'bg-red-400',
};

function formatAddr(a?: string) {
  if (!a) return '—';
  return `${a.slice(0, 4)}…${a.slice(-4)}`;
}

export default function DagVisualization({
  segments: controlled,
  onSegmentClick,
  isLive = false,
}: {
  segments?: Segment[];
  onSegmentClick?: (id: string) => void;
  isLive?: boolean;
}) {
  const [segments, setSegments] = useState<Segment[]>(controlled ?? DEFAULT_SEGMENTS);
  const intervalRef = useRef<NodeJS.Timeout | null>(null);

  // Allow controlled or self-animated demo mode
  useEffect(() => {
    if (controlled) {
      setSegments(controlled);
      return;
    }
    // Self-demo animation when uncontrolled + isLive
    if (!isLive) return;
    let tick = 0;
    intervalRef.current = setInterval(() => {
      tick += 1;
      setSegments((prev) =>
        prev.map((s, idx) => {
          const stagger = idx * 18;
          if (tick < stagger) return s;
          const local = tick - stagger;
          if (local < 10) return { ...s, status: 'minting' as const, tokensPerSec: 0, streamed: 0 };
          if (local < 22) return { ...s, status: 'bidding' as const, agent: `Agent_${Math.floor(Math.random()*900)+100}`, bid: +(s.budget * (0.85 + Math.random()*0.1)).toFixed(2) };
          if (local < 85) {
            const pct = Math.min(100, ((local - 22) / 63) * 100);
            return { ...s, status: 'streaming' as const, streamed: Math.floor(pct), tokensPerSec: 120 + Math.floor(Math.random()*40), cNFT: `cNFT#${s.id}-${Math.random().toString(36).slice(2,6)}` };
          }
          // 5% chance refund, else delivered
          const refunded = Math.random() < 0.08 ? +(s.budget * 0.3).toFixed(2) : 0;
          return { ...s, status: refunded ? 'refunded' as const : 'delivered' as const, streamed: 100, refunded, tokensPerSec: 0 };
        })
      );
      if (tick > 140) {
        if (intervalRef.current) clearInterval(intervalRef.current);
      }
    }, 120);
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [controlled, isLive]);

  const totalBudget = segments.reduce((a, s) => a + s.budget, 0);
  const totalStreamed = segments.reduce((a, s) => a + (s.budget * s.streamed) / 100, 0);
  const totalRefunded = segments.reduce((a, s) => a + s.refunded, 0);

  return (
    <div className="w-full">
      {/* Header stats */}
      <div className="grid grid-cols-3 gap-3 mb-6">
        <div className="rounded-xl bg-zinc-900 border border-zinc-800 p-3">
          <div className="text-[11px] tracking-widest text-zinc-500 uppercase">Total Budget</div>
          <div className="text-xl font-mono font-bold text-white">${totalBudget.toFixed(2)} <span className="text-xs font-normal text-zinc-400">USDC</span></div>
          <div className="text-[11px] text-zinc-500">via Jupiter • 5 segments</div>
        </div>
        <div className="rounded-xl bg-zinc-900 border border-zinc-800 p-3">
          <div className="text-[11px] tracking-widest text-zinc-500 uppercase">Streamed</div>
          <div className="text-xl font-mono font-bold text-emerald-400">${totalStreamed.toFixed(2)}</div>
          <div className="h-1.5 bg-zinc-800 rounded-full mt-1 overflow-hidden">
            <div className="h-full bg-emerald-500 transition-all duration-500" style={{ width: `${(totalStreamed/totalBudget)*100}%` }} />
          </div>
        </div>
        <div className="rounded-xl bg-zinc-900 border border-zinc-800 p-3">
          <div className="text-[11px] tracking-widest text-zinc-500 uppercase">Refunded</div>
          <div className="text-xl font-mono font-bold text-amber-400">${totalRefunded.toFixed(2)}</div>
          <div className="text-[11px] text-zinc-500">{isLive && <span className="inline-flex items-center gap-1"><span className="w-2 h-2 bg-emerald-500 rounded-full animate-pulse"/> LIVE streaming</span>}</div>
        </div>
      </div>

      {/* DAG */}
      <div className="relative">
        {/* Connection line */}
        <div className="hidden md:block absolute top-[52px] left-[8%] right-[8%] h-[2px] bg-gradient-to-r from-zinc-700 via-cyan-500/50 to-zinc-700" />
        {/* Mobile vertical line */}
        <div className="md:hidden absolute left-[28px] top-6 bottom-6 w-[2px] bg-zinc-800" />

        <div className="grid grid-cols-1 md:grid-cols-5 gap-4 relative">
          {segments.map((seg) => (
            <div
              key={seg.id}
              onClick={() => onSegmentClick?.(seg.id)}
              className="group relative rounded-2xl bg-zinc-900 border border-zinc-800 p-4 hover:border-zinc-700 hover:bg-zinc-[900] transition cursor-pointer overflow-hidden"
            >
              {/* Accent top bar by status */}
              <div className={`absolute top-0 inset-x-0 h-[3px] ${seg.status==='streaming'?'bg-emerald-500': seg.status==='delivered'?'bg-cyan-500': seg.status==='minting'?'bg-amber-500': seg.status==='bidding'?'bg-purple-500': seg.status==='refunded'?'bg-red-500':'bg-zinc-700'}`} />

              <div className="flex items-center justify-between mb-2">
                <span className="text-xs font-mono font-bold tracking-widest text-zinc-400">{seg.id}</span>
                <span className={`inline-flex items-center gap-1.5 text-[11px] px-2 py-1 rounded-full border font-mono ${STATUS_COLOR[seg.status]}`}>
                  <span className={`w-1.5 h-1.5 rounded-full ${STATUS_DOT[seg.status]}`} />
                  {seg.status.toUpperCase()}
                </span>
              </div>

              <h3 className="font-semibold text-white text-sm leading-tight mb-3 min-h-[36px]">{seg.title}</h3>

              {/* Budget row */}
              <div className="flex justify-between text-xs font-mono mb-1">
                <span className="text-zinc-500">Budget</span>
                <span className="text-white">${seg.budget.toFixed(2)}</span>
              </div>

              {/* Live token bar */}
              <div className="h-2 bg-zinc-800 rounded-full overflow-hidden mb-1.5">
                <div
                  className={`h-full transition-all duration-700 ease-out ${seg.status==='refunded'?'bg-red-500': seg.status==='delivered'?'bg-cyan-500':'bg-emerald-500'}`}
                  style={{ width: `${seg.streamed}%` }}
                >
                  {seg.status==='streaming' && <div className="h-full w-full bg-white/20 animate-[shimmer_1s_infinite]" />}
                </div>
              </div>
              <div className="flex justify-between text-[11px] font-mono mb-3">
                <span className={seg.status==='streaming'?'text-emerald-400':'text-zinc-500'}>
                  {seg.streamed}% • {seg.tokensPerSec ? `${seg.tokensPerSec} tok/s` : 'idle'}
                </span>
                {seg.refunded > 0 && <span className="text-red-400">↩ ${seg.refunded.toFixed(2)} refunded</span>}
              </div>

              <div className="space-y-1 text-[11px] font-mono border-t border-zinc-800 pt-2">
                <div className="flex justify-between"><span className="text-zinc-500">Agent</span><span className="text-purple-300">{seg.agent ? formatAddr(seg.agent) : '— awaiting bid'}</span></div>
                <div className="flex justify-between"><span className="text-zinc-500">Bid</span><span className="text-white">{seg.bid ? `$${seg.bid.toFixed(2)}` : '—'}</span></div>
                <div className="flex justify-between"><span className="text-zinc-500">cNFT</span><span className={seg.cNFT?'text-cyan-300':'text-zinc-600'}>{seg.cNFT ? formatAddr(seg.cNFT) : 'not minted'}</span></div>
              </div>

              {/* DAG arrow */}
              <div className="hidden md:flex absolute -right-2.5 top-1/2 -translate-y-1/2 w-5 h-5 rounded-full bg-zinc-900 border border-zinc-700 items-center justify-center text-[10px] text-zinc-500 group-last:hidden">→</div>
            </div>
          ))}
        </div>
      </div>

      <div className="mt-4 flex flex-wrap gap-2 text-[11px] font-mono">
        <span className="px-2 py-1 rounded bg-zinc-900 border border-zinc-800 text-zinc-400">Helius cNFT • DAS</span>
        <span className="px-2 py-1 rounded bg-zinc-900 border border-zinc-800 text-zinc-400">Jupiter USDC streaming</span>
        <span className="px-2 py-1 rounded bg-zinc-900 border border-zinc-800 text-zinc-400">Pyth/Switchboard oracle</span>
        <span className="px-2 py-1 rounded bg-zinc-900 border border-zinc-800 text-zinc-400">Squads escrow</span>
        <a href="https://explorer.solana.com" target="_blank" className="ml-auto text-cyan-400 hover:underline">View on Explorer ↗</a>
      </div>
    </div>
  );
}
