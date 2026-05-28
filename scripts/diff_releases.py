import argparse
import json
from pathlib import Path

from atspec.core import ROOT, write_text


def find_catalog(release_dir: Path) -> Path:
    matches = sorted(release_dir.glob('*_catalog.json'))
    if not matches:
        raise SystemExit(f'No catalog JSON found in {release_dir}')
    if len(matches) > 1:
        raise SystemExit(f'Multiple catalog JSON files found in {release_dir}: {matches}')
    return matches[0]


def load_archived_catalog(model_id: str, version: str) -> dict:
    release_dir = ROOT / 'releases' / model_id / version
    if not release_dir.exists():
        raise SystemExit(f'Release directory not found: {release_dir}')
    return load_catalog_file(find_catalog(release_dir))


def load_catalog_file(path: Path) -> dict:
    if not path.exists():
        raise SystemExit(f'Catalog JSON not found: {path}')
    return json.loads(path.read_text(encoding='utf-8'))


def command_map(catalog: dict) -> dict:
    return {cmd.get('id'): cmd for cmd in catalog.get('commands', []) if cmd.get('id')}


def compare_command(left: dict, right: dict) -> list[dict]:
    fields = ['numeric_id', 'display_id', 'name', 'summary', 'category', 'type', 'status', 'syntax', 'parameters', 'response', 'examples']
    changes = []
    for field in fields:
        if left.get(field) != right.get(field):
            changes.append({
                'field': field,
                'left_value': left.get(field),
                'right_value': right.get(field),
                'left_variant': (left.get('variant', {}) or {}).get(field),
                'right_variant': (right.get('variant', {}) or {}).get(field),
            })
    return changes


def build_diff(model_id: str, left_version: str, right_version: str, left_catalog_path: str = '', right_catalog_path: str = '') -> dict:
    left = load_catalog_file(Path(left_catalog_path)) if left_catalog_path else load_archived_catalog(model_id, left_version)
    right = load_catalog_file(Path(right_catalog_path)) if right_catalog_path else load_archived_catalog(model_id, right_version)
    left_map = command_map(left)
    right_map = command_map(right)
    left_ids = [cmd.get('id') for cmd in left.get('commands', []) if cmd.get('id')]
    right_ids = [cmd.get('id') for cmd in right.get('commands', []) if cmd.get('id')]
    left_set = set(left_ids)
    right_set = set(right_ids)

    added = [right_map[cmd_id] for cmd_id in right_ids if cmd_id not in left_set]
    removed = [left_map[cmd_id] for cmd_id in left_ids if cmd_id not in right_set]
    changed = []
    for cmd_id in left_ids:
        if cmd_id not in right_set:
            continue
        changes = compare_command(left_map[cmd_id], right_map[cmd_id])
        if changes:
            changed.append({
                'id': cmd_id,
                'numeric_id': right_map[cmd_id].get('numeric_id'),
                'display_id': right_map[cmd_id].get('display_id', cmd_id),
                'category': right_map[cmd_id].get('category', ''),
                'source': right_map[cmd_id].get('source', ''),
                'changes': changes,
            })

    return {
        'schema_version': '1.1',
        'model_id': model_id,
        'left': {
            'version': left_version,
            'command_count': len(left_ids),
        },
        'right': {
            'version': right_version,
            'command_count': len(right_ids),
        },
        'summary': {
            'added_count': len(added),
            'removed_count': len(removed),
            'changed_count': len(changed),
        },
        'added': [command_summary(cmd) for cmd in added],
        'removed': [command_summary(cmd) for cmd in removed],
        'changed': changed,
    }


def command_summary(cmd: dict) -> dict:
    return {
        'id': cmd.get('id', ''),
        'numeric_id': cmd.get('numeric_id'),
        'display_id': cmd.get('display_id', ''),
        'name': cmd.get('name', ''),
        'category': cmd.get('category', ''),
        'status': cmd.get('status', ''),
        'source': cmd.get('source', ''),
    }


def render_markdown(data: dict) -> str:
    lines = [
        f"# Release Diff: {data['model_id']} {data['left']['version']} -> {data['right']['version']}",
        '',
        '## Summary',
        '',
        f"- Previous command count: `{data['left']['command_count']}`",
        f"- Current command count: `{data['right']['command_count']}`",
        f"- Added commands: `{data['summary']['added_count']}`",
        f"- Removed commands: `{data['summary']['removed_count']}`",
        f"- Changed commands: `{data['summary']['changed_count']}`",
        '',
        '## Added Commands',
        '',
    ]
    if data['added']:
        for cmd in data['added']:
            lines.append(f"- `{cmd['display_id']}` ({cmd['id']}, numeric_id={cmd.get('numeric_id')}) - {cmd.get('name', '')}")
    else:
        lines.append('- None')

    lines.extend(['', '## Removed Commands', ''])
    if data['removed']:
        for cmd in data['removed']:
            lines.append(f"- `{cmd['display_id']}` ({cmd['id']}, numeric_id={cmd.get('numeric_id')}) - {cmd.get('name', '')}")
    else:
        lines.append('- None')

    lines.extend(['', '## Changed Commands', ''])
    if data['changed']:
        for cmd in data['changed']:
            fields = ', '.join(change['field'] for change in cmd.get('changes', []))
            lines.append(f"- `{cmd['display_id']}` ({cmd['id']}, numeric_id={cmd.get('numeric_id')}): {fields}")
    else:
        lines.append('- None')
    return '\n'.join(lines) + '\n'


def main():
    parser = argparse.ArgumentParser(description='Diff two releases of the same model.')
    parser.add_argument('--model', required=True, help='model id, for example dp5x')
    parser.add_argument('--left', required=True, help='previous release version, for example V1.08')
    parser.add_argument('--right', required=True, help='current release version, for example V1.09')
    parser.add_argument('--left-catalog', default='', help='optional left catalog JSON path')
    parser.add_argument('--right-catalog', default='', help='optional right catalog JSON path, useful before current release is archived')
    parser.add_argument('--output-json', default='')
    parser.add_argument('--output-md', default='')
    args = parser.parse_args()

    data = build_diff(args.model, args.left, args.right, args.left_catalog, args.right_catalog)
    out_json = Path(args.output_json) if args.output_json else ROOT / 'output' / f'release_diff_{args.model}_{args.left}_to_{args.right}.json'
    out_md = Path(args.output_md) if args.output_md else ROOT / 'output' / f'release_diff_{args.model}_{args.left}_to_{args.right}.md'
    write_text(out_json, json.dumps(data, ensure_ascii=False, indent=2) + '\n')
    write_text(out_md, render_markdown(data))
    print(f'Generated: {out_json}')
    print(f'Generated: {out_md}')


if __name__ == '__main__':
    main()
