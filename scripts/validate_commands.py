import sys
from typing import Any, Dict, List, Set

from jsonschema import Draft202012Validator

from atspec.core import (
    collect_display_id_duplicates,
    get_all_referenced_command_ids,
    get_base_profile_ids,
    load_command_specs,
    load_models,
    load_profiles,
    load_yaml,
    toolkit_path,
)
from atspec.numeric_ids import MAX_COMMAND_NUMERIC_ID, MIN_COMMAND_NUMERIC_ID, command_numeric_id

REQUIRED_COMMAND_FIELDS = ["id", "numeric_id", "display_id", "name", "category", "syntax", "response"]
REQUIRED_MODEL_FIELDS = ["model_id", "model_name", "document_title", "version", "language"]
VARIANT_GROUP_KEYS = {"by_model", "by_feature"}
REFERENCE_OPTIONAL_CATEGORIES = {
    "Appendix",
    "Channel Data Format",
}


class Reporter:
    def __init__(self) -> None:
        self.errors = 0
        self.warnings = 0

    def error(self, message: str) -> None:
        self.errors += 1
        print(f"[ERROR] {message}")

    def warn(self, message: str) -> None:
        self.warnings += 1
        print(f"[WARN] {message}")


def is_localized(value: Any) -> bool:
    return isinstance(value, dict) and ("zh" in value or "en" in value)


def validate_with_schema(data: Dict[str, Any], schema_name: str, source: str, reporter: Reporter) -> None:
    schema = load_yaml(toolkit_path("schemas", schema_name))
    validator = Draft202012Validator(schema)
    for error in sorted(validator.iter_errors(data), key=lambda e: list(e.path)):
        path = ".".join(str(p) for p in error.path) or "<root>"
        reporter.error(f"{source}: schema error at {path}: {error.message}")


def validate_variant_groups(value: Any, path: str, reporter: Reporter) -> None:
    if not isinstance(value, dict):
        return
    variants = value.get("variants")
    if variants is None:
        return
    if not isinstance(variants, dict):
        reporter.error(f"{path}.variants: must be a mapping")
        return
    for key in variants.keys():
        if key not in VARIANT_GROUP_KEYS:
            reporter.error(f"{path}.variants.{key}: direct variants are not supported; use variants.by_model or variants.by_feature")


def validate_command_variants(cmd: Dict[str, Any], model_ids: Set[str], source: str, reporter: Reporter) -> None:
    cmd_id = cmd.get("id", "<unknown>")
    for field in ["syntax", "parameters", "response", "examples"]:
        value = cmd.get(field)
        validate_variant_groups(value, f"{source}:{cmd_id}.{field}", reporter)
        if not isinstance(value, dict):
            continue
        variants = value.get("variants", {}) or {}
        by_model = variants.get("by_model", {}) if isinstance(variants.get("by_model"), dict) else {}
        for mid in by_model.keys():
            if model_ids and mid not in model_ids:
                reporter.error(f"{source}: {cmd_id} {field} variant references unknown model: {mid}")


def validate_commands(commands: List[Dict[str, Any]], model_ids: Set[str], reporter: Reporter) -> Set[str]:
    ids: Set[str] = set()
    numeric_id_map: Dict[int, str] = {}
    for cmd in commands:
        source = cmd.get("__source", "<unknown>")
        schema_cmd = {k: v for k, v in cmd.items() if not k.startswith("__")}
        validate_with_schema(schema_cmd, "command.schema.json", source, reporter)

        for field in REQUIRED_COMMAND_FIELDS:
            if field not in cmd:
                reporter.error(f"{source}: missing command field: {field}")

        cmd_id = cmd.get("id")
        if not cmd_id:
            continue
        if cmd_id in ids:
            reporter.error(f"duplicated command id: {cmd_id}")
        ids.add(cmd_id)

        try:
            numeric_id = command_numeric_id(cmd)
            if numeric_id < MIN_COMMAND_NUMERIC_ID or numeric_id > MAX_COMMAND_NUMERIC_ID:
                reporter.error(f"{source}: {cmd_id} numeric_id out of range: {numeric_id}")
            elif numeric_id in numeric_id_map:
                reporter.error(f"duplicated numeric_id {numeric_id}: {numeric_id_map[numeric_id]} and {cmd_id}")
            else:
                numeric_id_map[numeric_id] = cmd_id
        except (TypeError, ValueError) as exc:
            reporter.error(f"{source}: {cmd_id} invalid numeric_id: {exc}")

        if "availability" in cmd:
            reporter.error(f"{source}: {cmd_id} uses deprecated field 'availability'; move support control to profiles/models")
        if not is_localized(cmd.get("name", {})):
            reporter.error(f"{source}: {cmd_id} name must contain zh or en")
        summary = cmd.get("summary")
        if summary is not None and not is_localized(summary):
            reporter.error(f"{source}: {cmd_id} summary must contain zh or en")
        validate_command_variants(cmd, model_ids, source, reporter)
    return ids


