"""Agent Registry — Auto-loads 261+ expert agents from two sources:
1. agency-agents/  — 170+ domain expert agents (marketing, engineering, sales, etc.)
2. .claude/agents/ — 87+ system agents (swarm, consensus, SPARC, V3, GitHub, etc.)

Division mapping:
Agency-agents divisions:
- academic         -> deep research, historical analysis, psychology
- design           -> brand, UX, visual strategy
- engineering      -> technical architecture, security, DevOps
- marketing        -> growth, SEO, social media, content
- paid-media       -> advertising, PPC, programmatic
- product          -> product management, prioritization, research
- project-management -> project coordination, operations
- sales            -> deal strategy, pipeline, outbound
- game-development -> game design, narrative, spatial
- spatial-computing -> XR, VR, AR
- specialized      -> legal, finance, blockchain, compliance
- support          -> analytics, infrastructure, compliance
- testing          -> QA, performance, security testing

System agents (.claude/agents) divisions:
- core             -> coder, reviewer, researcher, tester, planner
- swarm            -> hierarchical, mesh, adaptive coordinators
- consensus        -> raft, byzantine, quorum, gossip, crdt
- v3               -> security, memory, performance, integration specialists
- github           -> PR manager, repo architect, release, sync
- flow-nexus       -> app-store, auth, challenges, neural, payments, sandbox
- sparc            -> specification, pseudocode, architecture, refinement
- sublinear        -> matrix optimizer, pagerank, trading predictor
- analysis         -> code analyzer, performance analyzer
- optimization     -> performance engineer, resource allocator
- goal             -> goal planner, task orchestrator
- data             -> ML model, data pipeline
- devops           -> CI/CD, ops automation
- payments         -> agentic payments
- sona             -> SONA learning optimizer
"""
import os
import re
from pathlib import Path
from dataclasses import dataclass, field

# Source 1: agency-agents (domain experts)
_agency_candidates = [
    Path(__file__).parent.parent.parent / "agency-agents",
    Path.home() / "agency-agents",
]
AGENTS_DIR = next((p for p in _agency_candidates if p.exists()), _agency_candidates[0])

# Source 2: .claude/agents (system agents)
_system_candidates = [
    Path(__file__).parent.parent / ".claude" / "agents",  # backend/../.claude/agents
    Path(__file__).parent.parent.parent / ".claude" / "agents",  # project root
]
SYSTEM_AGENTS_DIR = next((p for p in _system_candidates if p.exists()), None)

# Division colors for UI
DIVISION_COLORS = {
    # Agency-agents divisions
    "academic": "#8b5cf6",
    "design": "#ec4899",
    "engineering": "#3b82f6",
    "marketing": "#10b981",
    "paid-media": "#f59e0b",
    "product": "#6366f1",
    "project-management": "#64748b",
    "sales": "#ef4444",
    "game-development": "#a855f7",
    "spatial-computing": "#06b6d4",
    "specialized": "#f97316",
    "support": "#14b8a6",
    "testing": "#eab308",
    # System agent divisions
    "core": "#0ea5e9",
    "swarm": "#8b5cf6",
    "consensus": "#d946ef",
    "v3": "#06b6d4",
    "github": "#1d4ed8",
    "flow-nexus": "#7c3aed",
    "sparc": "#059669",
    "sublinear": "#dc2626",
    "analysis": "#2563eb",
    "optimization": "#ea580c",
    "goal": "#16a34a",
    "data": "#0891b2",
    "devops": "#4f46e5",
    "payments": "#15803d",
    "sona": "#9333ea",
    "templates": "#64748b",
    "development": "#3b82f6",
    "documentation": "#6b7280",
    "custom": "#f59e0b",
    "architecture": "#7c3aed",
    "security": "#dc2626",
    # BlackSwanX proprietary agents
    "blackswanx": "#7c3aed",
    "ma-intel": "#dc2626",
}

