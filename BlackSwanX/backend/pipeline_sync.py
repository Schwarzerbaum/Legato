"""Synchronous pipeline runner for Flask.

Since Flask is sync and our NEXUS pipeline is async,
this module bridges the gap using asyncio.run().
Runs the full pipeline: crawl -> compress -> assassin -> swarm -> elites -> delta -> report.
"""
import asyncio
import json
import threading
import time
import sqlite3
import os
import httpx

# Use same DB path as app_simple.py
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "blackswanx.db")
OLLAMA_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")

# Models
SWARM_MODEL = "llama3.2:3b"
ASSASSIN_MODEL = "phi4:14b"
NEXUS_MODEL = "mistral-small:24b"


def _db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _update_status(topic_id, status):
    conn = _db()
    conn.execute("UPDATE topics SET status=? WHERE id=?", (status, topic_id))
    conn.commit()
    conn.close()


def _select_agents(query):
    """Auto-select relevant agents based on the topic. Returns list of agent IDs."""
    q = query.lower()

    # Always active (core)
    active = ["provocateur", "whale", "catalyst", "nexus", "blackswan_assassin", "chaos_math", "street_hustler"]

    # Finance keywords
    if any(k in q for k in ["stock", "market", "crash", "bitcoin", "crypto", "price", "invest", "fund",
                              "ipo", "earnings", "nvidia", "tesla", "trading", "etf", "bond", "inflation"]):
        active += ["economist", "market_analyst", "trader", "quant_analyst", "monte_carlo",
                    "boom_bust_historian", "value_investor", "whale_tracker", "panic_seller",
                    "institutional_investor", "crypto_defi"]

    # Startup / VC keywords
    if any(k in q for k in ["startup", "founder", "raise", "funding", "vc", "yc", "pitch", "valuation",
                              "series a", "unicorn", "bootstrap", "saas", "mrr", "arr"]):
        active += ["vc", "pitch_deck", "cfo_financial", "fundraising", "therapist"]

    # Tech keywords
    if any(k in q for k in ["ai", "software", "developer", "code", "platform", "app", "cloud",
                              "gpu", "model", "llm", "agent", "automation", "robot"]):
        active += ["tech_analyst", "regulatory"]

    # Geopolitics
    if any(k in q for k in ["war", "china", "russia", "sanctions", "election", "policy", "regulation",
                              "government", "ban", "tariff", "nato"]):
        active += ["geopolitics", "regulatory"]

    # Social / Culture
    if any(k in q for k in ["tiktok", "viral", "social media", "influencer", "brand", "cancel",
                              "gen z", "culture", "trend", "meme"]):
        active += ["social_impact", "gen_z_decoder"]

    # Career
    if any(k in q for k in ["career", "job", "quit", "salary", "hire", "mba", "resume", "remote work"]):
        active += ["career_strategist", "therapist"]

    # Health
    if any(k in q for k in ["health", "vaccine", "pharma", "fda", "drug", "pandemic", "medical"]):
        active += ["regulatory"]

    # Dedupe
    return list(dict.fromkeys(active))


def _get_agent_display_info(agent_ids):
    """Get display info for active agents from the registry."""
    # Map of known elite agents
    elite_map = {
        "provocateur": {"name": "Agent Provocateur", "emoji": "⚡", "role": "Disruption finder"},
        "whale": {"name": "Sentiment Whale", "emoji": "◈", "role": "Crowd reader"},
        "catalyst": {"name": "Catalyst", "emoji": "◉", "role": "Flip-event predictor"},
        "nexus": {"name": "NEXUS Orchestrator", "emoji": "🧠", "role": "DAG Brain"},
        "blackswan_assassin": {"name": "BlackSwan Assassin", "emoji": "☠", "role": "Kill shot finder"},
        "chaos_math": {"name": "Chaos Mathematician", "emoji": "🦋", "role": "Tipping points & cascades"},
        "street_hustler": {"name": "Street Smart Hustler", "emoji": "💪", "role": "Reality check"},
        "economist": {"name": "Chief Economist", "emoji": "📊", "role": "Macro forces"},
        "market_analyst": {"name": "Market Analyst", "emoji": "📈", "role": "Asset pricing & flows"},
        "trader": {"name": "Floor Trader", "emoji": "📉", "role": "Short-term tactics"},
        "quant_analyst": {"name": "Quant Analyst", "emoji": "📐", "role": "Numbers & probabilities"},
        "monte_carlo": {"name": "Monte Carlo Simulator", "emoji": "🎲", "role": "10K scenario simulation"},
        "boom_bust_historian": {"name": "Boom & Bust Historian", "emoji": "📉", "role": "Minsky cycle stage"},
        "value_investor": {"name": "Value Investor", "emoji": "🦉", "role": "Buffett margin of safety"},
        "whale_tracker": {"name": "Whale Tracker", "emoji": "🐋", "role": "Smart money flows"},
        "panic_seller": {"name": "Panic Seller", "emoji": "😱", "role": "Retail emotion signal"},
        "institutional_investor": {"name": "Institutional Investor", "emoji": "🏛️", "role": "$5B fund perspective"},
        "crypto_defi": {"name": "Crypto Strategist", "emoji": "₿", "role": "On-chain & DeFi"},
        "vc": {"name": "VC Partner", "emoji": "🚀", "role": "Startup evaluation"},
        "pitch_deck": {"name": "Pitch Specialist", "emoji": "📋", "role": "Investable narrative"},
        "cfo_financial": {"name": "CFO", "emoji": "📊", "role": "Unit economics & runway"},
        "fundraising": {"name": "Fundraising Strategist", "emoji": "💰", "role": "Cap table & terms"},
        "tech_analyst": {"name": "Tech Analyst", "emoji": "💻", "role": "Adoption curves"},
        "regulatory": {"name": "Regulatory Analyst", "emoji": "⚖️", "role": "Legal & compliance risk"},
        "geopolitics": {"name": "Geopolitical Strategist", "emoji": "🌍", "role": "State actor analysis"},
        "social_impact": {"name": "Social Impact Analyst", "emoji": "👥", "role": "Cultural dynamics"},
        "gen_z_decoder": {"name": "Gen Z Decoder", "emoji": "📱", "role": "Vibe check & virality"},
        "therapist": {"name": "Therapist", "emoji": "🧘", "role": "Cognitive distortion detection"},
        "career_strategist": {"name": "Career Strategist", "emoji": "🎯", "role": "Career optimization"},
    }
    result = []
    for aid in agent_ids:
        if aid in elite_map:
            result.append({**elite_map[aid], "id": aid})
    return result


