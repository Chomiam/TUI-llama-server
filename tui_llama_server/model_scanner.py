"""GGUF Model scanner & deep metadata inspector with caching."""

import datetime
import json
import os
import re
from dataclasses import asdict, dataclass, field
from typing import Dict, List, Optional
import gguf


@dataclass
class ModelInfo:
    filepath: str
    filename: str
    size_bytes: int
    size_gb: float
    mtime_ts: float
    mtime_str: str = ""
    architecture: str = "Unknown"
    name: str = ""
    quantization: str = "Unknown"
    context_length: int = 4096
    block_count: int = 0  # Number of layers
    embedding_length: int = 0
    head_count: int = 0
    head_count_kv: int = 0
    expert_count: int = 0  # For MoE models
    tensor_count: int = 0
    chat_template_type: str = "Standard"
    has_tool_calling: bool = False
    estimated_vram_gb: float = 0.0


def _decode_field(field_obj) -> str:
    """Decode gguf field value to clean string."""
    if field_obj is None:
        return ""
    val = field_obj.parts[-1]
    if hasattr(val, "tobytes"):
        try:
            return bytes(val).decode("utf-8", errors="ignore").strip()
        except Exception:
            return str(val)
    if isinstance(val, (bytes, bytearray)):
        return val.decode("utf-8", errors="ignore").strip()
    return str(val)


def _decode_int(field_obj, default: int = 0) -> int:
    """Decode integer field."""
    if field_obj is None:
        return default
    try:
        val = field_obj.parts[-1]
        if hasattr(val, "__getitem__"):
            return int(val[0])
        return int(val)
    except Exception:
        return default


def _extract_quantization(filename: str, reader: gguf.GGUFReader) -> str:
    """Extract clean quantization name."""
    # Match standard quantization patterns from filename
    m = re.search(r"[-_.]([I]?[Qq]\d+_[A-Za-z0-9_]+|q\d+|[Bb]?[Ff]16)[-_.]?", filename)
    if m:
        return m.group(1).upper()

    ftype_field = reader.fields.get("general.file_type")
    if ftype_field:
        try:
            code = _decode_int(ftype_field, -1)
            enum_val = gguf.GGMLQuantizationType(code)
            return enum_val.name.upper()
        except Exception:
            pass

    return "GGUF Quantized"


def _detect_template_type(chat_tmpl: str) -> str:
    """Detect template family from Jinja template."""
    tmpl_lower = chat_tmpl.lower()
    if "<|im_start|>" in tmpl_lower:
        return "ChatML"
    if "<|start_header_id|>" in tmpl_lower:
        return "Llama-3"
    if "[inst]" in tmpl_lower:
        return "Mistral / Llama-2"
    if "gemma" in tmpl_lower:
        return "Gemma"
    if "deepseek" in tmpl_lower:
        return "DeepSeek"
    if "<|system|>" in tmpl_lower:
        return "ChatGLM / Phi"
    return "Custom Jinja"


