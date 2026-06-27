"""Hardware detection + automatic model selection for Ollama."""
import subprocess
import platform
import json
import re
from dataclasses import dataclass


@dataclass
class HardwareProfile:
    chip: str
    total_ram_gb: float
    usable_vram_gb: float  # For Apple Silicon = ~75% of unified memory
    os: str
    recommended_cluster_model: str
    recommended_reasoning_model: str


# Model tiers based on available VRAM/RAM
# Three-model strategy:
#   Swarm (citizens): llama3.2:3b — fast, small, biased human simulation
#   Assassin (BlackSwan/Kill-Switch): phi4:14b — deep reasoning, finds kill shots
#   Nexus Brain (orchestrator/elites): mistral-small:24b — synthesis, DAG construction
# keep_alive: 0 is used between swarm waves to flush RAM
MODEL_TIERS = [
    # (min_vram_gb, swarm_model, reasoning_model)
    # Note: phi4:14b is loaded on-demand for assassin tasks only
    (24, "llama3.2:3b", "mistral-small:24b"),  # Full power
    (12, "llama3.2:3b", "phi4:14b"),            # M2 Pro 16GB — phi4 as main brain
    (8, "llama3.2:3b", "phi4:14b"),
    (6, "llama3.2:3b", "llama3.2:3b"),          # Fallback: same model for everything
    (0, "llama3.2:3b", "llama3.2:3b"),
]

# The Assassin model — used specifically for BlackSwan/Kill-Switch
# Loaded on-demand, flushed after use
ASSASSIN_MODEL = "phi4:14b"


def detect_hardware() -> HardwareProfile:
    """Detect hardware and recommend optimal Ollama models."""
    system = platform.system()
    chip = "Unknown"
    total_ram_gb = 8.0

    if system == "Darwin":  # macOS
        # Get chip info
        try:
            result = subprocess.run(
                ["sysctl", "-n", "machdep.cpu.brand_string"],
                capture_output=True, text=True, timeout=5
            )
            chip = result.stdout.strip()
        except Exception:
            chip = "Apple Silicon (unknown)"

        # Get total RAM
        try:
            result = subprocess.run(
                ["sysctl", "-n", "hw.memsize"],
                capture_output=True, text=True, timeout=5
            )
            total_ram_gb = int(result.stdout.strip()) / (1024 ** 3)
        except Exception:
            pass

        # Apple Silicon uses unified memory; ~75% usable for ML
        usable_vram = total_ram_gb * 0.75

    elif system == "Linux":
        # Try nvidia-smi for NVIDIA GPUs
        try:
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=memory.total", "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=5
            )
            vram_mb = sum(int(x.strip()) for x in result.stdout.strip().split("\n") if x.strip())
            usable_vram = vram_mb / 1024
            chip = "NVIDIA GPU"
        except Exception:
            usable_vram = 4.0  # Fallback: assume CPU-only

        try:
            with open("/proc/meminfo") as f:
                for line in f:
                    if line.startswith("MemTotal:"):
                        total_ram_gb = int(line.split()[1]) / (1024 ** 2)
                        break
        except Exception:
            pass
    else:
        # Windows or unknown
        usable_vram = total_ram_gb * 0.5

    # Select models based on available VRAM
    cluster_model = MODEL_TIERS[-1][1]
    reasoning_model = MODEL_TIERS[-1][2]
    for min_vram, cm, rm in MODEL_TIERS:
        if usable_vram >= min_vram:
            cluster_model = cm
            reasoning_model = rm
            break

    return HardwareProfile(
        chip=chip,
        total_ram_gb=round(total_ram_gb, 1),
        usable_vram_gb=round(usable_vram, 1),
        os=system,
        recommended_cluster_model=cluster_model,
        recommended_reasoning_model=reasoning_model,
    )


def ensure_models_pulled(profile: HardwareProfile) -> dict:
    """Check which models are available and which need pulling."""
    try:
        result = subprocess.run(
            ["ollama", "list"], capture_output=True, text=True, timeout=10
        )
        installed = result.stdout
    except Exception:
        return {"cluster": False, "reasoning": False, "error": "Ollama not running"}

    return {
        "cluster_model": profile.recommended_cluster_model,
        "cluster_installed": profile.recommended_cluster_model.split(":")[0] in installed,
        "reasoning_model": profile.recommended_reasoning_model,
        "reasoning_installed": profile.recommended_reasoning_model.split(":")[0] in installed,
    }


if __name__ == "__main__":
    hw = detect_hardware()
    print(f"Chip: {hw.chip}")
    print(f"RAM: {hw.total_ram_gb} GB")
    print(f"Usable VRAM: {hw.usable_vram_gb} GB")
    print(f"Cluster Model: {hw.recommended_cluster_model}")
    print(f"Reasoning Model: {hw.recommended_reasoning_model}")
    print()
    status = ensure_models_pulled(hw)
    print(f"Model Status: {json.dumps(status, indent=2)}")
