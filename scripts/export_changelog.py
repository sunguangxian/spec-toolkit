import argparse
from collections import defaultdict

from atspec.core import get_commands_for_model, get_localized, load_command_specs, load_model_profile, write_text, ROOT


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True, help="model id")
    parser.add_argument("--output", help="optional output file")
    args = parser.parse_args()

    model = load_model_profile(args.model)
    language = model.get("language", "zh")
    commands = get_commands_for_model(model, load_command_specs())

    changes = defaultdict(list)
    for cmd in commands:
        for item in cmd.get("changed", []) or []:
            if not isinstance(item, dict):
                continue
            version = item.get("version", "Unreleased")
            desc = get_localized(item.get("description"), language)
            date = item.get("date", "")
            display_id = cmd.get("display_id", cmd["id"])
            if desc:
                prefix = f"{display_id}: "
                suffix = f" ({date})" if date else ""
                changes[version].append(f"- {prefix}{desc}{suffix}")

    lines = [f"# {model.get('model_name')} AT Command Changelog", ""]
    if not changes:
        lines.append("No changelog entries found.")
    else:
        for version in sorted(changes.keys(), reverse=True):
            lines.append(f"## {version}")
            lines.extend(changes[version])
            lines.append("")

    content = "\n".join(lines)
    if args.output:
        out_path = ROOT / args.output
    else:
        out_path = ROOT / "output" / f"{model.get('model_name')}_AT_Command_Changelog.md"
    write_text(out_path, content)
    print(f"Generated: {out_path}")


if __name__ == "__main__":
    main()
