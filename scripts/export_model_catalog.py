import argparse
import json
from pathlib import Path

from atspec.core import (
    ROOT,
    choose_variant,
    describe_variant_choice,
    get_base_profile_ids,
    get_commands_for_model,
    get_localized,
    load_command_specs,
    load_model_profile,
    write_text,
)
from atspec.numeric_ids import command_numeric_id


def variant_meta(cmd, model):
    result = {}
    for field in ["syntax", "parameters", "response", "examples"]:
        choice = describe_variant_choice(cmd.get(field), model)
        result[field] = {
            "source": choice.get("source", ""),
            "reason": choice.get("reason", ""),
        }
    return result


def selected_command(cmd, model, language):
    return {
        "id": cmd.get("id", ""),
        "numeric_id": command_numeric_id(cmd),
        "display_id": cmd.get("display_id", cmd.get("id", "")),
        "name": get_localized(cmd.get("name"), language),
        "summary": get_localized(cmd.get("summary"), language),
        "category": cmd.get("category", ""),
        "type": cmd.get("type", ""),
        "status": cmd.get("status", ""),
        "since": cmd.get("since", {}),
        "deprecated_since": cmd.get("deprecated_since", {}),
        "replacement": cmd.get("replacement", ""),
        "source": cmd.get("__source", ""),
        "syntax": choose_variant(cmd.get("syntax"), model),
        "parameters": choose_variant(cmd.get("parameters"), model),
        "response": choose_variant(cmd.get("response"), model),
        "examples": choose_variant(cmd.get("examples"), model),
        "variant": variant_meta(cmd, model),
    }


def build_catalog(model_id):
    model = load_model_profile(model_id)
    language = model.get("language", "zh")
    commands = get_commands_for_model(model, load_command_specs())
    return {
        "schema_version": "1.2",
        "model": {
            "model_id": model.get("model_id", model_id),
            "model_name": model.get("model_name", ""),
            "document_title": model.get("document_title", ""),
            "version": model.get("version", ""),
            "language": language,
            "base_profiles": get_base_profile_ids(model),
            "features": model.get("features", {}) or {},
        },
        "command_count": len(commands),
        "commands": [selected_command(cmd, model, language) for cmd in commands],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True)
    parser.add_argument("--output", default="")
    args = parser.parse_args()

    catalog = build_catalog(args.model)
    model_name = catalog["model"]["model_name"] or args.model
    version = catalog["model"]["version"] or "unknown"
    output = Path(args.output) if args.output else ROOT / "output" / f"{model_name}_AT_Command_{version}_catalog.json"
    write_text(output, json.dumps(catalog, ensure_ascii=False, indent=2) + "\n")
    print(f"Generated: {output}")


if __name__ == "__main__":
    main()