# Division icons
DIVISION_ICONS = {
    "academic": "book",
    "design": "palette",
    "engineering": "code",
    "marketing": "megaphone",
    "paid-media": "dollar",
    "product": "lightbulb",
    "project-management": "clipboard",
    "sales": "handshake",
    "game-development": "gamepad",
    "spatial-computing": "vr",
    "specialized": "star",
    "support": "headphones",
    "testing": "check",
    "core": "cpu",
    "swarm": "network",
    "consensus": "vote",
    "v3": "zap",
    "github": "git-branch",
    "flow-nexus": "flow",
    "sparc": "layers",
    "sublinear": "trending-up",
    "analysis": "search",
    "optimization": "settings",
    "goal": "target",
    "data": "database",
    "devops": "server",
    "payments": "credit-card",
    "sona": "brain",
    "blackswanx": "zap",
    "ma-intel": "briefcase",
}


@dataclass
class AgentDef:
    id: str
    name: str
    description: str
    emoji: str
    vibe: str
    division: str
    color: str
    system_prompt: str  # Full markdown content as system prompt
    file_path: str


_registry: dict[str, AgentDef] = {}
_loaded = False


def _parse_frontmatter(content: str) -> tuple[dict, str]:
    """Parse YAML-like frontmatter from markdown file."""
    meta = {}
    body = content

    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= 3:
            for line in parts[1].strip().split("\n"):
                if ":" in line:
                    key, val = line.split(":", 1)
                    meta[key.strip()] = val.strip().strip('"').strip("'")
            body = parts[2].strip()

    return meta, body


def _make_id(division: str, name: str) -> str:
    """Create a URL-safe ID from division and name."""
    clean = re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')
    return f"{division}--{clean}"


def _load_from_dir(source_dir: Path, skip_dirs: set, skip_files: set) -> int:
    """Load agents from a directory into _registry. Returns count added."""
    count = 0
    for md_file in source_dir.rglob("*.md"):
        rel = md_file.relative_to(source_dir)
        parts = rel.parts
        if not parts or parts[0] in skip_dirs:
            continue
        if md_file.name in skip_files:
            continue

        try:
            content = md_file.read_text(encoding="utf-8")
        except Exception:
            continue

        meta, body = _parse_frontmatter(content)
        name = meta.get("name", md_file.stem.replace("-", " ").title())
        if not name:
            continue

        # Determine division from directory structure
        division = parts[0] if len(parts) > 1 else "specialized"

        agent_id = _make_id(str(division), name)
        # Skip if already registered (agency-agents takes priority)
        if agent_id in _registry:
            continue

        raw_color = meta.get("color", DIVISION_COLORS.get(str(division), "#6b7280"))
        color = raw_color if (raw_color and raw_color.startswith("#")) else DIVISION_COLORS.get(str(division), "#6b7280")

        # Build a vibe from description if not provided
        vibe = meta.get("vibe", "")
        desc = meta.get("description", "")
        if not vibe and desc:
            vibe = desc[:100]

        agent = AgentDef(
            id=agent_id,
            name=name,
            description=desc,
            emoji=meta.get("emoji", _default_emoji(str(division))),
            vibe=vibe,
            division=str(division),
            color=color,
            system_prompt=body,
            file_path=str(md_file),
        )
        _registry[agent_id] = agent
        count += 1
    return count


def _default_emoji(division: str) -> str:
    """Default emoji per division when not specified in frontmatter."""
    return {
        "core": "⚙️", "swarm": "🐝", "consensus": "🗳️", "v3": "⚡",
        "github": "🐙", "flow-nexus": "🌊", "sparc": "🔷", "sublinear": "📐",
        "analysis": "🔍", "optimization": "⚡", "goal": "🎯", "data": "💾",
        "devops": "🔧", "payments": "💳", "sona": "🧠", "templates": "📋",
        "development": "💻", "documentation": "📝", "custom": "✨",
        "architecture": "🏗️", "security": "🔒", "testing": "🧪",
        "academic": "📚", "design": "🎨", "engineering": "🔧",
        "marketing": "📣", "paid-media": "💰", "product": "💡",
        "project-management": "📋", "sales": "🤝", "game-development": "🎮",
        "spatial-computing": "🥽", "specialized": "⭐", "support": "🎧",
    }.get(division, "🤖")


