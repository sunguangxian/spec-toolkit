import re
import sys
from typing import Any, Dict, Iterable, List, Optional

from atspec.core import choose_variant, get_commands_for_model, iter_model_files, load_command_specs, load_model_profile

HEX_RE = re.compile(r"^[0-9a-fA-F]+$")
ANGLE_HEX_RE = re.compile(r"<([0-9a-fA-F\s]+)>")
PLACEHOLDER_RE = re.compile(r"^<[^>]+>$")


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


def split_at_params(command: str) -> List[str]:
    if "=" not in command:
        return []
    rhs = command.split("=", 1)[1]
    params: List[str] = []
    current: List[str] = []
    in_quote = False
    angle_depth = 0
    escape = False
    for ch in rhs:
        if escape:
            current.append(ch)
            escape = False
            continue
        if ch == "\\":
            current.append(ch)
            escape = True
            continue
        if ch == '"':
            in_quote = not in_quote
            current.append(ch)
            continue
        if not in_quote:
            if ch == "<":
                angle_depth += 1
            elif ch == ">" and angle_depth > 0:
                angle_depth -= 1
            elif ch == "," and angle_depth == 0:
                params.append("".join(current).strip())
                current = []
                continue
        current.append(ch)
    params.append("".join(current).strip())
    return params


def strip_outer_quotes(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == '"' and value[-1] == '"':
        return value[1:-1]
    return value


def is_placeholder(value: str) -> bool:
    return PLACEHOLDER_RE.match(strip_outer_quotes(value)) is not None


def parse_int(value: str) -> Optional[int]:
    try:
        return int(strip_outer_quotes(value), 0)
    except ValueError:
        return None


def hex_payload_len(text: str) -> Optional[int]:
    if is_placeholder(text):
        return None
    compact = strip_outer_quotes(text).replace(" ", "")
    if not compact:
        return 0
    if not HEX_RE.match(compact) or len(compact) % 2 != 0:
        return None
    return len(compact) // 2


def angle_binary_len(command: str) -> Optional[int]:
    match = ANGLE_HEX_RE.search(command)
    if not match:
        return None
    return hex_payload_len(match.group(1))


def is_hex_parameter(param: Dict[str, Any]) -> bool:
    ptype = str(param.get("type", "")).lower()
    pname = str(param.get("name", "")).lower()
    encoding = str(param.get("encoding", "")).lower()
    return ptype == "hex_string" or encoding == "hex" or "hex" in pname


def is_length_parameter(param: Dict[str, Any]) -> bool:
    pname = str(param.get("name", "")).lower()
    ptype = str(param.get("type", "")).lower()
    return pname in ["len", "length"] or ptype in ["length"]


def validate_hex_parameters(model_id: str, cmd: Dict[str, Any], params: List[str], source: str, reporter: Reporter) -> None:
    selected_params = choose_variant(cmd.get("parameters"), {"model_id": model_id}) or []
    if not isinstance(selected_params, list):
        return
    for index, param in enumerate(selected_params):
        if not isinstance(param, dict) or not is_hex_parameter(param):
            continue
        if index >= len(params):
            continue
        if is_placeholder(params[index]):
            continue
        actual_len = hex_payload_len(params[index])
        if actual_len is None:
            reporter.error(f"{source}: parameter {param.get('name')} is not valid even-length HEX text")
            continue
        if index > 0 and isinstance(selected_params[index - 1], dict) and is_length_parameter(selected_params[index - 1]):
            expected_len = parse_int(params[index - 1])
            if expected_len is not None and expected_len != actual_len:
                reporter.error(f"{source}: length is {expected_len}, but parameter {param.get('name')} has {actual_len} byte(s)")


def validate_len_against_payload(model_id: str, cmd: Dict[str, Any], example: Dict[str, Any], reporter: Reporter) -> None:
    command = str(example.get("command", ""))
    params = split_at_params(command)
    if not params:
        return

    source = f"{model_id}:{cmd.get('id')} example command '{command}'"

    if "BIN" in params:
        bin_index = params.index("BIN")
        if len(params) <= bin_index + 2:
            reporter.warn(f"{source}: BIN example should contain length and binary payload")
            return
        expected_len = parse_int(params[bin_index + 1])
        actual_len = angle_binary_len(command)
        if expected_len is not None and actual_len is not None and expected_len != actual_len:
            reporter.error(f"{source}: length is {expected_len}, but binary example has {actual_len} byte(s)")
        return

    validate_hex_parameters(model_id, cmd, params, source, reporter)


def validate_binary_parameters(model_id: str, cmd: Dict[str, Any], reporter: Reporter) -> None:
    params = choose_variant(cmd.get("parameters"), {"model_id": model_id}) or []
    if not isinstance(params, list):
        return
    for param in params:
        if not isinstance(param, dict):
            continue
        ptype = str(param.get("type", "")).lower()
        pname = str(param.get("name", "")).lower()
        if ptype in ["binary", "bytes"] or pname in ["raw_bin_data", "len", "length"]:
            for field in ["unit", "encoding", "allow_zero"]:
                if field not in param:
                    reporter.error(f"{model_id}:{cmd.get('id')} parameter {param.get('name')}: missing {field}")


def main() -> None:
    reporter = Reporter()
    commands = load_command_specs()

    for model_file in iter_model_files():
        model = load_model_profile(model_file.stem)
        model_id = model.get("model_id")
        for cmd in get_commands_for_model(model, commands):
            validate_binary_parameters(model_id, cmd, reporter)
            examples = choose_variant(cmd.get("examples"), model) or []
            for example in iter_examples(examples):
                validate_len_against_payload(model_id, cmd, example, reporter)

    if reporter.errors:
        print(f"Binary example validation failed: {reporter.errors} error(s), {reporter.warnings} warning(s).")
        sys.exit(1)

    print(f"Binary example validation completed. Warning(s): {reporter.warnings}")


if __name__ == "__main__":
    main()
