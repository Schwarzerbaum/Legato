#!/usr/bin/env python3
"""
Complete Optimized Evaluation — Offline preprocessing + Fast Q&A runtime.

Step 1: Preprocess PDF (one-time, ~10-15 min)
Step 2: Evaluate with fast Q&A runtime
Step 3: Compare: Phase 1 (45%) vs Optimized (target 60-75%)
"""
import sys
import json
from pathlib import Path
from datetime import datetime

# Add to path
sys.path.insert(0, str(Path(__file__).parent))

from offline_preprocessor import OfflinePreprocessor
from qa_runtime import QARuntimeOptimized


def main():
    if len(sys.argv) < 3:
        print("Usage: python3 eval_optimized.py <pdf_path> <questions_yaml> [skip-preprocess]")
        sys.exit(1)

    pdf_path = sys.argv[1]
    questions_yaml = sys.argv[2]
    skip_preprocess = len(sys.argv) > 3 and sys.argv[3].lower() == "skip"

    print(f"\n{'='*72}")
    print(f"  Optimized Local PR #2 Evaluation")
    print(f"  Phase 1 (45%) → Optimized (target 60-75%)")
    print(f"{'='*72}\n")

    # Step 1: Preprocess (if not skipped)
    if not skip_preprocess:
        print("[PHASE 1] Offline Preprocessing")
        print("─" * 72)
        preprocessor = OfflinePreprocessor(pdf_path)
        preprocessor.process()
        index_file = preprocessor.index_file
    else:
        # Find existing index
        index_file = Path("legatum/indexes") / f"{Path(pdf_path).stem}.json"
        if not index_file.exists():
            print(f"[ERROR] Index file not found: {index_file}")
            sys.exit(1)
        print(f"[INFO] Using cached index: {index_file}\n")

    # Step 2: Evaluate
    print("[PHASE 2] Fast Q&A Runtime Evaluation")
    print("─" * 72)
    runtime = QARuntimeOptimized(str(index_file))

    print(f"\nEvaluating {questions_yaml}...\n")
    results = runtime.evaluate(questions_yaml)

    # Step 3: Save and report
    print(f"\n{'='*72}")
    print(f"  FINAL RESULTS")
    print(f"{'='*72}")
    print(f"\n📊 Summary:")
    print(f"  Total questions:    {results['total']}")
    print(f"  ✅ Correct:         {results['correct']} ({results['correct']/max(results['total'],1)*100:.0f}%)")
    print(f"  ⚠️  Partial:         {results['partial']} ({results['partial']/max(results['total'],1)*100:.0f}%)")
    print(f"  ❌ Incorrect:       {results['incorrect']} ({results['incorrect']/max(results['total'],1)*100:.0f}%)")
    print(f"\n📈 Score Progression:")
    print(f"  Phase 1 (text-only):              45.0%")
    print(f"  Optimized Local (current):        {results['avg_score']*100:.1f}%")
    print(f"  Target:                           60-75%")

    # Verdict
    print(f"\n{'─'*72}")
    if results['avg_score'] >= 0.70:
        print(f"✅ SUCCESS: Achieved 70%+ benchmark!")
        verdict = "EXCELLENT"
    elif results['avg_score'] >= 0.60:
        print(f"✅ GOOD: Achieved 60%+ target range!")
        verdict = "GOOD"
    elif results['avg_score'] >= 0.50:
        print(f"⚠️  PARTIAL: Above 50% but below 60% target.")
        verdict = "PARTIAL"
    else:
        print(f"❌ BELOW TARGET: Below 50%. Needs optimization.")
        verdict = "NEEDS_WORK"

    print(f"{'─'*72}\n")

    # Save results
    out = Path(__file__).parent / "eval_optimized_results.json"
    out.write_text(json.dumps({
        "timestamp": datetime.now().isoformat(),
        "pdf": Path(pdf_path).name,
        "verdict": verdict,
        "summary": {
            "total": results['total'],
            "correct": results['correct'],
            "partial": results['partial'],
            "incorrect": results['incorrect'],
            "avg_score": results['avg_score']
        },
        "comparison": {
            "phase_1_baseline": 0.45,
            "optimized_current": results['avg_score'],
            "target_range": [0.60, 0.75]
        },
        "results": results['results']
    }, indent=2, ensure_ascii=False))

    print(f"Results saved to: {out}\n")

    return 0 if results['avg_score'] >= 0.60 else 1


if __name__ == "__main__":
    sys.exit(main())