def load_agents() -> dict[str, AgentDef]:
    """Load all agents from agency-agents/ (domain experts) and .claude/agents/ (system agents)."""
    global _registry, _loaded

    if _loaded:
        return _registry

    # --- Source 1: agency-agents (domain experts) ---
    _agency_skip_dirs = {"examples", "integrations", ".git", ".github", "scripts"}
    _agency_skip_files = {
        "README.md", "CONTRIBUTING.md", "LICENSE", "PULL_REQUEST_TEMPLATE.md",
        "EXECUTIVE-BRIEF.md", "QUICKSTART.md",
    }

    agency_count = 0
    if AGENTS_DIR.exists():
        agency_count = _load_from_dir(AGENTS_DIR, _agency_skip_dirs, _agency_skip_files)
        print(f"✓ Loaded {agency_count} domain expert agents from {AGENTS_DIR}")
    else:
        print(f"⚠ agency-agents dir not found at {AGENTS_DIR}")

    # --- Source 2: .claude/agents (system agents) ---
    _system_skip_dirs = {"browser", ".git"}
    _system_skip_files = {"README.md", "CONTRIBUTING.md"}

    system_count = 0
    if SYSTEM_AGENTS_DIR and SYSTEM_AGENTS_DIR.exists():
        system_count = _load_from_dir(SYSTEM_AGENTS_DIR, _system_skip_dirs, _system_skip_files)
        print(f"✓ Loaded {system_count} system agents from {SYSTEM_AGENTS_DIR}")
    else:
        print(f"⚠ .claude/agents dir not found")

    _loaded = True
    print(f"✓ Total: {len(_registry)} agents loaded ({agency_count} domain + {system_count} system)")
    return _registry


def get_agent(agent_id: str) -> AgentDef | None:
    """Get a specific agent by ID."""
    reg = load_agents()
    return reg.get(agent_id)


def list_agents(division: str = None) -> list[dict]:
    """List all agents, optionally filtered by division."""
    reg = load_agents()
    agents = []
    for a in reg.values():
        if division and a.division != division:
            continue
        agents.append({
            "id": a.id,
            "name": a.name,
            "emoji": a.emoji,
            "vibe": a.vibe,
            "division": a.division,
            "color": a.color,
            "description": a.description[:120],
        })
    # Sort by division then name
    agents.sort(key=lambda x: (x["division"], x["name"]))
    return agents


def list_divisions() -> list[dict]:
    """List all divisions with agent counts."""
    reg = load_agents()
    divisions = {}
    for a in reg.values():
        if a.division not in divisions:
            divisions[a.division] = {
                "name": a.division,
                "color": DIVISION_COLORS.get(a.division, "#6b7280"),
                "icon": DIVISION_ICONS.get(a.division, "star"),
                "count": 0,
            }
        divisions[a.division]["count"] += 1
    return sorted(divisions.values(), key=lambda x: -x["count"])


def search_agents(query: str, limit: int = 10) -> list[dict]:
    """Search agents by name, description, or vibe."""
    query_lower = query.lower()
    reg = load_agents()
    scored = []
    for a in reg.values():
        score = 0
        if query_lower in a.name.lower():
            score += 10
        if query_lower in a.vibe.lower():
            score += 5
        if query_lower in a.description.lower():
            score += 3
        if query_lower in a.division.lower():
            score += 2
        if score > 0:
            scored.append((score, a))

    scored.sort(key=lambda x: -x[0])
    return [
        {"id": a.id, "name": a.name, "emoji": a.emoji, "vibe": a.vibe,
         "division": a.division, "color": a.color, "score": s}
        for s, a in scored[:limit]
    ]
