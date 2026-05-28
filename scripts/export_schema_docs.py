import argparse
import json
from pathlib import Path

from atspec.core import ROOT, TOOLKIT_ROOT, toolkit_path, write_text


def describe_schema(path: Path) -> str:
    schema = json.loads(path.read_text(encoding='utf-8'))
    lines = [
        f"# {schema.get('title', path.stem)}",
        '',
        f"- File: `{path.relative_to(TOOLKIT_ROOT)}`",
        f"- Schema: `{schema.get('$schema', '')}`",
        f"- ID: `{schema.get('$id', '')}`",
        '',
        '## Required top-level fields',
        '',
    ]
    required = schema.get('required', []) or []
    if required:
        for item in required:
            lines.append(f"- `{item}`")
    else:
        lines.append('- None')

    lines.extend(['', '## Top-level properties', ''])
    properties = schema.get('properties', {}) or {}
    if properties:
        lines.append('| Field | Type | Description |')
        lines.append('|---|---|---|')
        for name, prop in properties.items():
            field_type = prop.get('type', '') if isinstance(prop, dict) else ''
            if not field_type and isinstance(prop, dict) and '$ref' in prop:
                field_type = prop['$ref']
            description = prop.get('description', '') if isinstance(prop, dict) else ''
            lines.append(f"| `{name}` | `{field_type}` | {description} |")
    else:
        lines.append('- None')

    defs = schema.get('$defs', {}) or {}
    if defs:
        lines.extend(['', '## Definitions', ''])
        for name, value in defs.items():
            lines.append(f"### `{name}`")
            lines.append('')
            if isinstance(value, dict):
                if value.get('description'):
                    lines.append(value['description'])
                    lines.append('')
                req = value.get('required', []) or []
                if req:
                    lines.append('Required fields: ' + ', '.join(f'`{item}`' for item in req))
                    lines.append('')
                props = value.get('properties', {}) or {}
                if props:
                    lines.append('| Field | Type | Description |')
                    lines.append('|---|---|---|')
                    for prop_name, prop in props.items():
                        field_type = prop.get('type', '') if isinstance(prop, dict) else ''
                        if not field_type and isinstance(prop, dict) and '$ref' in prop:
                            field_type = prop['$ref']
                        description = prop.get('description', '') if isinstance(prop, dict) else ''
                        lines.append(f"| `{prop_name}` | `{field_type}` | {description} |")
                    lines.append('')
    return '\n'.join(lines).rstrip() + '\n'


def export_schema_docs(output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    index_lines = ['# Schema Documentation', '']
    for path in sorted(toolkit_path('schemas').glob('*.schema.json')):
        out = output_dir / f'{path.stem}.md'
        write_text(out, describe_schema(path))
        index_lines.append(f"- [{path.name}]({out.name})")
        print(f'Generated: {out}')
    write_text(output_dir / 'README.md', '\n'.join(index_lines) + '\n')
    print(f"Generated: {output_dir / 'README.md'}")


def main():
    parser = argparse.ArgumentParser(description='Export Markdown documentation for JSON schemas.')
    parser.add_argument('--output-dir', default='', help='output directory, default: output/schema_docs')
    args = parser.parse_args()
    output_dir = Path(args.output_dir) if args.output_dir else ROOT / 'output' / 'schema_docs'
    export_schema_docs(output_dir)


if __name__ == '__main__':
    main()
