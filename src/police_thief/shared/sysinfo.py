# Copyright (c) 2026 Dr. Yoram Segal / Gal Technologies Artificial Intelligence Ltd. (GTAI).
# All rights reserved. Educational Use EULA - see LICENSE. Contact: segal@gal-tech.ai
"""Local host system spec: CPU, GPU, RAM, OS — the book's mandatory hardware
declaration (section 6). Probed once, best-effort; unknown values stay 'unknown'.
"""

import json
import os
import platform
import subprocess

_PROBE_TIMEOUT = 15
_PS_QUERY = (
    "$c = Get-CimInstance Win32_Processor | Select-Object -First 1;"
    "$m = Get-CimInstance Win32_ComputerSystem;"
    "$g = Get-CimInstance Win32_VideoController | Select-Object -First 1;"
    "@{cpu=$c.Name; cores=$c.NumberOfCores; mhz=$c.MaxClockSpeed;"
    " ram=$m.TotalPhysicalMemory; gpu=$g.Name; vram=$g.AdapterRAM} | ConvertTo-Json"
)
_cache: dict | None = None


def _run(command: list[str]) -> str | None:
    try:
        result = subprocess.run(command, capture_output=True, text=True,
                                timeout=_PROBE_TIMEOUT, encoding="utf-8", errors="replace")
        return result.stdout.strip() if result.returncode == 0 else None
    except (subprocess.TimeoutExpired, OSError):
        return None


def _windows_probe(spec: dict) -> None:
    raw = _run(["powershell", "-NoProfile", "-Command", _PS_QUERY])
    if not raw:
        return
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return
    spec["cpu_type"] = data.get("cpu") or spec["cpu_type"]
    spec["cpu_cores"] = int(data.get("cores") or spec["cpu_cores"])
    spec["cpu_freq_mhz"] = int(data.get("mhz") or 0) or "unknown"
    if data.get("ram"):
        spec["ram_gb"] = round(int(data["ram"]) / 1024**3, 1)
    spec["gpu_type"] = data.get("gpu") or spec["gpu_type"]
    if data.get("vram"):  # Win32 caps at 4GB; nvidia-smi below overrides when present
        spec["vram_gb"] = round(int(data["vram"]) / 1024**3, 1)


def _nvidia_probe(spec: dict) -> None:
    raw = _run(["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader"])
    if not raw:
        return
    name, _, memory = raw.partition(",")
    spec["gpu_type"] = name.strip() or spec["gpu_type"]
    digits = "".join(ch for ch in memory if ch.isdigit())
    if digits:
        spec["vram_gb"] = round(int(digits) / 1024, 1)  # MiB -> GB
    spec["gpu_cores_or_cuda"] = "CUDA (core count not exposed by driver)"


def collect_spec() -> dict:
    """The host spec, probed once per process and cached."""
    global _cache
    if _cache is not None:
        return _cache
    spec = {
        "os": f"{platform.system()} {platform.release()} ({platform.version()})",
        "cpu_type": platform.processor() or "unknown",
        "cpu_cores": os.cpu_count() or 1,
        "cpu_freq_mhz": "unknown",
        "ram_gb": "unknown",
        "gpu_type": "unknown",
        "gpu_cores_or_cuda": "unknown",
        "vram_gb": "unknown",
    }
    if platform.system() == "Windows":
        _windows_probe(spec)
    _nvidia_probe(spec)
    _cache = spec
    return spec
