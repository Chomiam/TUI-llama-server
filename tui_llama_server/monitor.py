"""Live performance monitor: GPU, VRAM, RAM, CPU, and Swap with high-speed direct sysfs/SMI hooks."""

import glob
import json
import os
import subprocess
from dataclasses import dataclass
from typing import Optional
import psutil


@dataclass
class PerformanceMetrics:
    gpu_busy_pct: float = 0.0
    vram_used_gb: float = 0.0
    vram_total_gb: float = 0.0
    vram_pct: float = 0.0
    
    ram_used_gb: float = 0.0
    ram_total_gb: float = 0.0
    ram_pct: float = 0.0
    
    cpu_pct: float = 0.0
    swap_used_gb: float = 0.0
    swap_total_gb: float = 0.0
    swap_pct: float = 0.0


class SystemMonitor:
    def __init__(self, vendor: str = "amd"):
        self.vendor = vendor
        self._amd_sysfs_busy: Optional[str] = None
        self._amd_sysfs_used: Optional[str] = None
        self._amd_sysfs_total: Optional[str] = None
        
        # Discover direct AMD sysfs entries for zero-overhead polling
        busy_files = glob.glob("/sys/class/drm/card*/device/gpu_busy_percent")
        if busy_files:
            self._amd_sysfs_busy = busy_files[0]
        used_files = glob.glob("/sys/class/drm/card*/device/mem_info_vram_used")
        if used_files:
            self._amd_sysfs_used = used_files[0]
        tot_files = glob.glob("/sys/class/drm/card*/device/mem_info_vram_total")
        if tot_files:
            self._amd_sysfs_total = tot_files[0]

        # Prime CPU percent sampler
        psutil.cpu_percent(interval=None)

    def sample(self) -> PerformanceMetrics:
        """Sample all hardware performance metrics synchronously."""
        # 1. System RAM & CPU & Swap
        mem = psutil.virtual_memory()
        swap = psutil.swap_memory()
        cpu_usage = psutil.cpu_percent(interval=None)
        
        ram_used = mem.used / (1024 ** 3)
        ram_tot = mem.total / (1024 ** 3)
        ram_pct = mem.percent
        
        swap_used = swap.used / (1024 ** 3)
        swap_tot = swap.total / (1024 ** 3)
        swap_pct = swap.percent

        # 2. GPU & VRAM
        gpu_pct = 0.0
        vram_used = 0.0
        vram_tot = 0.0
        vram_pct = 0.0

        if self.vendor == "amd":
            # Fast path: direct sysfs
            if self._amd_sysfs_busy and os.path.isfile(self._amd_sysfs_busy):
                try:
                    with open(self._amd_sysfs_busy, "r") as f:
                        gpu_pct = float(f.read().strip())
                except Exception:
                    pass

            if self._amd_sysfs_used and self._amd_sysfs_total:
                try:
                    with open(self._amd_sysfs_used, "r") as f:
                        used_b = int(f.read().strip())
                    with open(self._amd_sysfs_total, "r") as f:
                        tot_b = int(f.read().strip())
                    vram_used = used_b / (1024 ** 3)
                    vram_tot = tot_b / (1024 ** 3)
                    if vram_tot > 0:
                        vram_pct = (vram_used / vram_tot) * 100.0
                except Exception:
                    pass
            
            # Fallback to rocm-smi if sysfs had nothing
            if vram_tot == 0.0:
                try:
                    res = subprocess.run(
                        ["rocm-smi", "--showuse", "--showmeminfo", "vram", "--json"],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                        timeout=1.0,
                    )
                    if res.returncode == 0:
                        data = json.loads(res.stdout)
                        for _, card_v in data.items():
                            g_use = card_v.get("GPU use (%)")
                            if g_use is not None:
                                gpu_pct = float(g_use)
                            tot_b = int(card_v.get("VRAM Total Memory (B)", 0))
                            used_b = int(card_v.get("VRAM Total Used Memory (B)", 0))
                            if tot_b > 0:
                                vram_used = used_b / (1024 ** 3)
                                vram_tot = tot_b / (1024 ** 3)
                                vram_pct = (vram_used / vram_tot) * 100.0
                            break
                except Exception:
                    pass

        elif self.vendor == "nvidia":
            try:
                res = subprocess.run(
                    [
                        "nvidia-smi",
                        "--query-gpu=utilization.gpu,memory.used,memory.total",
                        "--format=csv,noheader,nounits",
                    ],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    timeout=1.0,
                )
                if res.returncode == 0 and res.stdout.strip():
                    parts = [p.strip() for p in res.stdout.strip().split(",")]
                    if len(parts) >= 3:
                        gpu_pct = float(parts[0])
                        vram_used = float(parts[1]) / 1024.0
                        vram_tot = float(parts[2]) / 1024.0
                        if vram_tot > 0:
                            vram_pct = (vram_used / vram_tot) * 100.0
            except Exception:
                pass

        return PerformanceMetrics(
            gpu_busy_pct=round(gpu_pct, 1),
            vram_used_gb=round(vram_used, 2),
            vram_total_gb=round(vram_tot, 2),
            vram_pct=round(vram_pct, 1),
            ram_used_gb=round(ram_used, 2),
            ram_total_gb=round(ram_tot, 2),
            ram_pct=round(ram_pct, 1),
            cpu_pct=round(cpu_usage, 1),
            swap_used_gb=round(swap_used, 2),
            swap_total_gb=round(swap_tot, 2),
            swap_pct=round(swap_pct, 1),
        )
