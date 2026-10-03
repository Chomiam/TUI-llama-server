"""Subprocess management for llama-server with real-time log streaming and health checking."""

import os
import queue
import subprocess
import threading
import time
from collections import deque
from dataclasses import dataclass
from typing import Callable, Deque, Dict, List, Optional
import urllib.request
import urllib.error


@dataclass
class ServerStatus:
    is_running: bool = False
    is_ready: bool = False
    pid: Optional[int] = None
    model_name: str = ""
    model_path: str = ""
    base_url: str = ""
    exit_code: Optional[int] = None
    error_message: Optional[str] = None


class ServerManager:
    def __init__(self, log_capacity: int = 2000):
        self._process: Optional[subprocess.Popen] = None
        self._logs: Deque[str] = deque(maxlen=log_capacity)
        self._log_lock = threading.Lock()
        self._status = ServerStatus()
        self._status_lock = threading.Lock()
        self._on_log_callback: Optional[Callable[[str], None]] = None
        self._reader_thread: Optional[threading.Thread] = None
        self._health_thread: Optional[threading.Thread] = None
        self._stop_health = threading.Event()

    def set_log_callback(self, callback: Callable[[str], None]) -> None:
        self._on_log_callback = callback

    @property
    def status(self) -> ServerStatus:
        with self._status_lock:
            # Check if process unexpectedly died
            if self._process is not None and self._status.is_running:
                poll = self._process.poll()
                if poll is not None:
                    self._status.is_running = False
                    self._status.is_ready = False
                    self._status.exit_code = poll
            return ServerStatus(**self._status.__dict__)

    def start(
        self,
        binary_path: str,
        model_path: str,
        host: str = "127.0.0.1",
        port: int = 8080,
        ctx_size: int = 4096,
        n_gpu_layers: int = 99,
        threads: int = 4,
        flash_attn: str = "auto",
        no_webui: bool = True,
        extra_args: Optional[List[str]] = None,
        custom_env: Optional[Dict[str, str]] = None,
    ) -> bool:
        """Start llama-server with tailored flags and ROCm/GPU environment."""
        if self._process and self._process.poll() is None:
            return False  # Already running

        cmd = [
            binary_path,
            "-m", model_path,
            "--host", host,
            "--port", str(port),
            "-c", str(ctx_size),
            "-ngl", str(n_gpu_layers),
            "-t", str(threads),
        ]

        if flash_attn in ("on", "off"):
            cmd.extend(["--flash-attn", flash_attn])
        elif flash_attn == "auto":
            cmd.extend(["--flash-attn", "auto"])

        if no_webui:
            cmd.append("--no-webui")

        if extra_args:
            cmd.extend(extra_args)

        # Merge environment variables
        env = os.environ.copy()
        if custom_env:
            env.update(custom_env)

        # Ensure unbuffered output
        env["PYTHONUNBUFFERED"] = "1"

        try:
            self._process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,  # Merge stderr into stdout for unified logs
                stdin=subprocess.DEVNULL,
                text=True,
                bufsize=1,
                env=env,
            )
        except Exception as e:
            with self._status_lock:
                self._status.is_running = False
                self._status.is_ready = False
                self._status.error_message = str(e)
            return False

        with self._status_lock:
            self._status.is_running = True
            self._status.is_ready = False
            self._status.pid = self._process.pid
            self._status.model_name = os.path.basename(model_path)
            self._status.model_path = model_path
            self._status.base_url = f"http://{host}:{port}/v1"
            self._status.exit_code = None
            self._status.error_message = None

        # Start stream reader thread
        self._reader_thread = threading.Thread(target=self._stream_logs, daemon=True)
        self._reader_thread.start()

        # Start health check probe
        self._stop_health.clear()
        self._health_thread = threading.Thread(
            target=self._probe_health,
            args=(f"http://{host}:{port}/health",),
            daemon=True,
        )
        self._health_thread.start()

        return True

    def stop(self, timeout: float = 4.0) -> None:
        """Gracefully stop llama-server."""
        self._stop_health.set()
        if self._process is not None:
            try:
                self._process.terminate()
                self._process.wait(timeout=timeout)
            except Exception:
                try:
                    self._process.kill()
                except Exception:
                    pass
            self._process = None

        with self._status_lock:
            self._status.is_running = False
            self._status.is_ready = False
            self._status.pid = None

    def _stream_logs(self) -> None:
        """Stream log lines from process stdout."""
        proc = self._process
        if not proc or not proc.stdout:
            return

        for line in iter(proc.stdout.readline, ""):
            clean_line = line.rstrip("\r\n")
            if not clean_line:
                continue

            with self._log_lock:
                self._logs.append(clean_line)

            # Detect server ready signal in logs
            ready_signals = [
                "HTTP server listening",
                "all slots are idle",
                "model loaded",
                "llama server listening",
            ]
            if any(sig.lower() in clean_line.lower() for sig in ready_signals):
                with self._status_lock:
                    self._status.is_ready = True

            if self._on_log_callback:
                try:
                    self._on_log_callback(clean_line)
                except Exception:
                    pass

        # Subprocess finished
        proc.wait()
        with self._status_lock:
            self._status.is_running = False
            self._status.is_ready = False
            self._status.exit_code = proc.returncode

    def _probe_health(self, health_url: str) -> None:
        """Probe the server /health endpoint periodically until online."""
        while not self._stop_health.is_set():
            if not self._status.is_running:
                break
            try:
                req = urllib.request.Request(health_url, headers={"User-Agent": "TUI-Llama-Server"})
                with urllib.request.urlopen(req, timeout=1.5) as resp:
                    if resp.status == 200:
                        with self._status_lock:
                            self._status.is_ready = True
                        break
            except Exception:
                pass
            time.sleep(1.0)

    def get_logs(self) -> List[str]:
        with self._log_lock:
            return list(self._logs)

    def clear_logs(self) -> None:
        with self._log_lock:
            self._logs.clear()
