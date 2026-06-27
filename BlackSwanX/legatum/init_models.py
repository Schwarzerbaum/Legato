#!/usr/bin/env python3
"""
Initialize models for local PR #2 pipeline.
One-time setup: downloads ColModernVBERT, DeepSeek-OCR-2, Llama 3.1.
"""
import sys


def init_colmodernvbert():
    """Download ColModernVBERT from HuggingFace."""
    print("\n" + "="*72)
    print("  Initializing ColModernVBERT (250M params, ~500MB)")
    print("="*72)

    try:
        from transformers import AutoModel, AutoProcessor

        print("[1/2] Downloading ColModernVBERT model...")
        model = AutoModel.from_pretrained(
            "ModernVBERT/colmodernvbert",
            trust_remote_code=True
        )

        print("[2/2] Downloading processor...")
        processor = AutoProcessor.from_pretrained(
            "ModernVBERT/colmodernvbert",
            trust_remote_code=True
        )

        print("✅ ColModernVBERT ready! (cached in ~/.cache/huggingface/)")
        return True

    except Exception as e:
        print(f"❌ ColModernVBERT init failed: {str(e)[:100]}")
        print("   Install with: pip install transformers torch accelerate")
        return False


def init_deepseek_ocr():
    """Download DeepSeek-OCR-2 from HuggingFace (with FP16 MPS support)."""
    print("\n" + "="*72)
    print("  Initializing DeepSeek-OCR-2 (3B params, ~3.5-6GB, MPS optimized)")
    print("="*72)

    try:
        import torch
        from transformers import AutoModel

        print("[1/1] Downloading DeepSeek-OCR-2 (with float16 quantization for MPS)...")

        # Use FP16 quantization to fit in Mac RAM (~6GB → ~3GB)
        model = AutoModel.from_pretrained(
            "deepseek-ai/DeepSeek-OCR-2",
            trust_remote_code=True,
            torch_dtype=torch.float16  # Float16 for memory efficiency
        )

        # Move to MPS (Apple Silicon) if available
        if torch.backends.mps.is_available():
            model = model.to("mps")
            print("   → Using Apple Silicon (MPS) acceleration")
        else:
            model = model.to("cpu")
            print("   → Using CPU (no MPS available)")

        print("✅ DeepSeek-OCR-2 ready! (cached in ~/.cache/huggingface/)")
        return True

    except Exception as e:
        print(f"❌ DeepSeek-OCR-2 init failed: {str(e)[:100]}")
        print("   Install with: pip install transformers torch")
        return False


def init_llama_via_ollama():
    """Verify Llama 3.1 is available in Ollama."""
    print("\n" + "="*72)
    print("  Initializing Llama 3.1 8B (via Ollama, 4.8GB)")
    print("="*72)

    try:
        import subprocess

        print("[1/1] Checking Ollama and pulling Llama 3.1...")
        result = subprocess.run(
            ["ollama", "pull", "llama3.1"],
            capture_output=True,
            text=True,
            timeout=300
        )

        if result.returncode == 0:
            print("✅ Llama 3.1 ready!")
            return True
        else:
            print(f"⚠️  Ollama command failed: {result.stderr[:100]}")
            print("   Make sure Ollama is installed and running")
            return False

    except Exception as e:
        print(f"⚠️  Ollama check failed: {str(e)[:100]}")
        print("   Install from: https://ollama.ai")
        return False


def main():
    """Initialize all models."""
    print("\n" + "="*72)
    print("  PR #2 Local Model Initialization")
    print("  This is a one-time setup (~10-15 min, requires internet)")
    print("="*72)

    results = {}

    # ColModernVBERT (must have)
    results["colmodernvbert"] = init_colmodernvbert()

    # DeepSeek-OCR-2 (must have)
    results["deepseek_ocr"] = init_deepseek_ocr()

    # Llama 3.1 via Ollama (should have)
    results["llama"] = init_llama_via_ollama()

    # Summary
    print("\n" + "="*72)
    print("  SUMMARY")
    print("="*72)
    print(f"  ColModernVBERT:  {'✅' if results['colmodernvbert'] else '❌'}")
    print(f"  DeepSeek-OCR-2:  {'✅' if results['deepseek_ocr'] else '❌'}")
    print(f"  Llama 3.1:       {'✅' if results['llama'] else '⚠️ (optional)'}")

    if results["colmodernvbert"] and results["deepseek_ocr"]:
        print("\n✅ Ready to run: python3 offline_preprocessor.py <pdf>")
        return 0
    else:
        print("\n❌ Missing required models. Install and retry.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
