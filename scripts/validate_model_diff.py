from jsonschema import Draft202012Validator

from atspec.core import load_yaml, toolkit_path
from export_model_diff_json import build_diff


REPRESENTATIVE_DIFFS = [
    ('dp5x', 'km2'),
    ('dp5x', 'rsc'),
]


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


def validate_diff(left, right, schema, reporter):
    data = build_diff(left, right)
    validator = Draft202012Validator(schema)
    for error in sorted(validator.iter_errors(data), key=lambda e: list(e.path)):
        path = '.'.join(str(p) for p in error.path) or '<root>'
        reporter.error(f'{left} vs {right}: diff schema error at {path}: {error.message}')

    summary = data.get('summary', {})
    if summary.get('only_left_count') != len(data.get('only_left', [])):
        reporter.error(f'{left} vs {right}: only_left_count mismatch')
    if summary.get('only_right_count') != len(data.get('only_right', [])):
        reporter.error(f'{left} vs {right}: only_right_count mismatch')
    if summary.get('changed_count') != len(data.get('changed', [])):
        reporter.error(f'{left} vs {right}: changed_count mismatch')


def main():
    reporter = Reporter()
    schema = load_yaml(toolkit_path('schemas', 'model_diff.schema.json'))
    for left, right in REPRESENTATIVE_DIFFS:
        validate_diff(left, right, schema, reporter)
    if reporter.errors:
        print(f'Model diff validation failed: {reporter.errors} error(s), {reporter.warnings} warning(s).')
        raise SystemExit(1)
    print(f'Model diff validation completed. Warning(s): {reporter.warnings}')


if __name__ == '__main__':
    main()
