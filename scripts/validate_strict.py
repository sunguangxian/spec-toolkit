import sys
from typing import Any, Dict

from atspec.core import iter_command_files, load_command_specs, load_models, load_profiles, load_yaml

CMD_KEYS = set(
    'id numeric_id display_id name summary category type status since deprecated_since replacement syntax parameters response examples notes changed source'.split()
)
COMMAND_FILE_KEYS = set('source modules commands'.split()) | CMD_KEYS
MODEL_KEYS = set(
    'model_id model_name document_title version language communication revision_history base_profiles include_categories include_commands exclude_commands command_order order_after features options'.split()
)
PROFILE_KEYS = set(
    'profile_id profile_name include_categories include_commands exclude_commands command_order order_after features options'.split()
)

errors = 0
warnings = 0


def fail(msg):
    global errors
    errors += 1
    print('[ERROR]', msg)


def warn(msg):
    global warnings
    warnings += 1
    print('[WARN]', msg)


def check_keys(obj: Dict[str, Any], allowed: set[str], where: str) -> None:
    for key in obj:
        if not str(key).startswith('__') and key not in allowed:
            fail(f'{where}: unknown field {key}')


def check_command_file(path) -> None:
    data = load_yaml(path)
    if not isinstance(data, dict):
        fail(f'{path}: file must be YAML mapping')
        return
    check_keys(data, COMMAND_FILE_KEYS, str(path))
    if 'commands' in data and not isinstance(data.get('commands'), list):
        fail(f'{path}: top-level commands must be a list')
    if 'commands' not in data and 'id' not in data and 'modules' not in data:
        fail(f'{path}: command file must contain either id, commands, or modules')


def check_revision_history(model: Dict[str, Any]) -> None:
    where = model.get('__source', '<model>')
    items = model.get('revision_history')
    if items in [None, '']:
        return
    if not isinstance(items, list):
        fail(f'{where}: revision_history must be a list')
        return
    for index, item in enumerate(items, 1):
        if not isinstance(item, dict):
            fail(f'{where}: revision_history[{index}] must be a mapping')
            continue
        if not item.get('version'):
            fail(f'{where}: revision_history[{index}] missing version')
        if not (item.get('description') or item.get('changes')):
            fail(f'{where}: revision_history[{index}] missing description or changes')


def main():
    for path in iter_command_files():
        check_command_file(path)

    for cmd in load_command_specs():
        where = f"{cmd.get('__source')}:{cmd.get('id')}"
        check_keys(cmd, CMD_KEYS, where)
        if not cmd.get('numeric_id'):
            fail(f'{where}: missing numeric_id')
        if not cmd.get('status'):
            warn(f'{where}: missing status')
        for item in cmd.get('changed', []) or []:
            if not isinstance(item, dict) or not item.get('version') or not item.get('description'):
                fail(f'{where}: invalid changed item')

    for model in load_models():
        check_keys(model, MODEL_KEYS, model.get('__source', '<model>'))
        check_revision_history(model)

    for profile in load_profiles():
        check_keys(profile, PROFILE_KEYS, profile.get('__source', '<profile>'))

    if errors:
        print(f'Strict validation failed: {errors} error(s), {warnings} warning(s).')
        sys.exit(1)
    print(f'Strict validation completed. Warning(s): {warnings}')


if __name__ == '__main__':
    main()
