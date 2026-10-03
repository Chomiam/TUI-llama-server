"""TUI-llama-server: Premium Terminal Dashboard & Manager for llama.cpp server."""

import os
from typing import List, Optional

from rich.text import Text
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.reactive import reactive
from textual.widgets import (
    Button,
    DataTable,
    Footer,
    Header,
    Input,
    Label,
    ProgressBar,
    RichLog,
    Static,
    TabbedContent,
    TabPane,
)

from tui_llama_server.detector import (
    GPUInfo,
    detect_system_gpus,
    find_llama_server_binary,
)
from tui_llama_server.model_scanner import ModelInfo, scan_models_dir
from tui_llama_server.monitor import PerformanceMetrics, SystemMonitor
from tui_llama_server.server_manager import ServerManager
from tui_llama_server.utils import copy_text_to_clipboard, load_user_config, save_user_config


class TuiLlamaApp(App):
    CSS_PATH = "ui/styles.tcss"
    TITLE = "TUI · llama-server"
    SUB_TITLE = "GPU & ROCm Agent Inference Dashboard"

    BINDINGS = [
        Binding("f1", "switch_tab('tab-models')", "Models", priority=True),
        Binding("f2", "switch_tab('tab-monitor')", "Monitor", priority=True),
        Binding("f3", "switch_tab('tab-logs')", "Logs", priority=True),
        Binding("f4", "switch_tab('tab-flags')", "Flags & ROCm", priority=True),
        Binding("space", "toggle_server", "Start/Stop Server"),
        Binding("ctrl+y", "copy_base_url", "Copy Base URL"),
        Binding("ctrl+l", "copy_logs", "Copy Logs"),
        Binding("q", "quit_app", "Quit"),
    ]

    # Reactive states
    server_running = reactive(False)
    server_ready = reactive(False)
    selected_model: reactive[Optional[ModelInfo]] = reactive(None)

    def __init__(self, models_dir: Optional[str] = None):
        super().__init__()
        self.config = load_user_config()
        if models_dir:
            self.config["models_dir"] = models_dir

        self.gpus: List[GPUInfo] = detect_system_gpus()
        self.primary_gpu: GPUInfo = self.gpus[0] if self.gpus else GPUInfo(vendor="cpu", name="CPU")
        self.llama_binary = find_llama_server_binary()
        self.models: List[ModelInfo] = []

        self.monitor = SystemMonitor(vendor=self.primary_gpu.vendor)
        self.server = ServerManager()
        self.server.set_log_callback(self._on_server_log)

    def compose(self) -> ComposeResult:
        # Top Header Bar
        with Horizontal(id="header-container"):
            yield Static("λ TUI-LLAMA-SERVER", id="app-title")
            
            # Hardware badge (shows ROCm version and GFX arch if AMD)
            hw_text = f"{self.primary_gpu.name}"
            if self.primary_gpu.vendor == "amd":
                rocm_str = f"ROCm {self.primary_gpu.rocm_version or 'N/A'}"
                gfx_str = f" · {self.primary_gpu.gfx_arch}" if self.primary_gpu.gfx_arch else ""
                hw_text = f"[{rocm_str}{gfx_str}]  {self.primary_gpu.name}"
            yield Static(hw_text, id="hardware-badge")

            # Status badge
            yield Static("○ STOPPED", id="server-status-badge", classes="status-stopped")

            # Base URL Badge & Copy action
            base_url = f"http://{self.config['host']}:{self.config['port']}/v1"
            yield Static(base_url, id="base-url-badge")
            yield Button("📋 Copy URL", id="btn-copy-url")

        # Main Navigation Tabs
        with TabbedContent(initial="tab-models", id="main-tabs"):
            # TAB 1: Models & Inspector
            with TabPane("Models & Engine", id="tab-models"):
                with Horizontal(id="models-container"):
                    with Vertical(id="models-list-panel"):
                        yield Label(f"Discovered GGUF Models ({self.config['models_dir']})", classes="panel-header")
                        yield DataTable(id="models-table", cursor_type="row")

                    with Vertical(id="models-detail-panel"):
                        yield Label("Model Characteristics & Flags", classes="panel-header")
                        yield Static(id="model-detail-card")

            # TAB 2: Real-time Monitor & Agent Connectivity
            with TabPane("Live Performance", id="tab-monitor"):
                with Horizontal(id="monitor-grid"):
                    with Vertical(classes="metric-card"):
                        yield Label("Hardware Utilization", classes="panel-header")

                        # GPU Busy Meter
                        with Vertical(classes="meter-row"):
                            with Horizontal(classes="meter-label-row"):
                                yield Label("GPU Utilization", classes="meter-name")
                                yield Label("0%", id="val-gpu-busy", classes="meter-value")
                            yield ProgressBar(total=100, show_eta=False, id="bar-gpu-busy")

                        # VRAM Meter
                        with Vertical(classes="meter-row"):
                            with Horizontal(classes="meter-label-row"):
                                yield Label("VRAM Memory", classes="meter-name")
                                yield Label("0 / 0 GB", id="val-vram", classes="meter-value")
                            yield ProgressBar(total=100, show_eta=False, id="bar-vram")

                        # RAM Meter
                        with Vertical(classes="meter-row"):
                            with Horizontal(classes="meter-label-row"):
                                yield Label("System RAM", classes="meter-name")
                                yield Label("0 / 0 GB", id="val-ram", classes="meter-value")
                            yield ProgressBar(total=100, show_eta=False, id="bar-ram")

                        # CPU Meter
                        with Vertical(classes="meter-row"):
                            with Horizontal(classes="meter-label-row"):
                                yield Label("CPU Utilization", classes="meter-name")
                                yield Label("0%", id="val-cpu", classes="meter-value")
                            yield ProgressBar(total=100, show_eta=False, id="bar-cpu")

                        # Swap Meter
                        with Vertical(classes="meter-row"):
                            with Horizontal(classes="meter-label-row"):
                                yield Label("System Swap", classes="meter-name")
                                yield Label("0 / 0 GB", id="val-swap", classes="meter-value")
                            yield ProgressBar(total=100, show_eta=False, id="bar-swap")

                    with Vertical(classes="metric-card"):
                        yield Label("AI Agent Endpoints (OpenAI-compatible)", classes="panel-header")
                        with Vertical(id="agent-endpoints-box"):
                            yield Static("● Base URL:      " + base_url, classes="endpoint-line")
                            yield Static("● Chat API:      /v1/chat/completions", classes="endpoint-line")
                            yield Static("● Models List:   /v1/models", classes="endpoint-line")
                            yield Static("● Embeddings:    /v1/embeddings", classes="endpoint-line")
                            yield Static("● Health Status: /health", classes="endpoint-line")
                            yield Static(
                                "\n[dim]Designed for autonomous agents (Cline, Continue, Open-Devin, Antigravity).\n"
                                "Headless server mode is enabled (--no-webui) for maximum GPU memory efficiency.[/dim]",
                                classes="agent-desc",
                            )

            # TAB 3: Live Logs Console
            with TabPane("Console & Logs", id="tab-logs"):
                with Vertical(id="logs-container"):
                    with Horizontal(id="logs-toolbar"):
                        yield Input(placeholder="Filter logs...", id="log-filter-input")
                        yield Button("📋 Copy All Logs", id="btn-copy-logs", classes="tool-button")
                        yield Button("🗑️ Clear", id="btn-clear-logs", classes="tool-button")
                    yield RichLog(id="log-view", highlight=True, markup=True, wrap=True)

            # TAB 4: GPU & ROCm Flags Configuration
            with TabPane("Flags & Settings", id="tab-flags"):
                with Vertical(classes="metric-card"):
                    yield Label("Hardware & Auto-Tuned Flags", classes="panel-header")
                    yield Static(id="flags-info-text")

                    yield Label("\nEngine Tuning Options", classes="panel-header")
                    with Horizontal():
                        yield Label("Host: ", classes="detail-label")
                        yield Input(value=self.config["host"], id="cfg-host")
                    with Horizontal():
                        yield Label("Port: ", classes="detail-label")
                        yield Input(value=str(self.config["port"]), id="cfg-port")
                    with Horizontal():
                        yield Label("Context Size: ", classes="detail-label")
                        yield Input(value=str(self.config["ctx_size"]), id="cfg-ctx")
                    with Horizontal():
                        yield Label("GPU Layers: ", classes="detail-label")
                        yield Input(value=str(self.config["n_gpu_layers"]), id="cfg-layers")
                    with Horizontal():
                        yield Label("CPU Threads: ", classes="detail-label")
                        yield Input(value=str(self.config["threads"]), id="cfg-threads")

                    with Horizontal(classes="meter-row"):
                        yield Button("💾 Save Settings", id="btn-save-cfg", classes="btn-primary")

        # Bottom Server Control Bar
        with Horizontal(id="server-controls-bar"):
            yield Button("▶ Launch Server", id="btn-toggle-server", classes="btn-primary")
            yield Static("Select a model and press Launch or [Space]", id="controls-hint")

        yield Footer()

    def on_mount(self) -> None:
        """Initialize data on startup."""
        self._setup_models_table()
        self._refresh_models()
        self._update_flags_view()

        # Start periodic 1-second hardware monitoring timer
        self.set_interval(1.0, self._on_monitor_tick)

    def _setup_models_table(self) -> None:
        table = self.query_one("#models-table", DataTable)
        table.add_columns("Model File", "Quant", "Size", "Tools")

    def _refresh_models(self) -> None:
        models_dir = self.config.get("models_dir")
        self.models = scan_models_dir(models_dir)
        table = self.query_one("#models-table", DataTable)
        table.clear()

        for idx, m in enumerate(self.models):
            tool_badge = "✓ Yes" if m.has_tool_calling else "—"
            table.add_row(m.filename, m.quantization, f"{m.size_gb} GB", tool_badge, key=str(idx))

        if self.models:
            table.move_cursor(row=0)
            self.selected_model = self.models[0]
            self._render_model_details(self.selected_model)

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        try:
            idx = int(event.row_key.value)
            if 0 <= idx < len(self.models):
                self.selected_model = self.models[idx]
                self._render_model_details(self.selected_model)
        except Exception:
            pass

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        try:
            idx = int(event.row_key.value)
            if 0 <= idx < len(self.models):
                self.selected_model = self.models[idx]
                self._render_model_details(self.selected_model)
        except Exception:
            pass

    def _render_model_details(self, model: Optional[ModelInfo]) -> None:
        card = self.query_one("#model-detail-card", Static)
        if not model:
            card.update("[dim]No model selected[/dim]")
            return

        tool_str = "[bold green]✓ Available[/bold green]" if model.has_tool_calling else "[dim]No explicit schema[/dim]"
        vram_warning = ""
        if self.primary_gpu.vram_total_mb > 0:
            tot_gb = self.primary_gpu.vram_total_mb / 1024.0
            if model.estimated_vram_gb > tot_gb:
                vram_warning = f"  [bold red]⚠️ Exceeds VRAM ({tot_gb:.1f} GB)[/bold red]"

        lines = [
            f"[bold cyan]{model.name}[/bold cyan]",
            f"[dim]{model.filename}[/dim]\n",
            f"[bold]Architecture:[/bold]       {model.architecture}",
            f"[bold]Quantization:[/bold]       [bold yellow]{model.quantization}[/bold yellow]",
            f"[bold]Context Window:[/bold]     {model.context_length:,} tokens",
            f"[bold]Blocks / Layers:[/bold]    {model.block_count}",
            f"[bold]Embedding Dim:[/bold]      {model.embedding_length}",
            f"[bold]Attention Heads:[/bold]    {model.head_count} (KV: {model.head_count_kv})",
            f"[bold]Chat Template:[/bold]      {model.chat_template_type}",
            f"[bold]Function Calling:[/bold]   {tool_str}",
            f"[bold]File Size on Disk:[/bold]  {model.size_gb} GB",
            f"[bold]Est. VRAM Needed:[/bold]   [bold magenta]{model.estimated_vram_gb} GB[/bold magenta]{vram_warning}",
            "\n[bold]Auto-Tuned Engine Flags:[/bold]",
            f"  • GPU Layers:   -ngl {self.config['n_gpu_layers']}",
            f"  • Flash Attn:   --flash-attn {self.config['flash_attn']}",
            f"  • CPU Threads:  -t {self.config['threads']}",
            "  • Mode:         --no-webui (API server for Agents)",
        ]
        card.update("\n".join(lines))

    def _update_flags_view(self) -> None:
        txt = self.query_one("#flags-info-text", Static)
        env_lines = []
        for k, v in self.primary_gpu.recommended_env.items():
            env_lines.append(f"  • [bold green]{k}[/bold green]={v}")
        if not env_lines:
            env_lines.append("  [dim]None required for current hardware[/dim]")

        gpu_info_lines = [
            f"[bold]GPU Vendor:[/bold]       {self.primary_gpu.vendor.upper()}",
            f"[bold]Device Name:[/bold]      {self.primary_gpu.name}",
            f"[bold]ROCm Version:[/bold]     {self.primary_gpu.rocm_version or 'N/A'}",
            f"[bold]GFX Target Arch:[/bold]  [bold cyan]{self.primary_gpu.gfx_arch or 'N/A'}[/bold cyan]",
            f"[bold]Total VRAM:[/bold]        {self.primary_gpu.vram_total_mb / 1024:.2f} GB",
            f"[bold]Llama Server:[/bold]      {self.llama_binary or '[bold red]Not Found[/bold red]'}\n",
            "[bold]Recommended ROCm Environment Variables:[/bold]",
            *env_lines,
        ]
        txt.update("\n".join(gpu_info_lines))

    def _on_monitor_tick(self) -> None:
        """Sample system and GPU performance and update meters."""
        m: PerformanceMetrics = self.monitor.sample()

        # Update GPU & VRAM
        self.query_one("#val-gpu-busy", Label).update(f"{m.gpu_busy_pct}%")
        self.query_one("#bar-gpu-busy", ProgressBar).progress = m.gpu_busy_pct

        self.query_one("#val-vram", Label).update(f"{m.vram_used_gb:.1f} / {m.vram_total_gb:.1f} GB ({m.vram_pct:.0f}%)")
        self.query_one("#bar-vram", ProgressBar).progress = m.vram_pct

        # Update RAM, CPU, Swap
        self.query_one("#val-ram", Label).update(f"{m.ram_used_gb:.1f} / {m.ram_total_gb:.1f} GB ({m.ram_pct:.0f}%)")
        self.query_one("#bar-ram", ProgressBar).progress = m.ram_pct

        self.query_one("#val-cpu", Label).update(f"{m.cpu_pct}%")
        self.query_one("#bar-cpu", ProgressBar).progress = m.cpu_pct

        self.query_one("#val-swap", Label).update(f"{m.swap_used_gb:.1f} / {m.swap_total_gb:.1f} GB ({m.swap_pct:.0f}%)")
        self.query_one("#bar-swap", ProgressBar).progress = m.swap_pct

        # Update server status indicators
        status = self.server.status
        self.server_running = status.is_running
        self.server_ready = status.is_ready

        badge = self.query_one("#server-status-badge", Static)
        btn_toggle = self.query_one("#btn-toggle-server", Button)
        hint = self.query_one("#controls-hint", Static)

        if status.is_running:
            if status.is_ready:
                badge.update("● ONLINE (READY)")
                badge.classes = "status-running"
                hint.update(f"Running: {status.model_name} on {status.base_url}")
            else:
                badge.update("◌ LOADING MODEL...")
                badge.classes = "status-stopped"
                hint.update("Initializing weights into VRAM...")
            btn_toggle.label = "⏹ Stop Server"
            btn_toggle.classes = "btn-stop"
        else:
            if status.exit_code is not None and status.exit_code != 0:
                badge.update(f"✕ ERROR (Code {status.exit_code})")
                badge.classes = "status-error"
                hint.update("Server terminated with error. Check Console / Logs tab.")
            else:
                badge.update("○ STOPPED")
                badge.classes = "status-stopped"
                hint.update("Select a model and press Launch or [Space]")
            btn_toggle.label = "▶ Launch Server"
            btn_toggle.classes = "btn-primary"

    def _on_server_log(self, line: str) -> None:
        """Receives log lines asynchronously from llama-server process."""
        self.call_from_thread(self._append_log_line, line)

    def _append_log_line(self, line: str) -> None:
        try:
            log_view = self.query_one("#log-view", RichLog)
            filter_val = self.query_one("#log-filter-input", Input).value.strip().lower()
            if filter_val and filter_val not in line.lower():
                return

            if "error" in line.lower() or "fail" in line.lower():
                log_view.write(Text(line, style="bold red"))
            elif "warn" in line.lower():
                log_view.write(Text(line, style="bold yellow"))
            elif "listening" in line.lower() or "slot" in line.lower():
                log_view.write(Text(line, style="bold green"))
            else:
                log_view.write(line)
        except Exception:
            pass

    # Actions and Event Handlers
    def action_switch_tab(self, tab_id: str) -> None:
        self.query_one("#main-tabs", TabbedContent).active = tab_id

    def action_toggle_server(self) -> None:
        if self.server.status.is_running:
            self.server.stop()
            self.notify("llama-server stopped", title="Server")
        else:
            if not self.selected_model:
                self.notify("Please select a model first!", severity="warning")
                return
            if not self.llama_binary:
                self.notify("llama-server binary not found in PATH or standard locations!", severity="error")
                return

            # Combine recommended env with user overrides
            custom_env = dict(self.primary_gpu.recommended_env)
            custom_env.update(self.config.get("env_overrides", {}))

            success = self.server.start(
                binary_path=self.llama_binary,
                model_path=self.selected_model.filepath,
                host=self.config["host"],
                port=int(self.config["port"]),
                ctx_size=int(self.config["ctx_size"]),
                n_gpu_layers=int(self.config["n_gpu_layers"]),
                threads=int(self.config["threads"]),
                flash_attn=self.config.get("flash_attn", "auto"),
                no_webui=self.config.get("no_webui", True),
                custom_env=custom_env,
            )

            if success:
                self.notify(f"Launching {self.selected_model.filename}...", title="Engine")
                self.action_switch_tab("tab-logs")
            else:
                self.notify("Failed to spawn llama-server process", severity="error")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        btn_id = event.button.id
        if btn_id == "btn-toggle-server":
            self.action_toggle_server()
        elif btn_id == "btn-copy-url":
            self.action_copy_base_url()
        elif btn_id == "btn-copy-logs":
            self.action_copy_logs()
        elif btn_id == "btn-clear-logs":
            self.server.clear_logs()
            self.query_one("#log-view", RichLog).clear()
            self.notify("Logs cleared")
        elif btn_id == "btn-save-cfg":
            self._save_settings()

    def action_copy_base_url(self) -> None:
        url = f"http://{self.config['host']}:{self.config['port']}/v1"
        copied = copy_text_to_clipboard(url)
        try:
            self.copy_to_clipboard(url)
        except Exception:
            pass
        self.notify(f"Copied to clipboard: {url}", title="API Base URL")

    def action_copy_logs(self) -> None:
        logs = self.server.get_logs()
        if not logs:
            self.notify("No logs to copy", severity="information")
            return
        full_text = "\n".join(logs)
        copy_text_to_clipboard(full_text)
        try:
            self.copy_to_clipboard(full_text)
        except Exception:
            pass
        self.notify(f"Copied {len(logs)} log lines to clipboard!", title="Logs")

    def _save_settings(self) -> None:
        try:
            self.config["host"] = self.query_one("#cfg-host", Input).value.strip()
            self.config["port"] = int(self.query_one("#cfg-port", Input).value.strip())
            self.config["ctx_size"] = int(self.query_one("#cfg-ctx", Input).value.strip())
            self.config["n_gpu_layers"] = int(self.query_one("#cfg-layers", Input).value.strip())
            self.config["threads"] = int(self.query_one("#cfg-threads", Input).value.strip())
            save_user_config(self.config)
            self.notify("Configuration saved to ~/.config/tui-llama-server/config.json")
        except Exception as e:
            self.notify(f"Error saving config: {e}", severity="error")

    def action_quit_app(self) -> None:
        if self.server.status.is_running:
            self.server.stop()
        self.exit()
