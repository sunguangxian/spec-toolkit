import json
import sys

from jsonschema import Draft202012Validator

from atspec.core import iter_model_files, load_yaml, toolkit_path
from export_model_catalog import build_catalog


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


def validate_catalog(model_id, schema, reporter):
    catalog = build_catalog(model_id)
    validator = Draft202012Validator(schema)
    for error in sorted(validator.iter_errors(catalog), key=lambda e: list(e.path)):
        path = '.'.join(str(p) for p in error.path) or '<root>'
        reporter.error(f'{model_id}: catalog schema error at {path}: {error.message}')

    if catalog.get('command_count') != len(catalog.get('commands', [])):
        reporter.error(f"{model_id}: command_count does not match commands length")

    seen_ids = set()
    seen_display_ids = set()
    for cmd in catalog.get('commands', []):
        cmd_id = cmd.get('id')
        display_id = cmd.get('display_id')
        if cmd_id in seen_ids:
            reporter.error(f'{model_id}: duplicate command id in catalog: {cmd_id}')
        seen_ids.add(cmd_id)
        if display_id in seen_display_ids:
            reporter.warn(f'{model_id}: duplicate display_id in catalog: {display_id}')
        seen_display_ids.add(display_id)


def main():
    reporter = Reporter()
    schema = load_yaml(toolkit_path('schemas', 'model_catalog.schema.json'))
    for model_file in iter_model_files():
        validate_catalog(model_file.stem, schema, reporter)
    if reporter.errors:
        print(f'Catalog validation failed: {reporter.errors} error(s), {reporter.warnings} warning(s).')
        sys.exit(1)
    print(f'Catalog validation completed. Warning(s): {reporter.warnings}')


if __name__ == '__main__':
    main()
