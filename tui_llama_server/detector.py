"""Hardware detection module: ROCm, AMD GPU, GFX architecture, NVIDIA CUDA, CPU & RAM."""

import json
import os
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class GPUInfo:
    vendor: str  # "amd", "nvidia", "cpu"
    name: str  # e.g. "AMD Radeon RX 9070 XT"
    device_id: str = "0"
    driver_version: str = "N/A"
    rocm_version: Optional[str] = None
    cuda_version: Optional[str] = None
    gfx_arch: Optional[str] = None  # e.g. "gfx1201"
    vram_total_mb: int = 0
    vram_used_mb: int = 0
    recommended_env: Dict[str, str] = field(default_factory=dict)
    recommended_flags: List[str] = field(default_factory=list)


def _run_cmd(cmd: List[str], timeout: float = 3.0) -> Optional[str]:
    """Run command safely and return stripped stdout or None."""
    try:
        res = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout,
        )
        if res.returncode == 0:
            return res.stdout.strip()
    except Exception:
        pass
    return None


def detect_rocm_version() -> Optional[str]:
    """Detect ROCm runtime version from multiple sources."""
    # 1. Try hipconfig --version
    hip_out = _run_cmd(["hipconfig", "--version"])
    if hip_out:
        # e.g. "7.15.26333-0000000" -> "7.15"
        m = re.match(r"^(\d+\.\d+)", hip_out.strip())
        if m:
            return m.group(1)
        return hip_out.strip()

    # 2. Try /opt/rocm/.info/version or /opt/rocm/.version
    for p in ["/opt/rocm/.info/version", "/opt/rocm/.version"]:
        if os.path.isfile(p):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    content = f.read().strip()
                    m = re.match(r"^(\d+\.\d+)", content)
                    if m:
                        return m.group(1)
                    return content
            except Exception:
                pass

    # 3. Try rocm-smi
    smi_out = _run_cmd(["rocm-smi", "--showdriverversion"])
    if smi_out:
        m = re.search(r"Driver version:\s*([^\n\r]+)", smi_out)
        if m:
            return m.group(1).strip()

    # 4. Check dpkg/rpm installed rocm packages
    dpkg_out = _run_cmd(["dpkg", "-l", "rocm-core"])
    if dpkg_out:
        m = re.search(r"rocm-core\s+(\d+\.\d+)", dpkg_out)
        if m:
            return m.group(1)

    return None


