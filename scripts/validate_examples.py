import re
import sys
from typing import Any, Dict, Iterable, List

from atspec.core import (
    choose_variant,
    get_commands_for_model,
    load_command_specs,
    load_model_profile,
    iter_model_files,
)

PLACEHOLDER_RE = re.compile(r"<[^>]+>")


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


def iter_examples(value: Any) -> Iterable[Dict[str, Any]]:
    if isinstance(value, list):
        for item in value:
            if isinstance(item, dict):
                yield item
    elif isinstance(value, dict):
        for item in value.values():
            yield from iter_examples(item)


def command_prefix(display_id: str) -> str:
    return display_id.split("?")[0].split("=")[0]


def split_params(text: str) -> List[str]:
    params: List[str] = []
    current: List[str] = []
    in_quote = False
    angle_depth = 0
    for ch in text:
        if ch == '"':
            in_quote = not in_quote
        elif not in_quote:
            if ch == "<":
                angle_depth += 1
            elif ch == ">" and angle_depth > 0:
                angle_depth -= 1
            elif ch == "," and angle_depth == 0:
                item = "".join(current).strip()
                if item:
                    params.append(item)
                current = []
                continue
        current.append(ch)
    item = "".join(current).strip()
    if item:
        params.append(item)
    return params


def count_syntax_params(syntax: Dict[str, Any]) -> int:
    max_count = 0
    for text in syntax.values():
        if isinstance(text, str):
            placeholders = len(PLACEHOLDER_RE.findall(text))
            literals = len([p for p in split_params(text.split("=", 1)[1] if "=" in text else "") if not PLACEHOLDER_RE.search(p)])
            max_count = max(max_count, placeholders + literals)
    return max_count


def count_example_params(example_command: str) -> int:
    if "=" not in example_command:
        return 0
    rhs = example_command.split("=", 1)[1]
    if rhs == "":
        return 0
    return len(split_params(rhs))


def validate_command_examples(model: Dict[str, Any], cmd: Dict[str, Any], reporter: Reporter) -> None:
    model_id = model.get("model_id")
    display_id = cmd.get("display_id", cmd.get("id", ""))
    prefix = command_prefix(display_id)
    syntax = choose_variant(cmd.get("syntax", {}), model) or {}
    examples = choose_variant(cmd.get("examples", {}), model) or []
    expected_params = count_syntax_params(syntax) if isinstance(syntax, dict) else 0

    for index, example in enumerate(iter_examples(examples), 1):
        command = str(example.get("command", ""))
        source = f"{model_id}:{cmd.get('id')} example[{index}]"
        if not command:
            reporter.warn(f"{source}: missing example command")
            continue

        is_urc = display_id.startswith("+")
        if not is_urc and not command.startswith(prefix):
            reporter.warn(f"{source}: example command does not start with display command '{prefix}': {command}")
        if is_urc and not command.startswith(prefix):
            reporter.warn(f"{source}: URC example does not start with '{prefix}': {command}")

        actual_params = count_example_params(command)
        if expected_params and actual_params > expected_params:
            reporter.warn(f"{source}: example has more parameters ({actual_params}) than syntax placeholders/literals ({expected_params})")

        response = example.get("response")
        if response is None:
            reporter.warn(f"{source}: missing response field")
        elif not isinstance(response, list):
            reporter.warn(f"{source}: response should be a list")


def main() -> None:
    reporter = Reporter()
    commands = load_command_specs()
    model_ids = [p.stem for p in iter_model_files()]

    for model_id in model_ids:
        model = load_model_profile(model_id)
        for cmd in get_commands_for_model(model, commands):
            validate_command_examples(model, cmd, reporter)

    if reporter.errors:
        print(f"Example validation failed: {reporter.errors} error(s), {reporter.warnings} warning(s).")
        sys.exit(1)

    print(f"Example validation completed. Warning(s): {reporter.warnings}")


if __name__ == "__main__":
    main()
