import re
import shutil
from pathlib import Path
from typing import Any, Dict, List

from .core import ROOT, get_localized, load_yaml

IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".svg", ".webp"}


def make_image_anchor(value: str) -> str:
    text = re.sub(r"[^0-9A-Za-z_+-]+", "-", value or "")
    return f"appendix-image-{text.strip('-').lower() or 'figure'}"


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


def _safe_repo_path(path: str) -> Path:
    file_path = (ROOT / path).resolve()
    try:
        file_path.relative_to(ROOT.resolve())
    except ValueError as exc:
        raise ValueError(f"Image appendix path escapes repository root: {path}") from exc
    return file_path


def _normalize_image_item(item: Any, language: str) -> Dict[str, str]:
    if isinstance(item, str):
        path = item
        caption = Path(path).stem
        alt = caption
    elif isinstance(item, dict):
        path = item.get("path") or item.get("file")
        caption = get_localized(item.get("caption"), language) or Path(str(path or "")).stem
        alt = get_localized(item.get("alt"), language) or caption
    else:
        raise ValueError(f"Invalid image appendix item: {item!r}")

    if not path:
        raise ValueError("Image appendix item is missing path")

    file_path = _safe_repo_path(str(path))
    if not file_path.exists():
        raise FileNotFoundError(f"Image appendix file not found: {path}")
    if file_path.suffix.lower() not in IMAGE_SUFFIXES:
        raise ValueError(f"Unsupported image appendix file type: {path}")

    normalized_path = str(path).replace("\\", "/")
    return {
        "path": normalized_path,
        "src": normalized_path,
        "caption": str(caption),
        "alt": str(alt),
    }


def load_image_appendices(model: Dict[str, Any]) -> List[Dict[str, Any]]:
    config_path = ROOT / "appendices" / "image_appendices.yaml"
    if not config_path.exists():
        return []

    data = load_yaml(config_path) or {}
    entries = data.get("appendices", []) or []
    language = model.get("language", "zh")
    result: List[Dict[str, Any]] = []

    for entry in entries:
        if not isinstance(entry, dict):
            continue
        if not _model_matches(entry, model):
            continue
        if not _visibility_matches(entry, model):
            continue

        images = [
            _normalize_image_item(item, language)
            for item in (entry.get("images") or [])
        ]
        if not images:
            continue

        appendix_id = str(entry.get("id") or images[0]["path"])
        result.append({
            "id": appendix_id,
            "anchor": make_image_anchor(appendix_id),
            "title": get_localized(entry.get("title"), language) or appendix_id,
            "description": get_localized(entry.get("description"), language),
            "visibility": str(entry.get("visibility", "customer")),
            "images": images,
        })

    return result


def copy_image_assets(image_appendices: List[Dict[str, Any]], output_dir: Path) -> None:
    for appendix in image_appendices:
        for image in appendix.get("images", []):
            src = _safe_repo_path(str(image["path"]))
            dst = output_dir / image["src"]
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
