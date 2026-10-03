"""CLI entrypoint for tui-llama-server."""

import argparse
import sys
from tui_llama_server.detector import detect_system_gpus, find_llama_server_binary
from tui_llama_server.app import TuiLlamaApp

__version__ = "1.0.0"


def main():
    parser = argparse.ArgumentParser(
        prog="tui-llama-server",
        description="Premium TUI & GPU/ROCm Manager for llama.cpp server for AI agents.",
    )
    parser.add_argument(
        "--models-dir",
        type=str,
        default=None,
        help="Path to models directory (default: ~/models)",
    )
    parser.add_argument(
        "--detect",
        action="store_true",
        help="Print detected GPU and ROCm hardware diagnostics and exit",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )

    args = parser.parse_args()

    if args.detect:
        print(f"--- TUI-llama-server Hardware Detection v{__version__} ---")
        gpus = detect_system_gpus()
        for i, g in enumerate(gpus):
            print(f"GPU [{i}]:")
            print(f"  Vendor:            {g.vendor.upper()}")
            print(f"  Name:              {g.name}")
            print(f"  ROCm Version:      {g.rocm_version or 'N/A'}")
            print(f"  GFX Target Arch:   {g.gfx_arch or 'N/A'}")
            print(f"  VRAM Total:        {g.vram_total_mb / 1024:.2f} GB")
            print(f"  Recommended Flags: {' '.join(g.recommended_flags)}")
            print(f"  Recommended Env:   {g.recommended_env}")
        
        llama_bin = find_llama_server_binary()
        print(f"\nllama-server binary: {llama_bin or 'NOT FOUND (install or put in ~/.local/bin or PATH)'}")
        sys.exit(0)

    app = TuiLlamaApp(models_dir=args.models_dir)
    app.run()


if __name__ == "__main__":
    main()
