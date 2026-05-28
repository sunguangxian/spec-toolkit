import argparse
import sys

from atspec.core import (
    choose_variant,
    command_enabled_for_model,
    command_visible_for_model,
    describe_variant_choice,
    get_commands_for_model,
    get_enabled_command_ids,
    get_localized,
    iter_model_files,
    load_command_specs,
    load_model_profile,
    load_models,
    load_profiles,
)

CMD_KEYS = set('id numeric_id display_id name summary category type status since deprecated_since replacement syntax parameters response examples notes changed source'.split())
MODEL_KEYS = set('model_id model_name document_title version language communication revision_history base_profiles include_categories include_commands exclude_commands command_order order_after features options'.split())
PROFILE_KEYS = set('profile_id profile_name include_categories include_commands exclude_commands command_order order_after features options'.split())
TODO_TOKENS = ['TODO', 'TBD', '待补充']
BLOCKING_STATUS = {'draft', 'removed'}
VARIANT_ALIGNED_FIELDS = ['parameters', 'examples']


class Reporter:
    def __init__(self):
        self.errors = 0
        self.warnings = 0

    def error(self, message):
        self.errors += 1
        print(f'[ERROR] {message}')

    def warn(self, message):
        self.warnings += 1
        print(f'[WARN] {message}')


def iter_strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from iter_strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from iter_strings(item)


def has_todo(value):
    return any(token.upper() in text.upper() for text in iter_strings(value) for token in TODO_TOKENS)


def is_custom_variant_source(source):
    return bool(source) and source not in ['default', 'raw']


def check_keys(obj, allowed, where, reporter):
    for key in obj:
        if not str(key).startswith('__') and key not in allowed:
            reporter.error(f'{where}: unknown field {key}')


def validate_unknown_fields(commands, reporter):
    for cmd in commands:
        check_keys(cmd, CMD_KEYS, f"{cmd.get('__source', '<command>')}:{cmd.get('id', '<unknown>')}", reporter)
    for model in load_models():
        check_keys(model, MODEL_KEYS, model.get('__source', '<model>'), reporter)
    for profile in load_profiles():
        check_keys(profile, PROFILE_KEYS, profile.get('__source', '<profile>'), reporter)


def validate_visibility(model, commands, reporter):
    command_by_id = {cmd.get('id'): cmd for cmd in commands if cmd.get('id')}
    include_categories = set(model.get('include_categories', []) or [])
    excluded = set(model.get('exclude_commands', []) or [])
    model_id = model.get('model_id')
    for command_id in get_enabled_command_ids(model):
        if command_id in excluded:
            continue
        cmd = command_by_id.get(command_id)
        if cmd and cmd.get('category') not in include_categories:
            reporter.error(f"models/{model_id}.yaml: command {command_id} is enabled but category '{cmd.get('category')}' is not included")
    for cmd in commands:
        if command_enabled_for_model(cmd, model) and not command_visible_for_model(cmd, model):
            reporter.error(f"models/{model_id}.yaml: command {cmd.get('id')} is enabled but hidden by category filter")


def validate_duplicate_display_ids(model, commands, reporter):
    display_map = {}
    for cmd in get_commands_for_model(model, commands):
        display_id = cmd.get('display_id', cmd.get('id', ''))
        display_map.setdefault(display_id, []).append(cmd.get('id', ''))
    for display_id, ids in display_map.items():
        unique_ids = sorted(set(ids))
        if len(unique_ids) > 1:
            reporter.error(f"models/{model.get('model_id')}.yaml: duplicate display_id {display_id}: {', '.join(unique_ids)}")


