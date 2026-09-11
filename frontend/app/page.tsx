import DagVisualization from '../components/DagVisualization';

export const metadata = {
  title: 'Colosseum Protocol — Streaming DAG',
  description: 'Decompose prompts into 5 segments, mint cNFTs, stream USDC to agents, refund on failure.',
};

export default function Page() {
  return (
    <main className="min-h-screen bg-black text-white">
      {/* Nav */}
      <nav className="sticky top-0 z-10 backdrop-blur bg-black/70 border-b border-zinc-900">
        <div className="max-w-6xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-cyan-400 to-purple-600 flex items-center justify-center font-bold text-sm">◈</div>
            <span className="font-semibold tracking-tight">COLOSSEUM PROTOCOL</span>
            <span className="hidden sm:inline text-xs px-2 py-1 rounded-full bg-zinc-900 border border-zinc-800 text-zinc-400">Frontier • Devnet</span>
          </div>
          <div className="flex items-center gap-2 text-xs font-mono">
            <span className="hidden md:inline text-zinc-500">Squads escrow:</span>
            <span className="px-2 py-1 rounded bg-zinc-900 border border-zinc-800 text-cyan-300">Sq...3x9p</span>
            <button className="px-4 py-2 rounded-full bg-white text-black font-semibold hover:bg-zinc-200 transition">Connect Wallet</button>
          </div>
        </div>
      </nav>

      <div className="max-w-6xl mx-auto px-6 py-8">
        {/* Hero + Prompt input */}
        <div className="grid lg:grid-cols-5 gap-6 mb-8">
          <div className="lg:col-span-3 rounded-2xl bg-zinc-900 border border-zinc-800 p-6">
            <h1 className="text-2xl font-bold tracking-tight mb-1">Prompt → DAG → Agents → Delivery</h1>
            <p className="text-sm text-zinc-400 mb-4">Type a prompt. We categorize into 5 segments, mint cNFTs (Helius), escrow USDC (Jupiter), stream per-token (Pyth-verified).</p>

            <label className="text-xs font-mono tracking-widest text-zinc-500 uppercase">Your Prompt</label>
            <textarea
              placeholder="e.g., Build a Solana NFT marketplace with auction, royalties, and cNFT compression..."
              className="mt-2 w-full h-28 rounded-xl bg-black border border-zinc-800 p-4 text-sm placeholder:text-zinc-600 focus:outline-none focus:border-cyan-500/50 resize-none"
              defaultValue=""
            />
            <div className="mt-3 flex flex-wrap gap-2">
              <button className="px-5 py-2.5 rounded-full bg-gradient-to-r from-cyan-500 to-purple-600 font-semibold text-sm hover:opacity-90 transition">▶ Categorize & Mint cNFTs</button>
              <button className="px-5 py-2.5 rounded-full bg-zinc-800 border border-zinc-700 text-sm font-mono hover:bg-zinc-700 transition">Simulate Live</button>
              <span className="ml-auto text-xs font-mono text-zinc-500 self-center">~1.2s LLM categorize • 0.002 SOL mint</span>
            </div>

            <div className="mt-4 grid grid-cols-3 gap-2 text-xs font-mono">
              <div className="rounded-lg bg-black border border-zinc-800 p-2.5"><div className="text-zinc-500">Gateway</div><div className="text-emerald-400">● LLM Gateway OK</div></div>
              <div className="rounded-lg bg-black border border-zinc-800 p-2.5"><div className="text-zinc-500">Oracle</div><div className="text-emerald-400">● Pyth/Switchboard</div></div>
              <div className="rounded-lg bg-black border border-zinc-800 p-2.5"><div className="text-zinc-500">Explorer</div><div className="text-cyan-400">View cNFTs ↗</div></div>
            </div>
          </div>

          <div className="lg:col-span-2 rounded-2xl bg-gradient-to-br from-zinc-900 to-black border border-zinc-800 p-6">
            <div className="text-xs font-mono tracking-widest text-zinc-500 uppercase mb-3">How it wins</div>
            <ul className="space-y-2.5 text-sm">
              <li className="flex gap-2"><span className="text-cyan-400">✓</span> <span><b>Frontier</b> — Agentic execution, not marketplace</span></li>
              <li className="flex gap-2"><span className="text-purple-400">✓</span> <span>Helius cNFT + DAS — every segment is a compressed NFT</span></li>
              <li className="flex gap-2"><span className="text-emerald-400">✓</span> <span>Jupiter USDC — streaming, not lump sum</span></li>
              <li className="flex gap-2"><span className="text-amber-400">✓</span> <span>Pyth/Switchboard — oracle-verified delivery</span></li>
              <li className="flex gap-2"><span className="text-zinc-400">✓</span> <span>Squads — multisig escrow + refund</span></li>
            </ul>
            <div className="mt-4 p-3 rounded-xl bg-black border border-zinc-800">
              <div className="text-xs font-mono text-zinc-500">Live demo: 90 sec • No slides • Real txs</div>
              <div className="text-xs font-mono text-zinc-600 mt-1">Explorer links per segment → judges verify on-chain</div>
            </div>
          </div>
        </div>

        {/* DAG Visualization */}
        <div className="rounded-2xl bg-zinc-900/50 border border-zinc-800 p-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="font-semibold">Streaming DAG — 5 Segments</h2>
            <span className="text-xs font-mono px-2 py-1 rounded-full bg-emerald-500/10 border border-emerald-500/30 text-emerald-400">LIVE</span>
          </div>
          <DagVisualization isLive />
        </div>

        {/* Footer links */}
        <div className="mt-6 flex flex-wrap gap-3 text-xs font-mono text-zinc-500">
          <a className="hover:text-white" href="#">Docs</a>
          <span>•</span>
          <a className="hover:text-white" href="#">GitHub</a>
          <span>•</span>
          <a className="hover:text-white" href="#">Helius DAS</a>
          <span>•</span>
          <a className="hover:text-white" href="#">Jupiter API</a>
          <span>•</span>
          <a className="hover:text-white" href="#">Squads</a>
          <span className="ml-auto">Built for Colosseum Frontier • Ship fast, stream faster</span>
        </div>
      </div>
    </main>
  );
}
