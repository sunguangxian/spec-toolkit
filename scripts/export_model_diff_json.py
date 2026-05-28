import argparse
import json
from pathlib import Path

from atspec.core import ROOT, describe_variant_choice, get_commands_for_model, load_command_specs, load_model_profile, write_text
from export_model_catalog import selected_command


def command_signature(cmd, model, language):
    selected = selected_command(cmd, model, language)
    return {
        'numeric_id': selected.get('numeric_id'),
        'display_id': selected.get('display_id'),
        'category': selected.get('category'),
        'status': selected.get('status'),
        'syntax': selected.get('syntax'),
        'parameters': selected.get('parameters'),
        'response': selected.get('response'),
        'examples': selected.get('examples'),
    }


def changed_fields(cmd, left_model, right_model):
    left_lang = left_model.get('language', 'zh')
    right_lang = right_model.get('language', 'zh')
    left = command_signature(cmd, left_model, left_lang)
    right = command_signature(cmd, right_model, right_lang)
    changes = []
    for field in ['numeric_id', 'display_id', 'category', 'status', 'syntax', 'parameters', 'response', 'examples']:
        if left.get(field) != right.get(field):
            item = {
                'field': field,
                'left_value': left.get(field),
                'right_value': right.get(field),
            }
            if field in ['syntax', 'parameters', 'response', 'examples']:
                left_choice = describe_variant_choice(cmd.get(field), left_model)
                right_choice = describe_variant_choice(cmd.get(field), right_model)
                item['left_variant'] = {
                    'source': left_choice.get('source', ''),
                    'reason': left_choice.get('reason', ''),
                }
                item['right_variant'] = {
                    'source': right_choice.get('source', ''),
                    'reason': right_choice.get('reason', ''),
                }
            changes.append(item)
    return changes


def command_ref(cmd, cmd_id):
    return {
        'id': cmd_id,
        'numeric_id': cmd.get('numeric_id'),
        'display_id': cmd.get('display_id', cmd_id),
        'category': cmd.get('category', ''),
        'source': cmd.get('__source', ''),
    }


def build_diff(left_id, right_id):
    commands = load_command_specs()
    command_map = {cmd['id']: cmd for cmd in commands if cmd.get('id')}
    left_model = load_model_profile(left_id)
    right_model = load_model_profile(right_id)
    left_commands = get_commands_for_model(left_model, commands)
    right_commands = get_commands_for_model(right_model, commands)
    left_ids = [cmd['id'] for cmd in left_commands]
    right_ids = [cmd['id'] for cmd in right_commands]
    left_set = set(left_ids)
    right_set = set(right_ids)

    only_left = []
    for cmd_id in left_ids:
        if cmd_id not in right_set:
            only_left.append(command_ref(command_map[cmd_id], cmd_id))

    only_right = []
    for cmd_id in right_ids:
        if cmd_id not in left_set:
            only_right.append(command_ref(command_map[cmd_id], cmd_id))

    changed = []
    for cmd_id in left_ids:
        if cmd_id not in right_set:
            continue
        cmd = command_map[cmd_id]
        changes = changed_fields(cmd, left_model, right_model)
        if changes:
            changed.append({
                'id': cmd_id,
                'numeric_id': cmd.get('numeric_id'),
                'display_id': cmd.get('display_id', cmd_id),
                'category': cmd.get('category', ''),
                'source': cmd.get('__source', ''),
                'changes': changes,
            })

    return {
        'schema_version': '1.1',
        'left': {
            'model_id': left_model.get('model_id', left_id),
            'model_name': left_model.get('model_name', ''),
            'version': left_model.get('version', ''),
            'command_count': len(left_ids),
        },
        'right': {
            'model_id': right_model.get('model_id', right_id),
            'model_name': right_model.get('model_name', ''),
            'version': right_model.get('version', ''),
            'command_count': len(right_ids),
        },
        'summary': {
            'only_left_count': len(only_left),
            'only_right_count': len(only_right),
            'changed_count': len(changed),
        },
        'only_left': only_left,
        'only_right': only_right,
        'changed': changed,
    }


def main():
    parser = argparse.ArgumentParser(description='Export model diff as machine-readable JSON.')
    parser.add_argument('--left', required=True, help='left model id')
    parser.add_argument('--right', required=True, help='right model id')
    parser.add_argument('--output', default='', help='output JSON path')
    args = parser.parse_args()

    data = build_diff(args.left, args.right)
    output = Path(args.output) if args.output else ROOT / 'output' / f'diff_{args.left}_{args.right}.json'
    write_text(output, json.dumps(data, ensure_ascii=False, indent=2) + '\n')
    print(f'Generated: {output}')


if __name__ == '__main__':
    main()