def validate_variant_alignment(model, commands, strict, reporter):
    model_id = model.get('model_id')
    for cmd in get_commands_for_model(model, commands):
        syntax_choice = describe_variant_choice(cmd.get('syntax'), model)
        syntax_source = syntax_choice.get('source', '')
        if not is_custom_variant_source(syntax_source):
            continue
        for field in VARIANT_ALIGNED_FIELDS:
            field_source = describe_variant_choice(cmd.get(field), model).get('source', '')
            if field_source == syntax_source:
                continue
            message = (
                f"{model_id}:{cmd.get('id')}: syntax uses {syntax_source}, "
                f"but {field} uses {field_source or 'none'}"
            )
            if strict:
                reporter.error(message)
            else:
                reporter.warn(message)


def selected_release_content(cmd, model, language):
    return {
        'name': get_localized(cmd.get('name'), language),
        'summary': get_localized(cmd.get('summary'), language),
        'syntax': choose_variant(cmd.get('syntax'), model),
        'parameters': choose_variant(cmd.get('parameters'), model),
        'response': choose_variant(cmd.get('response'), model),
        'examples': choose_variant(cmd.get('examples'), model),
        'customer_notes': (cmd.get('notes', {}) or {}).get('customer', {}),
    }


def validate_revision_history(model, reporter):
    items = model.get('revision_history')
    if items in [None, '']:
        return
    where = model.get('__source', f"models/{model.get('model_id')}.yaml")
    if not isinstance(items, list):
        reporter.error(f'{where}: revision_history must be a list')
        return
    for index, item in enumerate(items, 1):
        if not isinstance(item, dict):
            reporter.error(f'{where}: revision_history[{index}] must be a mapping')
            continue
        if not item.get('version'):
            reporter.error(f'{where}: revision_history[{index}] missing version')
        if not (item.get('description') or item.get('changes')):
            reporter.error(f'{where}: revision_history[{index}] missing description or changes')


def validate_content(model, commands, customer, reporter):
    language = model.get('language', 'zh')
    model_id = model.get('model_id')
    if customer and (model.get('options', {}) or {}).get('show_internal_notes'):
        reporter.error(f'models/{model_id}.yaml: customer release must not enable show_internal_notes')
    validate_revision_history(model, reporter)
    visible = get_commands_for_model(model, commands)
    if not visible:
        reporter.error(f'models/{model_id}.yaml: no visible commands will be generated')
    for cmd in visible:
        where = f"{model_id}:{cmd.get('id', '<unknown>')}"
        status = cmd.get('status')
        if not status:
            reporter.error(f'{where}: missing status')
        elif status in BLOCKING_STATUS:
            reporter.error(f"{where}: status '{status}' is not allowed in release")
        if not cmd.get('since'):
            reporter.warn(f'{where}: missing since version map')
        for field, value in selected_release_content(cmd, model, language).items():
            if has_todo(value):
                reporter.error(f'{where}: selected release content contains TODO/TBD text in {field}')


def validate_model(model_id, commands, customer, strict_variants, reporter):
    model = load_model_profile(model_id)
    validate_visibility(model, commands, reporter)
    validate_duplicate_display_ids(model, commands, reporter)
    validate_variant_alignment(model, commands, strict_variants, reporter)
    validate_content(model, commands, customer, reporter)


def main():
    parser = argparse.ArgumentParser(description='Validate AT specs before release.')
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--model')
    group.add_argument('--all', action='store_true')
    parser.add_argument('--customer', action='store_true')
    parser.add_argument('--strict-variants', action='store_true', help='treat selected syntax/parameter/example variant mismatch as error')
    args = parser.parse_args()

    reporter = Reporter()
    commands = load_command_specs()
    validate_unknown_fields(commands, reporter)
    model_ids = [p.stem for p in iter_model_files()] if args.all else [args.model]
    strict_variants = args.strict_variants or args.customer
    for model_id in model_ids:
        validate_model(model_id, commands, args.customer, strict_variants, reporter)
    if reporter.errors:
        print(f'Release validation failed: {reporter.errors} error(s), {reporter.warnings} warning(s).')
        sys.exit(1)
    print(f'Release validation completed. Warning(s): {reporter.warnings}')


if __name__ == '__main__':
    main()
