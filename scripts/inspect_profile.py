import argparse

from atspec.core import (
    get_base_profile_ids,
    get_commands_for_model,
    get_localized,
    load_command_specs,
    load_model_profile,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True, help="model id, e.g. dp5x, km2, rsc")
    args = parser.parse_args()

    model = load_model_profile(args.model)
    commands = get_commands_for_model(model, load_command_specs())
    language = model.get("language", "zh")

    print(f"Model ID: {model.get('model_id')}")
    print(f"Model Name: {model.get('model_name')}")
    print(f"Document Title: {model.get('document_title')}")
    print(f"Version: {model.get('version')}")
    print("Base Profiles:")
    for profile_id in get_base_profile_ids(model):
        print(f"  - {profile_id}")
    print()
    print("Enabled categories:")
    for category in model.get("include_categories", []) or []:
        print(f"  - {category}")
    print()
    print("Final command order:")
    for index, cmd in enumerate(commands, 1):
        display_id = cmd.get("display_id", cmd["id"])
        name = get_localized(cmd.get("name"), language)
        print(f"{index:03d}. {cmd['id']} | {display_id} | {cmd.get('category', '')} | {name}")


if __name__ == "__main__":
    main()
