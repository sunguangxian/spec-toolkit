import argparse
from pathlib import Path

from atspec.core import (
    ROOT,
    choose_variant,
    describe_variant_choice,
    get_commands_for_model,
    get_localized,
    load_command_specs,
    load_model_profile,
    write_text,
)


def command_signature(cmd, model):
    return {
        "display_id": cmd.get("display_id", cmd.get("id", "")),
        "name": cmd.get("name", {}),
        "category": cmd.get("category", ""),
        "status": cmd.get("status", ""),
        "syntax": choose_variant(cmd.get("syntax", {}), model),
        "parameters": choose_variant(cmd.get("parameters", {}), model),
        "response": choose_variant(cmd.get("response", {}), model),
        "examples": choose_variant(cmd.get("examples", {}), model),
    }


def syntax_lines(value):
    if not isinstance(value, dict):
        return []
    lines = []
    for key in ["execute", "set", "read", "test", "write", "urc"]:
        if value.get(key):
            lines.append(f"{key}: `{value.get(key)}`")
    return lines


def command_title(cmd, language):
    display_id = cmd.get("display_id", cmd.get("id", ""))
    name = get_localized(cmd.get("name"), language)
    return f"`{display_id}` - {name}" if name else f"`{display_id}`"


def render_model_snapshot(model_id, commands):
    model = load_model_profile(model_id)
    language = model.get("language", "zh")
    visible = get_commands_for_model(model, commands)
    lines = [
        f"# Release Review: {model.get('model_name')} {model.get('version')}",
        "",
        "## Summary",
        "",
        f"- Model ID: `{model_id}`",
        f"- Model Name: `{model.get('model_name')}`",
        f"- Version: `{model.get('version')}`",
        f"- Visible Commands: `{len(visible)}`",
        "",
        "## Command List",
        "",
    ]
    for index, cmd in enumerate(visible, 1):
        lines.append(f"{index}. {command_title(cmd, language)}")
    lines.append("")
    lines.append("## Selected Syntax and Variants")
    lines.append("")
    for index, cmd in enumerate(visible, 1):
        lines.append(f"### {index}. {command_title(cmd, language)}")
        lines.append("")
        lines.append(f"- Internal ID: `{cmd.get('id')}`")
        lines.append(f"- Category: `{cmd.get('category', '')}`")
        lines.append(f"- Status: `{cmd.get('status', '')}`")
        lines.append(f"- Source: `{cmd.get('__source', '')}`")
        for field in ["syntax", "parameters", "response", "examples"]:
            choice = describe_variant_choice(cmd.get(field), model)
            lines.append(f"- {field} variant: `{choice.get('source', '')}` - {choice.get('reason', '')}")
        selected_syntax = choose_variant(cmd.get("syntax"), model)
        syntax = syntax_lines(selected_syntax)
        if syntax:
            lines.append("")
            lines.append("Selected syntax:")
            for item in syntax:
                lines.append(f"- {item}")
        lines.append("")
    return "\n".join(lines) + "\n"


def render_model_diff(left_id, right_id, commands):
    left_model = load_model_profile(left_id)
    right_model = load_model_profile(right_id)
    left_commands = get_commands_for_model(left_model, commands)
    right_commands = get_commands_for_model(right_model, commands)
    command_map = {cmd.get("id"): cmd for cmd in commands}
    left_ids = [cmd.get("id") for cmd in left_commands]
    right_ids = [cmd.get("id") for cmd in right_commands]
    left_set = set(left_ids)
    right_set = set(right_ids)
    left_lang = left_model.get("language", "zh")

    only_left = [cmd_id for cmd_id in left_ids if cmd_id not in right_set]
    only_right = [cmd_id for cmd_id in right_ids if cmd_id not in left_set]
    changed = []
    for cmd_id in [item for item in left_ids if item in right_set]:
        cmd = command_map[cmd_id]
        if command_signature(cmd, left_model) != command_signature(cmd, right_model):
            changed.append(cmd_id)

    lines = [
        f"# Release Review Diff: {left_id} vs {right_id}",
        "",
        "## Summary",
        "",
        f"- {left_id} visible commands: `{len(left_ids)}`",
        f"- {right_id} visible commands: `{len(right_ids)}`",
        f"- Only in {left_id}: `{len(only_left)}`",
        f"- Only in {right_id}: `{len(only_right)}`",
        f"- Same command but different selected content: `{len(changed)}`",
        "",
        f"## Only in {left_id}",
        "",
    ]
    if only_left:
        for cmd_id in only_left:
            lines.append(f"- {command_title(command_map[cmd_id], left_lang)} (`{cmd_id}`)")
    else:
        lines.append("- None")

    lines.extend(["", f"## Only in {right_id}", ""])
    if only_right:
        for cmd_id in only_right:
            lines.append(f"- {command_title(command_map[cmd_id], left_lang)} (`{cmd_id}`)")
    else:
        lines.append("- None")

    lines.extend(["", "## Different Selected Content", ""])
    if changed:
        for cmd_id in changed:
            cmd = command_map[cmd_id]
            lines.append(f"### {command_title(cmd, left_lang)} (`{cmd_id}`)")
            for field in ["syntax", "parameters", "response", "examples"]:
                left_choice = describe_variant_choice(cmd.get(field), left_model)
                right_choice = describe_variant_choice(cmd.get(field), right_model)
                if left_choice.get("value") != right_choice.get("value"):
                    lines.append(
                        f"- {field}: {left_id} uses `{left_choice.get('source')}`, "
                        f"{right_id} uses `{right_choice.get('source')}`"
                    )
            lines.append("")
    else:
        lines.append("- None")
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description="Export a human-readable AT spec release review report.")
    parser.add_argument("--model", required=True, help="model id to review")
    parser.add_argument("--compare-to", default="", help="optional model id to compare with")
    parser.add_argument("--output", default="", help="output markdown path")
    args = parser.parse_args()

    commands = load_command_specs()
    if args.compare_to:
        content = render_model_diff(args.model, args.compare_to, commands)
        default_name = f"release_review_{args.model}_vs_{args.compare_to}.md"
    else:
        content = render_model_snapshot(args.model, commands)
        default_name = f"release_review_{args.model}.md"

    output = Path(args.output) if args.output else ROOT / "output" / default_name
    write_text(output, content)
    print(f"Generated: {output}")


if __name__ == "__main__":
    main()
