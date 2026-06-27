# Contributing to BlackSwanX

Thanks for your interest in contributing. Here's how to help.

## Quick Setup for Development

```bash
git clone https://github.com/Kalki-M/BlackSwanX.git
cd BlackSwanX
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
ollama pull llama3.2:3b  # Minimum model needed
PYTHONPATH=. python backend/app_simple.py
```

## What We Need Most

### High Priority
- **Deeper crawlers**: YouTube comments (not just titles), full Twitter threads, LinkedIn posts
- **Agent-to-agent debate**: Citizens that argue with each other across rounds
- **Backtest framework**: Compare past predictions vs actual outcomes
- **Animated D3 timeline**: Show how sentiment shifts across simulation waves

### Medium Priority
- **More citizen personas**: We have 200, always room for more diversity
- **Better PDF parsing**: Current PDF extraction is basic
- **WebSocket live feed**: Replace polling with real WebSocket streaming
- **Export reports**: PDF/Markdown/JSON export of Decision-Ready Maps

### Fun / Viral
- **New unique agents**: What expert perspective is missing?
- **3D force graph**: Three.js version of the DAG
- **Mobile UI**: Responsive design for phone screens

## Adding a New Agent

1. Create a markdown file in `agency-agents/YOUR_DIVISION/your-agent.md`
2. Follow this format:

```markdown
---
name: Your Agent Name
description: One-line description of what this agent does.
color: "#HEX"
emoji: EMOJI
vibe: One catchy sentence about this agent's personality.
---

# Your Agent Name

Full system prompt here. Describe the agent's role, expertise, and rules.

Output JSON:
{
  "key": "value format for structured output"
}
```

3. The agent auto-loads on next server restart. No code changes needed.

## Code Style
- Python: Follow existing patterns, no strict linter
- JavaScript: Vanilla JS in the template (no framework needed)
- Commits: Clear, descriptive messages

## Pull Request Process
1. Fork the repo
2. Create a feature branch
3. Make your changes
4. Test locally (run a full pipeline)
5. Submit PR with description of what changed and why

## License
By contributing, you agree your contributions are licensed under MIT.
