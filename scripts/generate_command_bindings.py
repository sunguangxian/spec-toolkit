import argparse
import re
from pathlib import Path

from atspec.core import ROOT, write_text
from export_model_catalog import build_catalog


def safe_identifier(value: str) -> str:
    value = re.sub(r'[^0-9A-Za-z_]+', '_', value or '')
    value = re.sub(r'_+', '_', value).strip('_')
    if not value:
        value = 'UNKNOWN'
    if value[0].isdigit():
        value = '_' + value
    return value.upper()


def get_numeric_id(cmd: dict) -> int:
    if 'numeric_id' not in cmd:
        raise ValueError(f"catalog command {cmd.get('id', '<unknown>')} is missing numeric_id")
    return int(cmd['numeric_id'])


def render_c_header(catalog: dict) -> str:
    model = catalog['model']
    guard = safe_identifier(f"{model['model_id']}_AT_COMMAND_IDS_H")
    lines = [
        f"#ifndef {guard}",
        f"#define {guard}",
        '',
        '/* Auto-generated from AT-Spec catalog. Do not edit manually. */',
        f"/* Model: {model.get('model_name', '')} Version: {model.get('version', '')} */",
        '/* Values come from explicit command numeric_id fields. */',
        '',
        'typedef enum',
        '{',
    ]
    for cmd in catalog.get('commands', []):
        name = safe_identifier(cmd.get('id', ''))
        lines.append(f"    AT_CMD_ID_{name} = {get_numeric_id(cmd)}, /* {cmd.get('display_id', '')} */")
    lines.extend([
        '} at_command_id_t;',
        '',
        '#endif',
        '',
    ])
    return '\n'.join(lines)


def render_csharp(catalog: dict) -> str:
    model = catalog['model']
    lines = [
        '// Auto-generated from AT-Spec catalog. Do not edit manually.',
        f"// Model: {model.get('model_name', '')} Version: {model.get('version', '')}",
        '// Values come from explicit command numeric_id fields.',
        '',
        'namespace AtSpec.Generated',
        '{',
        '    public enum AtCommandId',
        '    {',
    ]
    for cmd in catalog.get('commands', []):
        name = ''.join(part.capitalize() for part in safe_identifier(cmd.get('id', '')).lower().split('_'))
        lines.append(f"        {name} = {get_numeric_id(cmd)}, // {cmd.get('display_id', '')}")
    lines.extend([
        '    }',
        '}',
        '',
    ])
    return '\n'.join(lines)


def render_python(catalog: dict) -> str:
    model = catalog['model']
    lines = [
        '# Auto-generated from AT-Spec catalog. Do not edit manually.',
        f"# Model: {model.get('model_name', '')} Version: {model.get('version', '')}",
        '# Values come from explicit command numeric_id fields.',
        '',
        'from enum import IntEnum',
        '',
        '',
        'class AtCommandId(IntEnum):',
    ]
    commands = catalog.get('commands', [])
    if not commands:
        lines.append('    pass')
    for cmd in commands:
        name = safe_identifier(cmd.get('id', ''))
        lines.append(f"    {name} = {get_numeric_id(cmd)}  # {cmd.get('display_id', '')}")
    lines.append('')
    return '\n'.join(lines)


def generate(model_id: str, language: str, output_dir: Path) -> Path:
    catalog = build_catalog(model_id)
    model = catalog['model']
    output_dir.mkdir(parents=True, exist_ok=True)
    if language == 'c':
        path = output_dir / f"{model['model_id']}_at_command_ids.h"
        write_text(path, render_c_header(catalog))
    elif language == 'csharp':
        path = output_dir / f"{model['model_id']}_AtCommandId.cs"
        write_text(path, render_csharp(catalog))
    elif language == 'python':
        path = output_dir / f"{model['model_id']}_at_command_ids.py"
        write_text(path, render_python(catalog))
    else:
        raise SystemExit(f'Unsupported language: {language}')
    return path


def main():
    parser = argparse.ArgumentParser(description='Generate command ID bindings from selected model catalog.')
    parser.add_argument('--model', required=True, help='model id, for example dp5x')
    parser.add_argument('--language', choices=['c', 'csharp', 'python'], required=True)
    parser.add_argument('--output-dir', default='', help='output directory')
    args = parser.parse_args()

    output_dir = Path(args.output_dir) if args.output_dir else ROOT / 'output' / 'bindings'
    path = generate(args.model, args.language, output_dir)
    print(f'Generated: {path}')


if __name__ == '__main__':
    main()