def _ollama_chat(prompt, system="", model=NEXUS_MODEL, json_mode=False):
    """Synchronous Ollama chat call."""
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    body = {"model": model, "messages": messages, "stream": False}
    if json_mode:
        body["format"] = "json"

    resp = httpx.post(f"{OLLAMA_URL}/api/chat", json=body, timeout=600)
    resp.raise_for_status()
    return resp.json()["message"]["content"]


def _ollama_flush(model):
    """Flush model from RAM."""
    try:
        httpx.post(f"{OLLAMA_URL}/api/generate", json={"model": model, "prompt": "", "keep_alive": 0}, timeout=10)
    except Exception:
        pass


def run_pipeline_background(topic_id, query):
    """Run the full pipeline in a background thread."""
    thread = threading.Thread(target=_run_pipeline, args=(topic_id, query), daemon=True)
    thread.start()
    return thread


def _run_pipeline(topic_id, query):
    """The actual pipeline — runs in a background thread."""
    try:
        # === STAGE 1: CRAWL ===
        _update_status(topic_id, "crawling")
        posts = []

        # Try ddgs (new package) first, fallback to duckduckgo_search
        try:
            from ddgs import DDGS
        except ImportError:
            from duckduckgo_search import DDGS

        try:
            ddgs = DDGS()
            for r in ddgs.text(query, max_results=30):
                posts.append({
                    "platform": "web",
                    "content": f"{r.get('title', '')}. {r.get('body', '')}",
                    "url": r.get("href", ""),
                })
            for r in ddgs.news(query, max_results=20):
                posts.append({
                    "platform": "news",
                    "content": f"{r.get('title', '')}. {r.get('body', '')}",
                    "url": r.get("url", ""),
                })
        except Exception as e:
            print(f"DuckDuckGo error: {e}")

        # Reddit
        try:
            reddit_resp = httpx.get(
                f"https://www.reddit.com/search.json?q={query}&sort=relevance&limit=30",
                headers={"User-Agent": "BlackSwanX/0.1"},
                timeout=15
            )
            if reddit_resp.status_code == 200:
                for post in reddit_resp.json().get("data", {}).get("children", []):
                    d = post.get("data", {})
                    posts.append({
                        "platform": "reddit",
                        "content": f"{d.get('title', '')}. {d.get('selftext', '')[:300]}",
                        "url": f"https://reddit.com{d.get('permalink', '')}",
                    })
        except Exception as e:
            print(f"Reddit error: {e}")

        # Hacker News (free Algolia API)
        try:
            hn_resp = httpx.get(
                f"https://hn.algolia.com/api/v1/search?query={query}&tags=story&hitsPerPage=20",
                timeout=15
            )
            if hn_resp.status_code == 200:
                for hit in hn_resp.json().get("hits", []):
                    posts.append({
                        "platform": "hackernews",
                        "content": f"{hit.get('title', '')}. {(hit.get('story_text') or '')[:200]}",
                        "url": hit.get("url", f"https://news.ycombinator.com/item?id={hit.get('objectID', '')}"),
                    })
        except Exception as e:
            print(f"HN error: {e}")

        # YouTube (public search, extract video titles)
        try:
            yt_resp = httpx.get(
                f"https://www.youtube.com/results?search_query={query}",
                timeout=15,
                headers={"User-Agent": "Mozilla/5.0", "Accept-Language": "en-US"}
            )
            if yt_resp.status_code == 200:
                import re as _re
                titles = _re.findall(r'"title":\{"runs":\[\{"text":"([^"]{10,100})"', yt_resp.text)
                for title in titles[:10]:
                    posts.append({"platform": "youtube", "content": f"[VIDEO] {title}", "url": ""})
        except Exception as e:
            print(f"YouTube error: {e}")

        _save_live_event(topic_id, "crawl", {"posts": len(posts), "platforms": list(set(p["platform"] for p in posts))})

        # === AUTO-SELECT RELEVANT AGENTS ===
        active_agents = _select_agents(query)
        active_agents_info = _get_agent_display_info(active_agents)
        _save_live_event(topic_id, "agents_selected", {
            "count": len(active_agents_info),
            "agents": active_agents_info
        })

        if len(posts) < 5:
            _update_status(topic_id, "failed")
            _save_result(topic_id, {"error": "Not enough data found", "posts": len(posts)})
            return

        # Save post count
        conn = _db()
        conn.execute("INSERT INTO raw_posts (topic_id, platform, content, url) VALUES (?,?,?,?)",
                      (topic_id, "summary", f"Crawled {len(posts)} posts", ""))
        conn.commit()
        conn.close()

        # === STAGE 2: COMPRESS (simplified — summarize via LLM instead of HDBSCAN) ===
        _update_status(topic_id, "analyzing")

        posts_text = "\n".join([f"[{p['platform']}] {p['content'][:200]}" for p in posts[:20]])

        vibes = _ollama_chat(
            prompt=f"Topic: {query}\n\nPosts:\n{posts_text}\n\nCompress these into 5 Social Personas (opinion groups). For each: name, core_belief, sentiment (-1 to 1), emotion, post_count estimate.",
            system="You compress social data into 5 Personas. Output JSON array of 5 objects with: label, core_belief, sentiment, emotion, post_count.",
            model=SWARM_MODEL,
            json_mode=True,
        )

        _ollama_flush(SWARM_MODEL)

        # === STAGE 3: ASSASSIN'S MARK ===
        _update_status(topic_id, "assassin")

        kill_shot = _ollama_chat(
            prompt=f"Topic: {query}\n\nSocial Personas:\n{vibes[:1000]}\n\nFind the Kill Shot. What Low-Probability High-Impact event would collapse the current narrative?",
            system="""You are the BlackSwan Assassin. Find the LPHI event nobody is talking about.
Output JSON: {"trigger": "...", "cascade": ["step1", "step2", "step3"], "probability": 0.0-0.2, "impact_score": 0.8-1.0, "antifragile_play": "how to profit from collapse"}""",
            model=ASSASSIN_MODEL,
            json_mode=True,
        )

        _ollama_flush(ASSASSIN_MODEL)

        _save_live_event(topic_id, "assassin", {"kill_shot": kill_shot[:500]})

        # === STAGE 4: SHADOW SWARM (200 citizens in waves of 10) ===
        _update_status(topic_id, "simulating")

        # Force diversity: 30% bullish, 30% bearish, 40% mixed = 200 total
        bullish_personas = [
            # Finance optimists (20)
            "a hyped VC intern who sees opportunity in everything",
            "a tech-optimist startup founder who believes all disruption is good",
            "a growth equity investor who just needs to see 3x TAM",
            "an early crypto adopter who got rich on ETH and thinks everything moons",
            "a YC partner who has funded 3 unicorns this quarter",
            "an AI researcher who is excited about every breakthrough",
            "a bullish Wall Street analyst upgrading everything to BUY",
            "a Silicon Valley product manager who thinks tech solves everything",
            "a Gen Z influencer who hypes every new trend for engagement",
            "a business school student who just read The Innovator's Dilemma",
            "an angel investor who FOMO-invests in every hot deal",
            "a LinkedIn thought leader who posts 'This changes everything' daily",
            "a tech journalist writing a puff piece for clicks",
            "a retail investor who just discovered growth stocks",
            "a futurist who thinks we're 5 years from singularity",
            # Sector optimists (15)
            "a biotech CEO who just got FDA fast-track designation",
            "a renewable energy evangelist who sees oil dying within a decade",
            "a fintech founder who thinks banks are dinosaurs waiting to die",
            "a gaming industry analyst who sees metaverse as inevitable",
            "a quantum computing researcher who thinks the breakthrough is 3 years away",
            "an EdTech founder who believes AI tutors will replace schools",
            "a SpaceX fanboy who thinks Mars colonization drives all innovation",
            "a DeFi yield farmer who made 200% APY last month",
            "a robotics engineer who sees humanoid robots in every home by 2030",
            "an emerging markets fund manager who thinks Africa is the next China",
            "a 25-year-old who turned $5K into $500K on options and thinks they're a genius",
            "a corporate innovation VP who just convinced the board to invest in AI",
            "a SaaS founder who just hit $1M ARR and thinks $100M is inevitable",
            "an electric vehicle analyst who sees Tesla dominating for decades",
            "a Web3 maximalist who thinks everything will be decentralized",
            # Cultural optimists (10)
            "a TikTok creator with 2M followers who sees infinite opportunity in creator economy",
            "a remote work advocate who thinks offices are dead forever",
            "a digital nomad earning $200K while traveling the world",
            "a meditation app founder who thinks wellness is a trillion-dollar market",
            "a podcast host with growing audience who thinks audio is the future",
            "an NFT artist who sold a piece for $50K and believes digital art is the new art",
            "a social enterprise founder who thinks impact investing will save capitalism",
            "an immigrant founder who escaped poverty and believes tech creates unlimited opportunity",
            "a college dropout who built a $10M business and thinks education is broken",
            "a longevity researcher who thinks we'll live to 150 and the market hasn't priced it in",
            # Regional optimists (15)
            "an Indian SaaS founder who sees India as the next Silicon Valley",
            "a Dubai crypto fund manager who thinks MENA is the new financial hub",
            "a Singapore-based family office manager bullish on Southeast Asia",
            "a Korean gaming executive who sees K-content conquering the world",
            "a Brazilian fintech user who skipped traditional banking entirely",
            "a Nigerian mobile money operator who sees Africa leapfrogging the West",
            "a Vietnamese factory owner pivoting to AI-assisted manufacturing",
            "an Estonian e-resident who runs a global business from a laptop",
            "a Chinese AI researcher who thinks China will lead AI within 5 years",
            "a German Mittelstand owner who sees Industry 4.0 as existential opportunity",
            "an Israeli cybersecurity founder who knows every government wants their tech",
            "a Kenyan M-Pesa power user who thinks mobile-first economies will dominate",
            "a Mexican nearshoring consultant who sees supply chains moving to LATAM",
            "a Polish game developer who thinks Eastern Europe is the new game dev hub",
            "an Australian mining executive who thinks rare earth demand will 10x",
        ]
        bearish_personas = [
            # Finance pessimists (20)
            "a cynical Reddit trader who has seen every hype cycle crash",
            "a 67-year-old value investor who only buys below book value",
            "a short seller who makes money finding fraud and hype",
            "a regulatory lawyer who sees legal risk in everything",
            "a Nassim Taleb disciple who thinks everyone underestimates tail risk",
            "a privacy activist who opposes all surveillance tech",
            "a burned ex-startup employee who lost everything in a pivot",
            "a conservative pension fund manager who only wants 4% returns",
            "a cybersecurity researcher who finds vulnerabilities in everything",
            "a government regulator who thinks the industry moves too fast",
            "a journalist investigating corporate fraud",
            "a union organizer worried about job displacement",
            "a philosophy professor questioning the ethics of it all",
            "a debt analyst who sees leverage and risk everywhere",
            "a climate activist who thinks tech growth is unsustainable",
            "a former Enron employee who sees fraud patterns everywhere",
            "a bankruptcy lawyer who knows exactly how companies die",
            "a credit rating analyst who has been downgrading companies all year",
            "a forensic accountant who specializes in uncovering creative accounting",
            "a political risk consultant who sees geopolitical instability everywhere",
            # Sector skeptics (15)
            "a traditional banker who thinks crypto is a ponzi scheme with extra steps",
            "an oil executive who thinks green energy is a government-subsidized fantasy",
            "a Luddite professor who wrote a book about why technology makes us worse off",
            "a healthcare policy expert who thinks medical AI will cause more harm than good",
            "an ex-Meta employee who thinks the metaverse was a $50B waste",
            "a taxi driver who lost everything to Uber and distrusts all disruption",
            "a newspaper editor who watched their industry die and sees the same pattern",
            "a librarian who thinks AI-generated content is intellectual pollution",
            "a farmer who has been promised 'precision agriculture' for 20 years with nothing to show",
            "a veteran teacher who thinks EdTech has made students worse, not better",
            "an artist who believes AI art is theft and will destroy creative careers",
            "a factory worker whose job was automated and who is now driving for DoorDash",
            "a real estate agent who thinks the housing market is a house of cards",
            "a retired general who thinks autonomous weapons will cause a war",
            "a parent who is terrified of what social media is doing to their children",
            # Macro bears (15)
            "a gold bug who has been predicting dollar collapse since 2008",
            "a demographics researcher who sees aging populations killing growth",
            "a water scarcity expert who thinks resource wars are coming within a decade",
            "a debt clock watcher who thinks $35T national debt will cause a reckoning",
            "an inflation hawk who thinks central banks have lost control permanently",
            "a deglobalization analyst who sees trade wars fragmenting the world economy",
            "a pandemic preparedness expert who thinks the next pandemic will be worse",
            "a nuclear proliferation researcher who thinks the risk of nuclear war is highest since 1962",
            "a coral reef scientist who sees ecosystem collapse as an economic time bomb",
            "a housing affordability researcher who thinks an entire generation is locked out of wealth",
            "a food security analyst who thinks agricultural systems are one drought from crisis",
            "an AI safety researcher who thinks we're building systems we can't control",
            "a wealth inequality researcher who thinks social instability is the inevitable result",
            "an energy grid analyst who thinks infrastructure can't support the AI compute boom",
            "a supply chain expert who thinks just-in-time is one disruption from total collapse",
        ]
        mixed_personas = [
            # Analytical centrists (20)
            "a pragmatic CFO who only cares about unit economics and cash flow",
            "a 45-year-old middle manager at a Fortune 500 watching from the sidelines",
            "a hedge fund analyst who sees both the bull and bear case",
            "an economist who sees macro forces pushing both directions",
            "a patent lawyer who sees IP value but also legal exposure",
            "a supply chain manager who knows where the bottlenecks are",
            "a data scientist who wants to see the numbers before deciding",
            "an insurance actuary who prices risk for a living",
            "a retired military strategist who thinks in scenarios not predictions",
            "a healthcare executive evaluating tech adoption carefully",
            "a real estate developer who thinks in 10-year cycles",
            "a central banker weighing inflation against innovation",
            "a teacher saving for retirement who reads Morningstar reports",
            "a small business owner who is cautiously interested",
            "an emerging markets analyst who compares to China and India",
            "a geopolitical strategist who factors in US-China tensions",
            "a media executive deciding whether to adopt or resist",
            "a venture debt provider who needs to see cash flow, not dreams",
            "a competition lawyer evaluating antitrust implications",
            "a sociologist studying how technology changes behavior",
            # Professional observers (20)
            "a management consultant who has seen this pattern at 50 companies",
            "a university provost evaluating whether to invest in this technology",
            "a museum curator wondering how this changes cultural preservation",
            "a city planner thinking about infrastructure implications",
            "an immigration lawyer seeing how this affects global talent flows",
            "a sports analytics director exploring crossover applications",
            "a logistics coordinator evaluating efficiency vs disruption tradeoffs",
            "a nonprofit director weighing impact potential vs mission drift",
            "a trade union negotiator preparing for the next collective bargaining round",
            "a church pastor wondering how this affects their community",
            "a school principal deciding whether to adopt or ban this",
            "a prison reform advocate looking at rehabilitation applications",
            "a disability rights activist evaluating accessibility implications",
            "a war correspondent who has seen how technology changes conflict zones",
            "a divorce lawyer who sees how financial stress from disruption breaks families",
            "a professional poker player who evaluates expected value for a living",
            "an archaeologist who studies how past civilizations adapted to disruption",
            "a stand-up comedian who spots absurdity and hypocrisy instantly",
            "a hospice nurse who has perspective on what actually matters in life",
            "a professional negotiator who reads people and incentives for a living",
            # Demographic diversity (20)
            "a 19-year-old college freshman who gets all news from TikTok and group chats",
            "a 35-year-old working mother juggling career ambitions with childcare costs",
            "a 50-year-old immigrant who built a business from nothing in a new country",
            "a 70-year-old retired engineer who has seen 5 technology hype cycles come and go",
            "a 28-year-old gig economy worker with no savings and no safety net",
            "a 40-year-old government bureaucrat who processes permits and sees inefficiency daily",
            "a 22-year-old art school graduate drowning in student debt with no job prospects",
            "a 55-year-old small-town mayor trying to keep their community alive",
            "a 33-year-old stay-at-home parent who day-trades during nap time",
            "a 45-year-old truck driver worried about self-driving trucks",
            "a 60-year-old doctor who has practiced medicine for 30 years and distrusts AI diagnostics",
            "a 24-year-old influencer whose entire income depends on algorithm changes",
            "a 38-year-old firefighter who thinks about risk and safety every single day",
            "a 52-year-old accountant who has audited companies that cooked their books",
            "a 29-year-old PhD student who knows more about the topic than anyone but has no money",
            "a 65-year-old grandmother who just learned to use a smartphone last year",
            "a 31-year-old veteran who transitioned to tech after military service",
            "a 42-year-old middle school teacher in a rural town with bad internet",
            "a 26-year-old barista with a philosophy degree who argues about everything",
            "a 48-year-old real estate agent who measures everything in monthly payments",
            # Wildcard personas (20)
            "a prepper who has a bunker and 6 months of food stored",
            "a flat earther who distrusts all institutional narratives",
            "a former cult member who recognizes manipulation patterns instantly",
            "a professional gambler who calculates odds on everything",
            "a retired CIA analyst who sees hidden agendas in every public statement",
            "a Burning Man regular who thinks decentralization is the answer to everything",
            "a monk who spent 10 years in silence and now questions modern attachment",
            "a competitive esports player who thinks reaction speed matters more than wisdom",
            "an Amish farmer who chose to reject technology and is happy about it",
            "a billionaire's personal assistant who has seen how the ultra-rich actually think",
            "a professional fact-checker who debunks misinformation for a living",
            "a tarot card reader whose clients are mostly anxious executives",
            "a submarine captain who makes decisions with incomplete information under pressure",
            "a wildlife biologist who studies how ecosystems collapse and recover",
            "a bankruptcy trustee who picks apart failed companies for a living",
            "a midwife who has learned that the best-laid plans rarely survive first contact",
            "a graffiti artist who sees the streets as the real pulse of a city",
            "a prison warden who understands human behavior under extreme constraints",
            "a sommelier who knows that 90% of people can't tell expensive from cheap",
            "a storm chaser who runs toward danger while everyone else runs away",
        ]

        # Citizen count: 50 for fast mode, 200 for deep mode
        # Fast mode (~5 min): good for demos and quick analysis
        # Deep mode (~25 min): full 200-citizen census
        CITIZEN_COUNT = int(os.environ.get("BLACKSWANX_CITIZENS", "25"))
        print(f"[SWARM] Running with {CITIZEN_COUNT} citizens")

        if CITIZEN_COUNT >= 200:
            all_personas = bullish_personas[:60] + bearish_personas[:50] + mixed_personas[:80]
        elif CITIZEN_COUNT >= 100:
            all_personas = bullish_personas[:30] + bearish_personas[:25] + mixed_personas[:45]
        elif CITIZEN_COUNT >= 50:
            all_personas = bullish_personas[:15] + bearish_personas[:15] + mixed_personas[:20]
        else:
            # Turbo mode: 25 citizens (8 bull + 8 bear + 9 mixed) — ~2 min
            all_personas = bullish_personas[:8] + bearish_personas[:8] + mixed_personas[:9]
        import random
        random.shuffle(all_personas)

        citizen_opinions = []
        wave_size = 10
        for wave_num in range(len(all_personas) // wave_size):
            wave_start = wave_num * wave_size
            wave_personas = all_personas[wave_start:wave_start + wave_size]
            _update_status(topic_id, f"simulating wave {wave_num+1}/{len(all_personas)//wave_size}")

            for persona in wave_personas:
                # Determine bias instruction based on persona category
                if persona in bullish_personas:
                    bias = "You are OPTIMISTIC. Find reasons why this succeeds. Your gut says YES."
                elif persona in bearish_personas:
                    bias = "You are SKEPTICAL. Find reasons why this fails. Your gut says NO."
                else:
                    bias = "You are ANALYTICAL. Weigh both sides. Your gut is uncertain."

                opinion = _ollama_chat(
                    prompt=f"Topic: {query}\nContext: {vibes[:400]}\nHidden risk: {kill_shot[:200]}\n\nReact based on your persona. Be specific and opinionated.",
                    system=f"You are {persona}. {bias} Do NOT be balanced — pick a side based on your character. Output JSON: {{\"gut_feeling\": \"one raw sentence\", \"sentiment\": -1.0 to 1.0, \"emotion\": \"fear|greed|anger|hope|apathy|panic|euphoria|caution|excitement|skepticism\", \"hot_take\": \"your most extreme opinion in one sentence\"}}",
                    model=SWARM_MODEL,
                    json_mode=True,
                )
                citizen_opinions.append({"persona": persona, "response": opinion})

                # Save each citizen as it arrives (for live feed)
                _save_live_event(topic_id, "citizen", {
                    "persona": persona,
                    "response": opinion,
                    "wave": wave_num + 1,
                    "index": len(citizen_opinions),
                })

            # Flush GPU between waves
            _ollama_flush(SWARM_MODEL)

        # === STAGE 5: CALCULATE REAL DISSONANCE (from data, not LLM) ===
        _update_status(topic_id, "calculating")

        # Parse citizen sentiments
        sentiments = []
        emotions = {}
        for c in citizen_opinions:
            try:
                r = json.loads(c["response"]) if isinstance(c["response"], str) else c["response"]
                s = float(r.get("sentiment", 0))
                sentiments.append(s)
                emo = r.get("emotion", "neutral")
                emotions[emo] = emotions.get(emo, 0) + 1
            except:
                pass

        total = max(len(sentiments), 1)
        bulls = sum(1 for s in sentiments if s > 0.2)
        bears = sum(1 for s in sentiments if s < -0.2)
        neutrals = total - bulls - bears
        avg_sentiment = sum(sentiments) / total
        bull_pct = round(bulls / total * 100, 1)
        bear_pct = round(bears / total * 100, 1)

        # Parse kill shot probability
        try:
            kill_data = json.loads(kill_shot) if isinstance(kill_shot, str) else kill_shot
            kill_prob = float(kill_data.get("probability", 0.1))
            kill_impact = float(kill_data.get("impact_score", 0.5))
            kill_trigger = kill_data.get("trigger", "Unknown")
        except:
            kill_prob = 0.1
            kill_impact = 0.5
            kill_trigger = str(kill_shot)[:200]

        # DELTA 1: THE TRAP (sentiment polarity)
        # How one-sided is the crowd? More extreme = more trap
        sentiment_extremity = abs(avg_sentiment)
        the_trap = round(sentiment_extremity * 100, 1)
        trap_desc = f"Crowd is {bull_pct}% bull / {bear_pct}% bear. " + (
            "Extreme consensus = classic trap setup." if the_trap > 60 else
            "Moderate split = healthy debate." if the_trap < 30 else
            "Leaning one way but not extreme."
        )

        # DELTA 2: THE BLINDSPOT (consensus vs kill shot)
        consensus_strength = max(bull_pct, bear_pct)
        kill_feasibility = kill_prob * kill_impact * 100
        the_blindspot = round(abs(consensus_strength - (100 - kill_feasibility)), 1)
        blindspot_desc = f"Consensus at {consensus_strength}% but kill shot feasibility is {kill_feasibility:.0f}%. " + (
            "CRITICAL — crowd ignoring viable threat." if the_blindspot > 50 else
            "Moderate gap — some awareness of risk." if the_blindspot > 25 else
            "Low gap — risk mostly priced in."
        )

        # DELTA 3: THE CHAOS (sentiment variance)
        if sentiments:
            mean_s = sum(sentiments) / len(sentiments)
            variance = sum((s - mean_s)**2 for s in sentiments) / len(sentiments)
            the_chaos = round(min(variance * 100, 100), 1)
        else:
            the_chaos = 50
        chaos_desc = f"Sentiment variance: {the_chaos:.0f}. " + (
            "MAXIMUM CHAOS — citizens fundamentally disagree." if the_chaos > 50 else
            "Moderate disagreement — no clear consensus." if the_chaos > 25 else
            "Low chaos — crowd is aligned."
        )

        # COMPOSITE SCORE
        dissonance_score = round(the_trap * 0.3 + the_blindspot * 0.4 + the_chaos * 0.3, 1)
        dissonance_score = min(100, max(0, dissonance_score))

        real_dissonance = {
            "score": dissonance_score,
            "the_trap": {"value": the_trap, "description": trap_desc},
            "the_blindspot": {"value": the_blindspot, "description": blindspot_desc},
            "the_chaos": {"value": the_chaos, "description": chaos_desc},
            "crowd": {"bulls": bulls, "bears": bears, "neutrals": neutrals, "total": total, "bull_pct": bull_pct, "bear_pct": bear_pct},
            "top_emotions": sorted(emotions.items(), key=lambda x: -x[1])[:5],
        }

        # === STAGE 6: NEXUS SYNTHESIS ===
        _update_status(topic_id, "synthesis")

        final = _ollama_chat(
            prompt=f"""TOPIC: {query}

SOCIAL PERSONAS: {vibes[:1500]}

BLACKSWAN KILL SHOT:
- Trigger: {kill_trigger}
- Probability: {kill_prob*100:.0f}%
- Impact: {kill_impact*100:.0f}%

SHADOW SWARM CENSUS ({total} citizens):
- Bulls: {bulls} ({bull_pct}%) | Bears: {bears} ({bear_pct}%) | Neutral: {neutrals}
- Average sentiment: {avg_sentiment:.2f}
- Top emotions: {emotions}

COGNITIVE DISSONANCE (calculated from data):
- Overall Score: {dissonance_score}/100
- The Trap: {trap_desc}
- The Blindspot: {blindspot_desc}
- The Chaos: {chaos_desc}

Synthesize into a Decision-Ready Map. The dissonance data above is REAL — do not override it. Focus on the LINCHPIN and ANTIFRAGILE PLAY.""",
            system="""You are the NEXUS Orchestrator. The cognitive dissonance scores are PRE-CALCULATED from real data — do NOT change them. Your job is to interpret them and find the Linchpin.
Output JSON: {
  "linchpin": "the one thing everything depends on",
  "bull_case": "why it could succeed (2-3 sentences)",
  "kill_shot_assessment": "is the assassin's kill shot credible? why or why not?",
  "antifragile_output": "one paragraph: what to DO about this (specific, actionable)",
  "prediction": {"most_likely": "...", "best_case": "...", "worst_case": "..."},
  "pressure_points": [{"point": "...", "actionability": "high|medium|low"}],
  "confidence": 0.0-1.0
}""",
            model=ASSASSIN_MODEL,
            json_mode=True,
        )

        _ollama_flush(ASSASSIN_MODEL)

        # === STAGE 7: SONA AUDIT (Self-Learning) ===
        _update_status(topic_id, "learning")
        _save_live_event(topic_id, "system", {"message": "SONA auditing all agents — learning from this run..."})

        try:
            from backend.simulation.sona import init_sona_tables, _get_db as sona_db
            # Ensure SONA tables exist
            init_sona_tables()

            # Audit: check which citizens caught the kill shot
            sona_conn = sona_db()
            kill_trigger_words = str(kill_data.get("trigger", "")).lower().split()[:5]

            for c in citizen_opinions:
                try:
                    r = json.loads(c["response"]) if isinstance(c["response"], str) else c["response"]
                    gut = str(r.get("gut_feeling", "")).lower()
                    hot = str(r.get("hot_take", "")).lower()
                    sentiment = float(r.get("sentiment", 0))
                    persona = c.get("persona", "unknown")

                    # Did this citizen catch the kill shot risk?
                    edge_bonus = 0.0
                    if any(w in gut + " " + hot for w in kill_trigger_words if len(w) > 3):
                        edge_bonus = 0.5

                    # Was citizen contrarian during high dissonance?
                    if dissonance_score > 50 and abs(sentiment - avg_sentiment) > 0.5:
                        edge_bonus += 0.3

                    if edge_bonus > 0:
                        citizen_id = f"citizen_{persona[:30].replace(' ', '_')}"
                        sona_conn.execute(
                            "INSERT OR REPLACE INTO sona_agent_scores (agent_id, agent_type, topic_domain, quality_score, edge_case_bonus, total_weight, runs) VALUES (?,?,?,?,?,?,1)",
                            (citizen_id, "citizen", _detect_domain(query), 0.5, min(edge_bonus, 1.0), 0.5 + min(edge_bonus, 1.0) * 0.5, 1)
                        )
                except:
                    pass

            # Save pattern to ReasoningBank
            sona_conn.execute(
                "INSERT INTO sona_reasoning_bank (pattern_type, pattern_description, source_agent, topic_domain, confidence) VALUES (?,?,?,?,?)",
                ("prediction_run",
                 f"Topic: {query[:100]}. Dissonance: {dissonance_score}. Kill: {str(kill_data.get('trigger',''))[:100]}. Bulls: {bull_pct}% Bears: {bear_pct}%",
                 "nexus", _detect_domain(query), dissonance_score / 100)
            )
            sona_conn.commit()
            sona_conn.close()
        except Exception as e:
            print(f"SONA audit error (non-fatal): {e}")

        # === SAVE RESULTS ===
        _update_status(topic_id, "complete")
        _save_live_event(topic_id, "system", {"message": "Analysis complete! SONA has learned from this run."})
        _save_result(topic_id, {
            "vibes": vibes,
            "kill_shot": kill_shot,
            "citizen_opinions": citizen_opinions,
            "synthesis": final,
            "dissonance": real_dissonance,
            "posts_crawled": len(posts),
            "citizen_count": total,
            "bull_pct": bull_pct,
            "bear_pct": bear_pct,
            "active_agents": active_agents_info,
            "active_agent_count": len(active_agents_info),
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        _update_status(topic_id, "failed")
        _save_result(topic_id, {"error": str(e), "traceback": traceback.format_exc()})


def _save_live_event(topic_id, event_type, data):
    """Save a live event for real-time feed polling."""
    conn = _db()
    conn.execute(
        "CREATE TABLE IF NOT EXISTS live_feed (id INTEGER PRIMARY KEY AUTOINCREMENT, topic_id INTEGER, event_type TEXT, data TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"
    )
    conn.execute(
        "INSERT INTO live_feed (topic_id, event_type, data) VALUES (?,?,?)",
        (topic_id, event_type, json.dumps(data, ensure_ascii=False, default=str))
    )
    conn.commit()
    conn.close()


def get_live_feed(topic_id, after_id=0):
    """Get live feed events after a given ID (for polling)."""
    conn = _db()
    conn.execute(
        "CREATE TABLE IF NOT EXISTS live_feed (id INTEGER PRIMARY KEY AUTOINCREMENT, topic_id INTEGER, event_type TEXT, data TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"
    )
    rows = conn.execute(
        "SELECT id, event_type, data, created_at FROM live_feed WHERE topic_id=? AND id>? ORDER BY id",
        (topic_id, after_id)
    ).fetchall()
    conn.close()
    events = []
    for r in rows:
        try:
            data = json.loads(r["data"])
        except:
            data = {"raw": r["data"]}
        events.append({"id": r["id"], "type": r["event_type"], "data": data, "time": r["created_at"]})
    return events


def _save_result(topic_id, result):
    """Save pipeline result to raw_posts as JSON."""
    conn = _db()
    conn.execute(
        "INSERT INTO raw_posts (topic_id, platform, content, url) VALUES (?,?,?,?)",
        (topic_id, "result", json.dumps(result, ensure_ascii=False, default=str), "")
    )
    conn.commit()
    conn.close()


def _detect_domain(query):
    """Detect topic domain for SONA categorization."""
    q = query.lower()
    domains = {
        "finance": ["stock", "market", "trading", "bitcoin", "crypto", "price", "invest", "fund", "ipo", "earnings", "nvidia", "tesla"],
        "tech": ["ai", "software", "startup", "app", "platform", "developer", "code", "saas", "cloud", "gpu"],
        "politics": ["election", "policy", "government", "regulation", "law", "vote", "democrat", "republican"],
        "social": ["culture", "trend", "viral", "social media", "influencer", "brand", "reputation", "tiktok"],
        "geopolitics": ["war", "sanctions", "china", "russia", "trade war", "nato", "military"],
        "health": ["vaccine", "pandemic", "health", "fda", "drug", "pharma", "medical"],
        "career": ["job", "career", "salary", "hire", "quit", "startup founder", "mba", "resume"],
    }
    for domain, keywords in domains.items():
        if any(k in q for k in keywords):
            return domain
    return "general"


def get_result(topic_id):
    """Get the pipeline result for a topic."""
    conn = _db()
    row = conn.execute(
        "SELECT content FROM raw_posts WHERE topic_id=? AND platform='result' ORDER BY id DESC LIMIT 1",
        (topic_id,)
    ).fetchone()
    conn.close()
    if row:
        try:
            return json.loads(row["content"])
        except json.JSONDecodeError:
            return {"raw": row["content"]}
    return None
