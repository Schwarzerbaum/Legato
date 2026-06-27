# r/LocalLLaMA Post

**Title:** I built BlackSwanX — 174 AI experts + 200 citizen agents that predict the future adversarially. Runs entirely on Ollama. Zero API cost.

**Body:**

I've been obsessed with a question: what if instead of asking AI "what will happen?", you built a system where 200 AI citizens ARGUE about it while a BlackSwan Assassin tries to kill the consensus?

So I built **BlackSwanX** — an adversarial intelligence engine that runs 100% locally on Ollama.

**What it does:**
1. You enter any topic ("Will NVIDIA crash when the AI bubble pops?")
2. It crawls DuckDuckGo + Reddit + Hacker News + YouTube (free, no API keys)
3. A BlackSwan Assassin (phi4:14b) finds the Kill Shot — the low-probability event nobody's talking about
4. 200 citizen agents (llama3.2:3b) react with biased, emotional, human-like opinions — bulls, bears, conspiracy theorists, retired generals, submarine captains
5. A Cognitive Dissonance Matrix calculates where the crowd disagrees with the experts
6. NEXUS synthesizes everything into a Decision-Ready Map with an Antifragile Play

**The 3-model strategy (runs on 16GB M2 Pro):**
- Swarm: llama3.2:3b (200 citizens)
- Assassin: phi4:14b (kill shots)
- Nexus Brain: mistral-small:24b (synthesis)

GPU cache flushed between waves with `keep_alive: 0`. Wave-based processing (10 citizens at a time) so it doesn't brick your laptop.

**What makes it different from MiroFish/BettaFish:**
- Zero API cost (they need 2-7 API keys)
- 174 domain expert agents (CFO, Quant Analyst, Vedic Astrologer, Chaos Mathematician, Panic Seller...)
- Self-learning via SONA — the system gets smarter with every run
- Kill-Switch stress test: Fans vs Assassins battle
- Cognitive Dissonance Matrix: The Trap / The Blindspot / The Chaos

**Yes, there's a Vedic Astrologer agent.** Markets follow psychology. Psychology follows cycles. Fight me.

**Screenshots:** [See README for all 7 screenshots]

**GitHub:** https://github.com/Kalki-M/BlackSwanX

**Quick start:**
```
git clone https://github.com/Kalki-M/BlackSwanX.git
cd BlackSwanX
ollama pull llama3.2:3b && ollama pull phi4:14b
pip install -r requirements.txt
bash start.sh
```

Turbo mode finishes in ~2 minutes. No API keys, no PostgreSQL, no cloud accounts needed.

Built this in 10 days. Open source. MIT license. Roast it.
