from typing import Any, Dict, List

from .core import get_localized


def load_error_code_appendix(model: Dict[str, Any], command_specs: List[Dict[str, Any]]) -> Dict[str, Any] | None:
    """Return COMMON_ERROR_CODES as an appendix table instead of a command section."""
    language = model.get("language", "zh")
    model_id = str(model.get("model_id", "")).lower()

    cmd = next((item for item in command_specs if item.get("id") == "COMMON_ERROR_CODES"), None)
    if not cmd:
        return None

    since = cmd.get("since") or {}
    if since and model_id not in {str(key).lower() for key in since.keys()}:
        return None

    params = []
    raw_params = cmd.get("parameters") or {}
    if isinstance(raw_params, dict):
        raw_params = raw_params.get("default", raw_params)
    for item in raw_params or []:
        if not isinstance(item, dict):
            continue
        params.append({
            "code": str(item.get("name", "")),
            "description": get_localized(item.get("description"), language),
        })

    if not params:
        return None

    return {
        "id": "error_codes",
        "anchor": "appendix-error-codes",
        "title": "错误码说明" if language == "zh" else "Error Code Table",
        "description": get_localized(cmd.get("summary"), language),
        "parameters": params,
    }
