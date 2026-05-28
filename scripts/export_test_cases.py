import argparse
import json
from pathlib import Path

from atspec.core import ROOT, get_localized, write_text
from export_model_catalog import build_catalog


def iter_examples(value):
    if isinstance(value, list):
        for item in value:
            if isinstance(item, dict):
                yield item
    elif isinstance(value, dict):
        for item in value.values():
            yield from iter_examples(item)


def build_test_cases(model_id):
    catalog = build_catalog(model_id)
    language = catalog.get('model', {}).get('language', 'zh')
    cases = []
    for cmd in catalog.get('commands', []):
        examples = list(iter_examples(cmd.get('examples')))
        for index, example in enumerate(examples, 1):
            command_text = example.get('command')
            if not command_text:
                continue
            response = example.get('response') or []
            if isinstance(response, str):
                response = [response]
            cases.append({
                'case_id': f"{cmd.get('id')}_EXAMPLE_{index:03d}",
                'command_id': cmd.get('id', ''),
                'display_id': cmd.get('display_id', ''),
                'category': cmd.get('category', ''),
                'title': get_localized(example.get('title'), language),
                'command': command_text,
                'expected_response': response if isinstance(response, list) else [],
                'source': cmd.get('source', ''),
                'example_index': index,
            })
    return {
        'schema_version': '1.0',
        'model': catalog.get('model', {}),
        'case_count': len(cases),
        'cases': cases,
    }


def main():
    parser = argparse.ArgumentParser(description='Export selected AT examples as machine-readable test cases.')
    parser.add_argument('--model', required=True, help='model id, for example dp5x')
    parser.add_argument('--output', default='', help='output JSON path')
    args = parser.parse_args()

    test_cases = build_test_cases(args.model)
    model_name = test_cases['model'].get('model_name') or args.model
    version = test_cases['model'].get('version') or 'unknown'
    output = Path(args.output) if args.output else ROOT / 'output' / f'{model_name}_AT_Command_{version}_test_cases.json'
    write_text(output, json.dumps(test_cases, ensure_ascii=False, indent=2) + '\n')
    print(f'Generated: {output}')


if __name__ == '__main__':
    main()
