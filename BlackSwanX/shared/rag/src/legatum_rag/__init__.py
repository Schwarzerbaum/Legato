"""LEGATUM RAG — multimodal + knowledge-graph retrieval, driven as a
deepagents dynamic workflow.
Layered on the lbbw harness: one human-facing **orchestrator**, a workforce
of **RAG subagents** (Ingestor, Harvester, Writer, GraphBuilder, Retriever) it
fans out to via a sandboxed QuickJS program, and durable **HITL** gates on the
graph clean-up / optimization step.
"""
__version__ = "0.1.0"
