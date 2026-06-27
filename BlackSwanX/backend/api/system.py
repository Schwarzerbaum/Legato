"""System endpoints — hardware info, model status, health checks."""
from fastapi import APIRouter
from backend.hardware import detect_hardware, ensure_models_pulled

router = APIRouter()


@router.get("/health")
async def health():
    return {"status": "ok"}


@router.get("/hardware")
async def hardware_info():
    hw = detect_hardware()
    models = ensure_models_pulled(hw)
    return {
        "hardware": {
            "chip": hw.chip,
            "total_ram_gb": hw.total_ram_gb,
            "usable_vram_gb": hw.usable_vram_gb,
            "os": hw.os,
        },
        "models": models,
    }
