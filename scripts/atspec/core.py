import copy, os, pathlib, yaml
from typing import Any, Dict, Iterable, List, Set

TOOLKIT_ROOT = pathlib.Path(__file__).resolve().parents[2]


def find_spec_root() -> pathlib.Path:
    env_root = os.environ.get("SPEC_ROOT")
    if env_root:
        return pathlib.Path(env_root).resolve()

    cwd = pathlib.Path.cwd().resolve()
    markers = ("commands", "models", "profiles")
    if any((cwd / marker).exists() for marker in markers):
        return cwd

    return TOOLKIT_ROOT


ROOT = find_spec_root()
LIST_MERGE_FIELDS = ["include_categories", "exclude_commands", "command_order", "include_commands"]
DICT_MERGE_FIELDS = ["options", "features", "order_after"]
SUPPORTED_SYNTAX_KEYS = {"execute", "set", "read", "test", "write", "urc"}
SUPPORTED_VARIANT_GROUPS = {"by_model", "by_feature"}


def toolkit_path(*parts: str) -> pathlib.Path:
    return TOOLKIT_ROOT.joinpath(*parts)

def load_yaml(path: pathlib.Path) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def write_text(path: pathlib.Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")

def unique_extend(base: List[Any], extra: List[Any]) -> List[Any]:
    result = list(base or [])
    for item in extra or []:
        if item not in result:
            result.append(item)
    return result

def deep_merge_dict(base: Dict[str, Any], extra: Dict[str, Any]) -> Dict[str, Any]:
    result = copy.deepcopy(base or {})
    for key, value in (extra or {}).items():
        if isinstance(result.get(key), dict) and isinstance(value, dict):
            result[key] = deep_merge_dict(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result

def apply_order_after(order: List[str], rules: Dict[str, str]) -> List[str]:
    result = list(order or [])
    for command_id, anchor_id in (rules or {}).items():
        if command_id not in result:
            result.append(command_id)
        result = [item for item in result if item != command_id]
        try:
            result.insert(result.index(anchor_id) + 1, command_id)
        except ValueError:
            result.append(command_id)
    return result

def merge_profile(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    merged = copy.deepcopy(base)
    for key, value in override.items():
        if key in LIST_MERGE_FIELDS:
            merged[key] = unique_extend(merged.get(key, []), value or [])
        elif key in DICT_MERGE_FIELDS:
            merged[key] = deep_merge_dict(merged.get(key, {}) or {}, value or {})
        else:
            merged[key] = copy.deepcopy(value)
    merged["command_order"] = apply_order_after(merged.get("command_order", []), merged.get("order_after", {}) or {})
    return merged

def iter_command_files() -> Iterable[pathlib.Path]:
    commands_dir = ROOT / "commands"
    if not commands_dir.exists():
        return []
    for path in sorted(commands_dir.rglob("*.yaml")):
        if "archive" not in set(path.relative_to(commands_dir).parts):
            yield path

def iter_model_files() -> Iterable[pathlib.Path]:
    models_dir = ROOT / "models"
    if not models_dir.exists():
        return []
    for path in sorted(models_dir.glob("*.yaml")):
        if not path.name.startswith("_"):
            yield path

def iter_profile_files() -> Iterable[pathlib.Path]:
    profiles_dir = ROOT / "profiles"
    if not profiles_dir.exists():
        return []
    for path in sorted(profiles_dir.glob("*.yaml")):
        if not path.name.startswith("_"):
            yield path

def iter_model_ids() -> Iterable[str]:
    for path in iter_model_files():
        yield path.stem

def load_common_parameters() -> Dict[str, Dict[str, Any]]:
    path = ROOT / "common" / "enums.yaml"
    if not path.exists():
        return {}
    data = load_yaml(path) or {}
    params = data.get("parameters", {}) if isinstance(data, dict) else {}
    return params if isinstance(params, dict) else {}

def resolve_parameter_refs(value: Any, common_params: Dict[str, Dict[str, Any]]) -> Any:
    if isinstance(value, list):
        return [resolve_parameter_refs(item, common_params) for item in value]
    if isinstance(value, dict):
        if "ref" in value:
            ref_id = value.get("ref")
            override = {k: v for k, v in value.items() if k != "ref"}
            if ref_id not in common_params:
                result = copy.deepcopy(override)
                result["__missing_ref"] = ref_id
                return result
            return deep_merge_dict(copy.deepcopy(common_params[ref_id]), override)
        return {k: resolve_parameter_refs(v, common_params) for k, v in value.items()}
    return value

def iter_commands_from_file(path: pathlib.Path, common_params: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
    data = load_yaml(path)
    if not data:
        return []
    commands = data["commands"] if isinstance(data, dict) and "commands" in data else [data]
    result = []
    for cmd in commands:
        if isinstance(cmd, dict):
            cmd = copy.deepcopy(cmd)
            if "parameters" in cmd:
                cmd["parameters"] = resolve_parameter_refs(cmd["parameters"], common_params)
            cmd["__source"] = str(path.relative_to(ROOT))
            result.append(cmd)
    return result

def load_command_specs() -> List[Dict[str, Any]]:
    commands: List[Dict[str, Any]] = []
    common_params = load_common_parameters()
    for path in iter_command_files():
        commands.extend(iter_commands_from_file(path, common_params))
    return commands

def load_profiles() -> List[Dict[str, Any]]:
    result = []
    for path in iter_profile_files():
        item = load_yaml(path)
        if isinstance(item, dict):
            item = copy.deepcopy(item); item["__source"] = str(path.relative_to(ROOT)); result.append(item)
    return result

def load_models() -> List[Dict[str, Any]]:
    result = []
    for path in iter_model_files():
        item = load_yaml(path)
        if isinstance(item, dict):
            item = copy.deepcopy(item); item["__source"] = str(path.relative_to(ROOT)); result.append(item)
    return result

def get_profile_map() -> Dict[str, Dict[str, Any]]:
    return {p["profile_id"]: p for p in load_profiles() if p.get("profile_id")}

def get_base_profile_ids(model: Dict[str, Any]) -> List[str]:
    base_profiles = model.get("base_profiles")
    return list(base_profiles or []) if isinstance(base_profiles, list) else []

def load_profile_by_id(profile_id: str) -> Dict[str, Any]:
    path = ROOT / "profiles" / f"{profile_id}.yaml"
    base = load_yaml(path)
    if not isinstance(base, dict):
        raise ValueError(f"Invalid base profile: {path}")
    base = copy.deepcopy(base); base["__source"] = str(path.relative_to(ROOT))
    return base

def load_model_profile(model_id: str) -> Dict[str, Any]:
    path = ROOT / "models" / f"{model_id}.yaml"
    model = load_yaml(path)
    if not isinstance(model, dict):
        raise ValueError(f"Invalid model profile: {path}")
    model = copy.deepcopy(model); model["__source"] = str(path.relative_to(ROOT))
    base_profile_ids = get_base_profile_ids(model)
    if not base_profile_ids:
        model["command_order"] = apply_order_after(model.get("command_order", []), model.get("order_after", {}) or {})
        return model
    merged: Dict[str, Any] = {}
    for profile_id in base_profile_ids:
        merged = merge_profile(merged, load_profile_by_id(profile_id))
    return merge_profile(merged, model)

def get_localized(value: Any, language: str, fallback: str = "") -> str:
    if isinstance(value, dict):
        return value.get(language) or value.get("zh") or value.get("en") or fallback
    return value or fallback

def get_variant_bucket(value: Any) -> Dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    variants = value.get("variants", {}) or {}
    return variants if isinstance(variants, dict) else {}

def get_direct_variant_keys(value: Any) -> Set[str]:
    return {str(k) for k in get_variant_bucket(value).keys() if k not in SUPPORTED_VARIANT_GROUPS}

def get_matching_feature_variants(value: Any, model: Dict[str, Any]) -> List[str]:
    variants = get_variant_bucket(value)
    by_feature = variants.get("by_feature", {}) if isinstance(variants.get("by_feature"), dict) else {}
    features = model.get("features", {}) or {}
    return [name for name, enabled in features.items() if enabled and name in by_feature]

def describe_variant_choice(value: Any, model: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(value, dict):
        return {"value": value, "source": "raw", "reason": "value is not a variant object"}
    model_id = model.get("model_id")
    variants = get_variant_bucket(value)
    by_model = variants.get("by_model", {}) if isinstance(variants.get("by_model"), dict) else {}
    if model_id in by_model:
        return {"value": by_model[model_id], "source": f"variants.by_model.{model_id}", "reason": f"model_id matched {model_id}"}
    by_feature = variants.get("by_feature", {}) if isinstance(variants.get("by_feature"), dict) else {}
    matches = get_matching_feature_variants(value, model)
    if matches:
        feature_name = matches[0]
        return {"value": by_feature[feature_name], "source": f"variants.by_feature.{feature_name}", "reason": f"enabled feature matched {feature_name}"}
    return {"value": value.get("default"), "source": "default", "reason": "no model or feature variant matched"}

def choose_variant(value: Any, model: Dict[str, Any]) -> Any:
    return describe_variant_choice(value, model)["value"]

def get_variant_description(value: Any, model: Dict[str, Any], language: str) -> str:
    selected = choose_variant(value, model)
    return get_localized(selected.get("description"), language) if isinstance(selected, dict) else ""

def get_enabled_command_ids(model: Dict[str, Any]) -> List[str]:
    return unique_extend(model.get("command_order", []) or [], model.get("include_commands", []) or [])

def command_enabled_for_model(cmd: Dict[str, Any], model: Dict[str, Any]) -> bool:
    return cmd["id"] not in model.get("exclude_commands", []) and cmd["id"] in get_enabled_command_ids(model)

def command_visible_for_model(cmd: Dict[str, Any], model: Dict[str, Any]) -> bool:
    return command_enabled_for_model(cmd, model) and cmd.get("category") in model.get("include_categories", [])

def get_commands_for_model(model: Dict[str, Any], commands: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    filtered = [cmd for cmd in commands if command_visible_for_model(cmd, model)]
    order = model.get("command_order", []) or []
    filtered.sort(key=lambda c: order.index(c["id"]) if c["id"] in order else 9999)
    return filtered

def get_all_referenced_command_ids(models: List[Dict[str, Any]], profiles: List[Dict[str, Any]]) -> Set[str]:
    refs: Set[str] = set()
    for item in list(models) + list(profiles):
        for field in ["command_order", "include_commands", "exclude_commands"]:
            refs.update(item.get(field, []) or [])
        order_after = item.get("order_after", {}) or {}
        if isinstance(order_after, dict):
            refs.update(order_after.keys()); refs.update(order_after.values())
    return refs

def collect_display_id_duplicates(commands: List[Dict[str, Any]]) -> Dict[str, List[str]]:
    result: Dict[str, List[str]] = {}
    for cmd in commands:
        result.setdefault(cmd.get("display_id", cmd.get("id")), []).append(cmd.get("id", ""))
    return {display_id: ids for display_id, ids in result.items() if len(set(ids)) > 1}

def normalize_syntax_keys(syntax: Any) -> Set[str]:
    selected = syntax or {}
    return {str(key) for key in selected.keys()} if isinstance(selected, dict) else set()
