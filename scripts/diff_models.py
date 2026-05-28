import argparse

from atspec.core import (
    choose_variant,
    get_commands_for_model,
    load_command_specs,
    load_model_profile,
)


def variant_signature(cmd, model):
    return {
        "syntax": choose_variant(cmd.get("syntax", {}), model),
        "parameters": choose_variant(cmd.get("parameters", {}), model),
        "response": choose_variant(cmd.get("response", {}), model),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--left", required=True, help="left model id")
    parser.add_argument("--right", required=True, help="right model id")
    args = parser.parse_args()

    commands = load_command_specs()
    command_map = {cmd["id"]: cmd for cmd in commands}

    left_model = load_model_profile(args.left)
    right_model = load_model_profile(args.right)

    left_ids = [cmd["id"] for cmd in get_commands_for_model(left_model, commands)]
    right_ids = [cmd["id"] for cmd in get_commands_for_model(right_model, commands)]

    left_set = set(left_ids)
    right_set = set(right_ids)

    print(f"# Model Diff: {args.left} vs {args.right}\n")

    print(f"## Only in {args.left}")
    only_left = [cmd_id for cmd_id in left_ids if cmd_id not in right_set]
    if only_left:
        for cmd_id in only_left:
            cmd = command_map[cmd_id]
            print(f"- {cmd_id} ({cmd.get('display_id', cmd_id)})")
    else:
        print("- None")

    print(f"\n## Only in {args.right}")
    only_right = [cmd_id for cmd_id in right_ids if cmd_id not in left_set]
    if only_right:
        for cmd_id in only_right:
            cmd = command_map[cmd_id]
            print(f"- {cmd_id} ({cmd.get('display_id', cmd_id)})")
    else:
        print("- None")

    print("\n## Different format")
    different = []
    for cmd_id in [item for item in left_ids if item in right_set]:
        cmd = command_map[cmd_id]
        if variant_signature(cmd, left_model) != variant_signature(cmd, right_model):
            different.append(cmd_id)

    if different:
        for cmd_id in different:
            cmd = command_map[cmd_id]
            print(f"- {cmd_id} ({cmd.get('display_id', cmd_id)})")
    else:
        print("- None")


if __name__ == "__main__":
    main()
