import argparse
import pprint
import sys

from atspec.core import (
    describe_variant_choice,
    get_commands_for_model,
    load_command_specs,
    load_model_profile,
)

VARIANT_FIELDS = ["syntax", "parameters", "response", "examples"]


def find_command(commands, command_id: str):
    for cmd in commands:
        if cmd.get("id") == command_id or cmd.get("display_id") == command_id:
            return cmd
    return None


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True, help="model id, e.g. dp5x")
    parser.add_argument("--command", required=True, help="command internal id or display id")
    parser.add_argument("--field", choices=VARIANT_FIELDS, help="optional field to inspect")
    args = parser.parse_args()

    model = load_model_profile(args.model)
    commands = load_command_specs()
    enabled_ids = {cmd["id"] for cmd in get_commands_for_model(model, commands)}
    cmd = find_command(commands, args.command)
    if not cmd:
        print(f"Command not found: {args.command}")
        sys.exit(1)

    print(f"model: {model.get('model_id')}")
    print(f"command: {cmd.get('id')} ({cmd.get('display_id', cmd.get('id'))})")
    print(f"enabled: {'yes' if cmd.get('id') in enabled_ids else 'no'}")
    print()

    fields = [args.field] if args.field else VARIANT_FIELDS
    for field in fields:
        choice = describe_variant_choice(cmd.get(field), model)
        print(f"[{field}]")
        print(f"source: {choice.get('source')}")
        print(f"reason: {choice.get('reason')}")
        print("value:")
        pprint.pprint(choice.get("value"), width=120, sort_dicts=False)
        print()


if __name__ == "__main__":
    main()