def detect_amd_gpus() -> List[GPUInfo]:
    """Detect AMD GPUs and derive optimal ROCm flags and environment variables."""
    gpus: List[GPUInfo] = []
    rocm_ver = detect_rocm_version()

    # Try rocm-smi JSON output
    json_out = _run_cmd(["rocm-smi", "--showproductname", "--showdriverversion", "--json"])
    smi_info_out = _run_cmd(["rocm-smi", "--showproductname"])

    # Extract GFX arch from rocm-smi or sysfs
    gfx_arch = None
    if smi_info_out:
        m = re.search(r"GFX Version:\s*(gfx\w+)", smi_info_out)
        if m:
            gfx_arch = m.group(1)

    # If gfx_arch is still None, inspect /sys/class/kfd/kfd/topology/nodes/*/properties
    if not gfx_arch and os.path.isdir("/sys/class/kfd/kfd/topology/nodes"):
        try:
            for node in sorted(os.listdir("/sys/class/kfd/kfd/topology/nodes")):
                prop_path = os.path.join("/sys/class/kfd/kfd/topology/nodes", node, "properties")
                if os.path.isfile(prop_path):
                    with open(prop_path, "r", encoding="utf-8") as f:
                        content = f.read()
                        m = re.search(r"gfx_target_version\s+(\d+)", content)
                        if m:
                            val = int(m.group(1))
                            if val > 0:
                                # e.g. 120001 -> gfx1201, 110000 -> gfx1100, 103000 -> gfx1030
                                major = val // 10000
                                minor = (val % 10000) // 100
                                stepping = val % 100
                                gfx_arch = f"gfx{major}{minor}{stepping}"
                                break
        except Exception:
            pass

    # Extract VRAM memory from rocm-smi
    vram_mem_out = _run_cmd(["rocm-smi", "--showmeminfo", "vram", "--json"])
    total_vram_mb = 0
    used_vram_mb = 0
    if vram_mem_out:
        try:
            v_data = json.loads(vram_mem_out)
            for card_k, card_v in v_data.items():
                tot_b = int(card_v.get("VRAM Total Memory (B)", 0))
                used_b = int(card_v.get("VRAM Total Used Memory (B)", 0))
                total_vram_mb = max(total_vram_mb, tot_b // (1024 * 1024))
                used_vram_mb = max(used_vram_mb, used_b // (1024 * 1024))
        except Exception:
            pass

    # Extract Card Name
    card_name = "AMD Radeon GPU"
    if smi_info_out:
        m = re.search(r"Card Series:\s*([^\n\r]+)", smi_info_out)
        if m:
            card_name = m.group(1).strip()
    elif os.path.exists("/usr/bin/lspci"):
        lspci_out = _run_cmd(["lspci", "-nn"])
        if lspci_out:
            for line in lspci_out.splitlines():
                if "VGA" in line and ("AMD" in line or "ATI" in line):
                    card_name = line.split(":")[-1].strip()
                    break

    # Calculate optimal presets based on GFX arch and ROCm version
    recommended_env: Dict[str, str] = {
        "HIP_VISIBLE_DEVICES": "0",
        "ROCR_VISIBLE_DEVICES": "0",
    }
    recommended_flags: List[str] = ["-ngl", "99", "--flash-attn", "auto"]

    if gfx_arch:
        # Tuning overrides for specific architectures
        if gfx_arch.startswith("gfx12"):
            # RDNA4 (e.g. RX 9070 XT gfx1201)
            # Many ROCm binaries look for HSA_OVERRIDE_GFX_VERSION if not natively compiled
            recommended_env["HSA_OVERRIDE_GFX_VERSION"] = "12.0.1"
            recommended_flags = ["-ngl", "99", "--flash-attn", "auto"]
        elif gfx_arch.startswith("gfx110"):
            # RDNA3 (e.g. RX 7900 XTX / 7900 XT / 7800 XT)
            recommended_env["HSA_OVERRIDE_GFX_VERSION"] = "11.0.0"
            recommended_flags = ["-ngl", "99", "--flash-attn", "on"]
        elif gfx_arch.startswith("gfx103"):
            # RDNA2 (e.g. RX 6800 / 6700 / 6900)
            recommended_env["HSA_OVERRIDE_GFX_VERSION"] = "10.3.0"
            # Flash attention can sometimes be unstable on RDNA2 with older ROCm
            recommended_flags = ["-ngl", "99", "--flash-attn", "off"]
        elif gfx_arch.startswith("gfx90"):
            # CDNA (MI100/200/300) or Vega 56/64/VII
            recommended_flags = ["-ngl", "99", "--flash-attn", "on"]

    # SDMA queue tuning
    recommended_env["GPU_MAX_HW_QUEUES"] = "8"

    gpu = GPUInfo(
        vendor="amd",
        name=card_name,
        device_id="0",
        driver_version=detect_rocm_version() or "ROCm installed",
        rocm_version=rocm_ver,
        gfx_arch=gfx_arch,
        vram_total_mb=total_vram_mb,
        vram_used_mb=used_vram_mb,
        recommended_env=recommended_env,
        recommended_flags=recommended_flags,
    )
    gpus.append(gpu)
    return gpus


def detect_nvidia_gpus() -> List[GPUInfo]:
    """Detect NVIDIA GPUs if present."""
    gpus: List[GPUInfo] = []
    smi_out = _run_cmd([
        "nvidia-smi",
        "--query-gpu=index,name,driver_version,memory.total,memory.used",
        "--format=csv,noheader,nounits",
    ])
    if smi_out:
        for line in smi_out.splitlines():
            parts = [p.strip() for p in line.split(",")]
            if len(parts) >= 5:
                idx, name, driver, tot_mem, used_mem = parts[:5]
                gpu = GPUInfo(
                    vendor="nvidia",
                    name=name,
                    device_id=idx,
                    driver_version=driver,
                    cuda_version=driver,
                    vram_total_mb=int(float(tot_mem)),
                    vram_used_mb=int(float(used_mem)),
                    recommended_env={"CUDA_VISIBLE_DEVICES": idx},
                    recommended_flags=["-ngl", "99", "--flash-attn", "auto"],
                )
                gpus.append(gpu)
    return gpus


def detect_system_gpus() -> List[GPUInfo]:
    """Auto-detect all available GPUs, prioritizing ROCm/AMD if present, then NVIDIA, else CPU."""
    # Check AMD ROCm first
    if shutil.which("rocm-smi") or shutil.which("hipconfig") or os.path.exists("/sys/class/kfd"):
        amd_gpus = detect_amd_gpus()
        if amd_gpus and amd_gpus[0].vram_total_mb > 0 or amd_gpus[0].gfx_arch:
            return amd_gpus

    # Check NVIDIA
    if shutil.which("nvidia-smi"):
        nv_gpus = detect_nvidia_gpus()
        if nv_gpus:
            return nv_gpus

    # Fallback to CPU
    import psutil
    cpu_cores = os.cpu_count() or 4
    mem = psutil.virtual_memory()
    return [
        GPUInfo(
            vendor="cpu",
            name="CPU Inference (Fallback)",
            device_id="cpu",
            driver_version="System CPU",
            vram_total_mb=int(mem.total // (1024 * 1024)),
            vram_used_mb=int(mem.used // (1024 * 1024)),
            recommended_env={},
            recommended_flags=["-ngl", "0", "--threads", str(max(1, cpu_cores - 2))],
        )
    ]


def find_llama_server_binary() -> Optional[str]:
    """Find llama-server binary in PATH or standard user directories."""
    candidates = [
        shutil.which("llama-server"),
        os.path.expanduser("~/.local/bin/llama-server"),
        "/usr/local/bin/llama-server",
        "/usr/bin/llama-server",
        os.path.expanduser("~/bin/llama-server"),
    ]
    for c in candidates:
        if c and os.path.isfile(c) and os.access(c, os.X_OK):
            return os.path.abspath(c)
    return None
