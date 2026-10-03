"""Utility functions for clipboard, formatting, and persistent config."""

import json
import os
import shutil
import subprocess
from typing import Any, Dict, Optional


CONFIG_PATH = os.path.expanduser("~/.config/tui-llama-server/config.json")


def load_user_config() -> Dict[str, Any]:
    """Load user configuration from ~/.config/tui-llama-server/config.json."""
    default_cfg: Dict[str, Any] = {
        "models_dir": os.path.expanduser("~/models"),
        "host": "127.0.0.1",
        "port": 8080,
        "ctx_size": 4096,
        "n_gpu_layers": 99,
        "threads": max(1, (os.cpu_count() or 4) - 2),
        "flash_attn": "auto",
        "no_webui": True,
        "extra_args": "",
        "env_overrides": {},
    }
    if os.path.isfile(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                saved = json.load(f)
                default_cfg.update(saved)
        except Exception:
            pass
    return default_cfg


def save_user_config(cfg: Dict[str, Any]) -> None:
    """Save user configuration to disk."""
    try:
        os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2)
    except Exception:
        pass


def copy_text_to_clipboard(text: str) -> bool:
    """Copy text to clipboard using xclip, wl-copy, or pbcopy."""
    # Try wl-copy (Wayland)
    if shutil.which("wl-copy"):
        try:
            subprocess.run(["wl-copy"], input=text, text=True, check=True, timeout=1.0)
            return True
        except Exception:
            pass

    # Try xclip (X11)
    if shutil.which("xclip"):
        try:
            subprocess.run(
                ["xclip", "-selection", "clipboard"],
                input=text,
                text=True,
                check=True,
                timeout=1.0,
            )
            return True
        except Exception:
            pass

    # Try xsel
    if shutil.which("xsel"):
        try:
            subprocess.run(
                ["xsel", "--clipboard", "--input"],
                input=text,
                text=True,
                check=True,
                timeout=1.0,
            )
            return True
        except Exception:
            pass

    return False


def format_bytes(bytes_val: int) -> str:
    """Format bytes into human readable string (KB, MB, GB)."""
    if bytes_val < 1024:
        return f"{bytes_val} B"
    elif bytes_val < 1024 ** 2:
        return f"{bytes_val / 1024:.1f} KB"
    elif bytes_val < 1024 ** 3:
        return f"{bytes_val / (1024 ** 2):.1f} MB"
    else:
        return f"{bytes_val / (1024 ** 3):.2f} GB"
