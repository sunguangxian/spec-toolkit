import sys
from typing import Any, Dict, Iterable, List, Set

from atspec.core import (
    choose_variant,
    get_matching_feature_variants,
    get_variant_bucket,
    load_command_specs,
    load_model_profile,
    iter_model_files,
    normalize_syntax_keys,
)

VARIANT_FIELDS = ["syntax", "parameters", "response", "examples"]


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


def variant_keys(value: Any) -> Set[str]:
    variants = get_variant_bucket(value)
    result = {k for k in variants.keys() if k not in ["by_model", "by_feature"]}
    by_model = variants.get("by_model", {}) if isinstance(variants.get("by_model"), dict) else {}
    result.update(by_model.keys())
    return result


def feature_variant_keys(value: Any) -> Set[str]:
    variants = get_variant_bucket(value)
    by_feature = variants.get("by_feature", {}) if isinstance(variants.get("by_feature"), dict) else {}
    return set(by_feature.keys())


def validate_model_feature_conflicts(commands: List[Dict[str, Any]], model: Dict[str, Any], reporter: Reporter) -> None:
    model_id = model.get("model_id")
    for cmd in commands:
        for field in VARIANT_FIELDS:
            matches = get_matching_feature_variants(cmd.get(field), model)
            if len(matches) > 1:
                reporter.error(
                    f"{cmd.get('__source', '<unknown>')}:{cmd.get('id')} {field}: "
                    f"model {model_id} matches multiple feature variants: {', '.join(matches)}"
                )


def validate_variant_field_alignment(commands: List[Dict[str, Any]], reporter: Reporter) -> None:
    for cmd in commands:
        source = cmd.get("__source", "<unknown>")
        cmd_id = cmd.get("id", "<unknown>")
        model_variant_sets = {field: variant_keys(cmd.get(field)) for field in VARIANT_FIELDS}
        feature_variant_sets = {field: feature_variant_keys(cmd.get(field)) for field in VARIANT_FIELDS}

        for field, keys in model_variant_sets.items():
            for key in keys:
                missing = [other for other in ["parameters", "examples"] if field == "syntax" and key not in model_variant_sets.get(other, set())]
                if missing:
                    reporter.warn(f"{source}:{cmd_id}: model variant '{key}' customizes syntax but not {', '.join(missing)}")

        for field, keys in feature_variant_sets.items():
            for key in keys:
                missing = [other for other in ["parameters", "examples"] if field == "syntax" and key not in feature_variant_sets.get(other, set())]
                if missing:
                    reporter.warn(f"{source}:{cmd_id}: feature variant '{key}' customizes syntax but not {', '.join(missing)}")


def validate_selected_syntax_shape(commands: List[Dict[str, Any]], models: List[Dict[str, Any]], reporter: Reporter) -> None:
    for model in models:
        model_id = model.get("model_id")
        for cmd in commands:
            selected = choose_variant(cmd.get("syntax"), model)
            keys = normalize_syntax_keys(selected)
            if not keys:
                continue
            if "write" in keys and ("set" in keys or "execute" in keys or "read" in keys):
                reporter.warn(f"{cmd.get('__source', '<unknown>')}:{cmd.get('id')}: model {model_id} mixes write syntax with standard AT forms")


def main() -> None:
    reporter = Reporter()
    commands = load_command_specs()
    models = [load_model_profile(p.stem) for p in iter_model_files()]

    validate_variant_field_alignment(commands, reporter)
    validate_selected_syntax_shape(commands, models, reporter)
    for model in models:
        validate_model_feature_conflicts(commands, model, reporter)

    if reporter.errors:
        print(f"Variant validation failed: {reporter.errors} error(s), {reporter.warnings} warning(s).")
        sys.exit(1)

    print(f"Variant validation completed. Warning(s): {reporter.warnings}")


if __name__ == "__main__":
    main()
