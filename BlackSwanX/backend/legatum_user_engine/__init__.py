"""
LEGATUM User Engine — layers that face the philanthropic donor (Stifter).

L1  l1_persona_discovery   — onboarding quiz → archetype
L4  l4_advisor_interface   — LBBW advisor matching
L5  l5_impact_universe     — SDG allocation + lives-touched simulation
L7  l7_foundation_arc      — German Stiftung structuring gates
L8  l8_legatum_passport    — badge credentials + credibility score
L9  l9_stifter_intelligence — AI giving strategy
"""
from .l1_persona_discovery   import calc_persona, persona_to_dict, PersonaResult
from .l4_advisor_interface   import match_advisor, advisor_to_dict, AdvisorMatch
from .l5_impact_universe     import build_impact_snapshot, snapshot_to_dict, ImpactSnapshot
from .l7_foundation_arc      import build_foundation_arc, arc_to_dict, FoundationArc
from .l8_legatum_passport    import build_passport, passport_to_dict, LegatumPassport
from .l9_stifter_intelligence import generate_strategy, strategy_to_dict, GivingStrategy

__all__ = [
    "calc_persona", "persona_to_dict", "PersonaResult",
    "match_advisor", "advisor_to_dict", "AdvisorMatch",
    "build_impact_snapshot", "snapshot_to_dict", "ImpactSnapshot",
    "build_foundation_arc", "arc_to_dict", "FoundationArc",
    "build_passport", "passport_to_dict", "LegatumPassport",
    "generate_strategy", "strategy_to_dict", "GivingStrategy",
]
