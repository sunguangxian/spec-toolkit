from typing import Any, Dict

MIN_COMMAND_NUMERIC_ID = 1
MAX_COMMAND_NUMERIC_ID = 0x7FFFFFFF


def command_numeric_id(command: Dict[str, Any]) -> int:
    """Return the explicitly maintained stable numeric command id.

    numeric_id is intentionally mandatory. Do not derive fallback values from
    command order or command id text, because generated bindings may be used by
    firmware, PC tools, logs, and test systems across versions.
    """
    if 'numeric_id' not in command or command.get('numeric_id') in [None, '']:
        raise ValueError(f"command {command.get('id', '<unknown>')} is missing required numeric_id")
    return int(command['numeric_id'])
