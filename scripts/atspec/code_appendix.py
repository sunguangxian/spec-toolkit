import re
from pathlib import Path
from typing import Any, Dict, List

from .core import ROOT, get_localized, load_yaml


LANGUAGE_BY_SUFFIX = {
    ".c": "c",
    ".h": "c",
    ".cpp": "cpp",
    ".hpp": "cpp",
    ".cs": "csharp",
    ".py": "python",
    ".java": "java",
    ".js": "javascript",
    ".ts": "typescript",
    ".md": "markdown",
    ".txt": "text",
}


def make_appendix_anchor(value: str) -> str:
    text = re.sub(r"[^0-9A-Za-z_+-]+", "-", value or "")
    return f"appendix-{text.strip('-').lower() or 'code'}"


def _model_matches(entry: Dict[str, Any], model: Dict[str, Any]) -> bool:
    models = entry.get("models")
    if not models:
        return True
    if isinstance(models, str):
        models = [models]
    allowed = {str(item).lower() for item in models}
    if "*" in allowed or "all" in allowed:
        return True
    model_ids = {
        str(model.get("model_id", "")).lower(),
        str(model.get("model_name", "")).lower(),
    }
    return bool(allowed & model_ids)


def _visibility_matches(entry: Dict[str, Any], model: Dict[str, Any]) -> bool:
    visibility = str(entry.get("visibility", "customer")).lower()
    if visibility in {"all", "both", "public"}:
        return True

    options = model.get("options", {}) or {}
    internal_doc = bool(options.get("show_internal_notes", False))

    if internal_doc:
        return visibility in {"customer", "internal"}
    return visibility == "customer"


def _normalize_file_item(item: Any, default_language: str | None = None) -> Dict[str, str]:
    if isinstance(item, str):
        path = item
        title = Path(path).name
        language = default_language
    elif isinstance(item, dict):
        path = item.get("path") or item.get("file")
        title = item.get("title") or Path(str(path or "")).name
        language = item.get("language") or default_language
    else:
        raise ValueError(f"Invalid code appendix file item: {item!r}")

    if not path:
        raise ValueError("Code appendix file item is missing path")

    file_path = (ROOT / path).resolve()
    try:
        file_path.relative_to(ROOT.resolve())
    except ValueError as exc:
        raise ValueError(f"Code appendix file path escapes repository root: {path}") from exc

    if not file_path.exists():
        raise FileNotFoundError(f"Code appendix file not found: {path}")

    suffix_language = LANGUAGE_BY_SUFFIX.get(file_path.suffix.lower(), "text")
    return {
        "path": str(path).replace("\\", "/"),
        "title": str(title),
        "language": str(language or suffix_language),
        "content": file_path.read_text(encoding="utf-8"),
    }


def load_code_appendices(model: Dict[str, Any]) -> List[Dict[str, Any]]:
    config_path = ROOT / "appendices" / "code_appendices.yaml"
    if not config_path.exists():
        return []

    data = load_yaml(config_path) or {}
    entries = data.get("appendices", []) or []
    language = model.get("language", "zh")
    result = []

    for entry in entries:
        if not isinstance(entry, dict):
            continue
        if not _model_matches(entry, model):
            continue
        if not _visibility_matches(entry, model):
            continue

        files = [
            _normalize_file_item(item, entry.get("language"))
            for item in (entry.get("files") or [])
        ]
        if not files:
            continue

        appendix_id = str(entry.get("id") or files[0]["path"])
        result.append({
            "id": appendix_id,
            "anchor": make_appendix_anchor(appendix_id),
            "title": get_localized(entry.get("title"), language) or appendix_id,
            "description": get_localized(entry.get("description"), language),
            "visibility": str(entry.get("visibility", "customer")),
            "files": files,
        })

    return result