def parse_gguf_metadata(filepath: str) -> ModelInfo:
    """Extract deep architecture and runtime metadata from a GGUF model file."""
    st = os.stat(filepath)
    size_bytes = st.st_size
    size_gb = round(size_bytes / (1024 ** 3), 2)
    mtime = datetime.datetime.fromtimestamp(st.st_mtime)
    filename = os.path.basename(filepath)

    model = ModelInfo(
        filepath=filepath,
        filename=filename,
        size_bytes=size_bytes,
        size_gb=size_gb,
        mtime_ts=st.st_mtime,
        mtime_str=mtime.strftime("%Y-%m-%d %H:%M"),
    )

    try:
        reader = gguf.GGUFReader(filepath)
        model.tensor_count = len(reader.tensors)

        # 1. Architecture
        arch_field = reader.fields.get("general.architecture")
        arch = _decode_field(arch_field) if arch_field else "llama"
        model.architecture = arch

        # 2. Model Name
        name_field = reader.fields.get("general.name")
        if name_field:
            model.name = _decode_field(name_field)
        else:
            model.name = os.path.splitext(filename)[0]

        # 3. Context Length
        ctx_field = reader.fields.get(f"{arch}.context_length") or reader.fields.get("general.context_length")
        if ctx_field:
            model.context_length = _decode_int(ctx_field, default=4096)

        # 4. Layers / Block count
        block_field = reader.fields.get(f"{arch}.block_count")
        if block_field:
            model.block_count = _decode_int(block_field, default=0)

        # 5. Embedding length
        emb_field = reader.fields.get(f"{arch}.embedding_length")
        if emb_field:
            model.embedding_length = _decode_int(emb_field, default=0)

        # 6. Attention Heads
        head_field = reader.fields.get(f"{arch}.attention.head_count")
        if head_field:
            model.head_count = _decode_int(head_field, default=0)

        head_kv_field = reader.fields.get(f"{arch}.attention.head_count_kv")
        if head_kv_field:
            model.head_count_kv = _decode_int(head_kv_field, default=0)

        # 7. MoE Experts
        expert_field = reader.fields.get(f"{arch}.expert_count") or reader.fields.get(f"{arch}.expert_used_count")
        if expert_field:
            model.expert_count = _decode_int(expert_field, default=0)

        # 8. Quantization Scheme
        model.quantization = _extract_quantization(filename, reader)

        # 9. Chat Template & Tool Calling Capability
        tmpl_field = reader.fields.get("tokenizer.chat_template")
        if tmpl_field:
            tmpl_text = _decode_field(tmpl_field)
            model.chat_template_type = _detect_template_type(tmpl_text)
            tool_keywords = [
                "<tools>", "<tool_call>", "[AVAILABLE_TOOLS]", "tools:", "tool_response", "tools is defined"
            ]
            if any(k in tmpl_text for k in tool_keywords):
                model.has_tool_calling = True

        # 10. Estimated VRAM Requirement (Model size + KV cache + context buffer)
        model.estimated_vram_gb = round(size_gb * 1.15 + 0.8, 1)

    except Exception:
        model.name = os.path.splitext(filename)[0]
        model.quantization = _extract_quantization(filename, None)
        model.estimated_vram_gb = round(size_gb * 1.2, 1)

    return model


_CACHE_FILE = os.path.expanduser("~/.cache/tui-llama-server/models_cache.json")


def _load_cache() -> Dict[str, dict]:
    if os.path.exists(_CACHE_FILE):
        try:
            with open(_CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def _save_cache(cache: Dict[str, dict]) -> None:
    try:
        os.makedirs(os.path.dirname(_CACHE_FILE), exist_ok=True)
        with open(_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(cache, f, indent=2)
    except Exception:
        pass


def scan_models_dir(directory: Optional[str] = None) -> List[ModelInfo]:
    """Scan directory for .gguf model files with persistent metadata cache."""
    if not directory:
        user_home = os.path.expanduser("~")
        directory = os.path.join(user_home, "models")

    if not os.path.isdir(directory):
        return []

    cache = _load_cache()
    dirty = False
    models: List[ModelInfo] = []

    try:
        entries = sorted(os.listdir(directory))
        for entry in entries:
            if entry.lower().endswith(".gguf") and not entry.startswith("."):
                full_path = os.path.join(directory, entry)
                if not os.path.isfile(full_path):
                    continue

                mtime = os.path.getmtime(full_path)
                cached_entry = cache.get(full_path)

                if cached_entry and cached_entry.get("mtime_ts") == mtime:
                    # Construct from cache
                    d = dict(cached_entry)
                    models.append(ModelInfo(**d))
                else:
                    info = parse_gguf_metadata(full_path)
                    cache[full_path] = asdict(info)
                    dirty = True
                    models.append(info)

        if dirty:
            _save_cache(cache)
    except Exception:
        pass

    return models
