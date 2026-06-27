"""
LEGATUM Bank Engine — layers operated by LBBW analysts and AI agents.

L2  l2_ngo_intelligence        — vetted NGO registry, impact scoring
L3  l3_blackswanx_credibility  — risk-adjusted philanthropic credibility scores
L6  l6_knowledge_graph         — persistent relationship mesh (SQLite-backed)
"""
from .l2_ngo_intelligence      import search_ngos, score_ngo, ngo_result_to_dict, NGORecord
from .l3_blackswanx_credibility import calc_credibility, credibility_to_dict, CredibilityInput
from .l6_knowledge_graph        import (
    add_node, add_edge, get_graph, query_neighbours, get_stats, seed_demo_graph,
    KGNode, KGEdge,
)

__all__ = [
    "search_ngos", "score_ngo", "ngo_result_to_dict", "NGORecord",
    "calc_credibility", "credibility_to_dict", "CredibilityInput",
    "add_node", "add_edge", "get_graph", "query_neighbours", "get_stats",
    "seed_demo_graph", "KGNode", "KGEdge",
]
