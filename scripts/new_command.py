import argparse
from pathlib import Path

import yaml

from atspec.core import ROOT, load_yaml, write_text
from atspec.numeric_ids import MAX_COMMAND_NUMERIC_ID, MIN_COMMAND_NUMERIC_ID


def command_template(command_id: str, numeric_id: int, display_id: str, name_zh: str, name_en: str, category: str) -> dict:
    return {
        "id": command_id,
        "numeric_id": numeric_id,
        "display_id": display_id,
        "name": {"zh": name_zh, "en": name_en or name_zh},
        "category": category,
        "status": "draft",
        "summary": {"zh": "TODO: 补充指令用途说明。", "en": "TODO: Add command summary."},
        "syntax": {"default": {"set": f"{display_id}=<Param>"}},
        "parameters": {
            "default": [
                {
                    "name": "Param",
                    "type": "string",
                    "required": True,
                    "description": {"zh": "TODO: 补充参数说明。", "en": "TODO: Add parameter description."},
                }
            ]
        },
        "response": {
            "default": {
                "timeout_ms": 1000,
                "success": [{"pattern": "OK", "final": True}],
                "error": [{"pattern": "+CME ERROR:<ErrorCode>", "final": True}],
            }
        },
        "examples": {
            "default": [
                {
                    "title": {"zh": "TODO: 示例", "en": "TODO: Example"},
                    "command": f"{display_id}=1",
                    "response": ["OK"],
                }
            ]
        },
    }


def load_command_file(path: Path) -> dict:
    if not path.exists():
        return {"commands": []}
    data = load_yaml(path) or {}
    if "commands" not in data:
        data = {"commands": [data]}
    return data


def append_command(path: Path, command: dict) -> None:
    data = load_command_file(path)
    commands = data.setdefault("commands", [])
    ids = {item.get("id") for item in commands if isinstance(item, dict)}
    numeric_ids = {item.get("numeric_id") for item in commands if isinstance(item, dict)}
    if command["id"] in ids:
        raise SystemExit(f"Command id already exists in {path}: {command['id']}")
    if command["numeric_id"] in numeric_ids:
        raise SystemExit(f"numeric_id already exists in {path}: {command['numeric_id']}")
    commands.append(command)
    write_text(path, yaml.safe_dump(data, allow_unicode=True, sort_keys=False, width=120))


def append_to_profile(profile_id: str, command_id: str) -> None:
    path = ROOT / "profiles" / f"{profile_id}.yaml"
    if not path.exists():
        raise SystemExit(f"Profile does not exist: {path}")
    data = load_yaml(path) or {}
    order = data.setdefault("command_order", [])
    if command_id not in order:
        order.append(command_id)
    write_text(path, yaml.safe_dump(data, allow_unicode=True, sort_keys=False, width=120))


def parse_numeric_id(value: str) -> int:
    try:
        numeric_id = int(value, 0)
    except ValueError as exc:
        raise SystemExit(f"numeric_id must be an integer: {value}") from exc
    if numeric_id < MIN_COMMAND_NUMERIC_ID or numeric_id > MAX_COMMAND_NUMERIC_ID:
        raise SystemExit(f"numeric_id out of range: {numeric_id}")
    return numeric_id


def main() -> None:
    parser = argparse.ArgumentParser(description="Create an AT command YAML skeleton and optionally attach it to a profile.")
    parser.add_argument("--id", required=True, help="internal command id, for example BT_AT_CBTADDR")
    parser.add_argument("--numeric-id", required=True, help="explicit stable numeric command id, for example 2010")
    parser.add_argument("--display", required=True, help="customer-visible AT command, for example AT+CBTADDR")
    parser.add_argument("--name-zh", required=True, help="Chinese command name")
    parser.add_argument("--name-en", default="", help="English command name")
    parser.add_argument("--category", required=True, help="command category, for example Bluetooth")
    parser.add_argument("--file", required=True, help="target YAML file, for example commands/extensions/bluetooth.yaml")
    parser.add_argument("--profile", default="", help="optional profile id to append command_order, for example bluetooth_common")
    args = parser.parse_args()

    target = ROOT / args.file
    numeric_id = parse_numeric_id(args.numeric_id)
    cmd = command_template(args.id, numeric_id, args.display, args.name_zh, args.name_en, args.category)
    append_command(target, cmd)

    if args.profile:
        append_to_profile(args.profile, args.id)

    print(f"Created command skeleton: {args.id}")
    print(f"Assigned numeric_id: {numeric_id}")
    print(f"Updated command file: {target.relative_to(ROOT)}")
    if args.profile:
        print(f"Updated profile command_order: profiles/{args.profile}.yaml")
    print("Next steps:")
    print("  1. Replace TODO fields in the generated command.")
    print("  2. Run: python scripts/validate_all.py")
    print(f"  3. Run: python scripts/build_doc.py --model <model_id> --format html")


if __name__ == "__main__":
    main()
