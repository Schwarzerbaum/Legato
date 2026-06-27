#!/usr/bin/env python3
"""
PR #2 Full Evaluation — Multimodal RAG with OCR + visual grounding.
Target: 65-75% on 18 BIM-Leitfaden questions.
"""
import sys
import json
from pathlib import Path

# Add to path
sys.path.insert(0, str(Path(__file__).parent))

from pr2_integration import PR2Pipeline


def main():
    if len(sys.argv) < 3:
        print("Usage: python3 eval_pr2.py <pdf_path> <questions_yaml>")
        sys.exit(1)

    pdf_path = sys.argv[1]
    yaml_path = sys.argv[2]

    print(f"\n{'='*72}")
    print(f"  PR #2 Full Evaluation — Multimodal RAG")
    print(f"  Target: 65-75% (vs Phase 1: 45%, Option A: 55-65%)")
    print(f"{'='*72}\n")

    # Initialize pipeline
    pipeline = PR2Pipeline(pdf_path)

    # Ingest
    print(f"[0/3] Initializing pipeline...")
    pipeline.ingest()

    # Evaluate
    print(f"\n[1/3] Running evaluation (18 questions)...\n")
    results = pipeline.evaluate(yaml_path)

    # Summary
    print(f"\n{'='*72}")
    print(f"  RESULTS — PR #2 Full Pipeline")
    print(f"  \033[92m{results['correct']} correct\033[0m · "
          f"\033[93m{results['partial']} partial\033[0m · "
          f"\033[91m{results['incorrect']} incorrect\033[0m")
    print(f"  Average score: {results['avg_score']:.1%}")
    print(f"{'='*72}\n")

    # Save results
    out = Path(__file__).parent / "eval_pr2_results.json"
    out.write_text(json.dumps(results, indent=2, ensure_ascii=False))
    print(f"Results saved to: {out}\n")

    # Comparison
    print("COMPARISON:")
    print("─" * 72)
    print(f"Phase 1 (text-only retrieval):           45.0%")
    print(f"Option A (RRF + LLM harvester):          ~55%")
    print(f"PR #2 (multimodal + OCR + visual):       {results['avg_score']:.1%}")
    print(f"Target:                                  65-75%")
    print("─" * 72 + "\n")

    # Success check
    if results['avg_score'] >= 0.65:
        print("✅ TARGET ACHIEVED: PR #2 meets 65%+ benchmark!")
    elif results['avg_score'] >= 0.55:
        print("⚠️  PARTIAL: PR #2 above 55%, but below 65% target. Tuning needed.")
    else:
        print("❌ BELOW TARGET: PR #2 below 55%. Investigate failures.")

    return 0 if results['avg_score'] >= 0.65 else 1


if __name__ == "__main__":
    sys.exit(main())