def validate_profile_like_item(item: Dict[str, Any], command_ids: Set[str], categories: Set[str], reporter: Reporter) -> None:
    source = item.get("__source", "<unknown>")
    for field in ["command_order", "exclude_commands", "include_commands"]:
        seen = set()
        for cmd_id in item.get(field, []) or []:
            if cmd_id in seen:
                reporter.error(f"{source}: {field} contains duplicate command id: {cmd_id}")
            seen.add(cmd_id)
            if command_ids and cmd_id not in command_ids:
                reporter.error(f"{source}: {field} references unknown command id: {cmd_id}")
    order_after = item.get("order_after", {}) or {}
    if not isinstance(order_after, dict):
        reporter.error(f"{source}: order_after must be a mapping")
    else:
        for cmd_id, anchor_id in order_after.items():
            if command_ids and cmd_id not in command_ids:
                reporter.error(f"{source}: order_after command references unknown command id: {cmd_id}")
            if command_ids and anchor_id not in command_ids:
                reporter.error(f"{source}: order_after anchor references unknown command id: {anchor_id}")
    for category in item.get("include_categories", []) or []:
        if categories and category not in categories:
            reporter.warn(f"{source}: include_categories references unused category: {category}")


def validate_profiles(profiles: List[Dict[str, Any]], command_ids: Set[str], categories: Set[str], reporter: Reporter) -> Set[str]:
    profile_ids: Set[str] = set()
    for profile in profiles:
        source = profile.get("__source", "<unknown>")
        profile_id = profile.get("profile_id")
        if not profile_id:
            reporter.error(f"{source}: missing profile_id")
            continue
        if profile_id in profile_ids:
            reporter.error(f"duplicated profile id: {profile_id}")
        profile_ids.add(profile_id)
        validate_profile_like_item(profile, command_ids, categories, reporter)
    return profile_ids


def validate_models(models: List[Dict[str, Any]], profile_ids: Set[str], command_ids: Set[str], categories: Set[str], reporter: Reporter) -> Set[str]:
    model_ids: Set[str] = set()
    for model in models:
        source = model.get("__source", "<unknown>")
        schema_model = {k: v for k, v in model.items() if not k.startswith("__")}
        validate_with_schema(schema_model, "profile.schema.json", source, reporter)
        for field in REQUIRED_MODEL_FIELDS:
            if field not in model:
                reporter.error(f"{source}: missing model field: {field}")
        model_id = model.get("model_id")
        if model_id:
            if model_id in model_ids:
                reporter.error(f"duplicated model id: {model_id}")
            model_ids.add(model_id)
        for base_profile in get_base_profile_ids(model):
            if base_profile not in profile_ids:
                reporter.error(f"{source}: base profile references unknown profile: {base_profile}")
        validate_profile_like_item(model, command_ids, categories, reporter)
    return model_ids


def command_reference_is_optional(cmd: Dict[str, Any]) -> bool:
    """Return true for documentation-only entries rendered through appendices.

    These entries are intentionally not selected by profiles/models as normal AT commands,
    so the generic unused-command warning would be noisy and misleading.
    """
    return str(cmd.get("category", "")) in REFERENCE_OPTIONAL_CATEGORIES


def warn_unused_commands(commands: List[Dict[str, Any]], models: List[Dict[str, Any]], profiles: List[Dict[str, Any]], reporter: Reporter) -> None:
    referenced = get_all_referenced_command_ids(models, profiles)
    for cmd in commands:
        cmd_id = cmd.get("id")
        if not cmd_id:
            continue
        if command_reference_is_optional(cmd):
            continue
        if cmd_id not in referenced and cmd.get("status") != "removed":
            reporter.warn(f"{cmd.get('__source', '<unknown>')}: command {cmd_id} is not referenced by any profile/model")


def validate_display_id_duplicates(commands: List[Dict[str, Any]], reporter: Reporter) -> None:
    """Keep this intentionally quiet at global scope.

    Some products intentionally use different internal ids for the same customer-facing
    display_id when the command semantics differ by product. The actionable check is
    model-scoped duplicate display_id validation in validate_release.py.
    """
    collect_display_id_duplicates(commands)


def main() -> None:
    reporter = Reporter()
    models = load_models()
    model_ids = {m.get("model_id") for m in models if m.get("model_id")}
    commands = load_command_specs()
    command_ids = validate_commands(commands, model_ids, reporter)
    categories = {str(cmd.get("category", "")) for cmd in commands if cmd.get("category")}
    profiles = load_profiles()
    profile_ids = validate_profiles(profiles, command_ids, categories, reporter)
    validate_models(models, profile_ids, command_ids, categories, reporter)
    warn_unused_commands(commands, models, profiles, reporter)
    validate_display_id_duplicates(commands, reporter)
    if reporter.errors:
        print(f"Validation failed: {reporter.errors} error(s), {reporter.warnings} warning(s).")
        sys.exit(1)
    print(f"All command specs are valid. Warning(s): {reporter.warnings}")


if __name__ == "__main__":
    main()
