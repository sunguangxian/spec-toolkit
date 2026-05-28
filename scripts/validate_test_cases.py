from jsonschema import Draft202012Validator

from atspec.core import iter_model_files, load_yaml, toolkit_path
from export_test_cases import build_test_cases


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


def validate_model(model_id, schema, reporter):
    data = build_test_cases(model_id)
    validator = Draft202012Validator(schema)
    for error in sorted(validator.iter_errors(data), key=lambda e: list(e.path)):
        path = '.'.join(str(p) for p in error.path) or '<root>'
        reporter.error(f'{model_id}: test case schema error at {path}: {error.message}')

    if data.get('case_count') != len(data.get('cases', [])):
        reporter.error(f'{model_id}: case_count does not match cases length')

    seen = set()
    for case in data.get('cases', []):
        case_id = case.get('case_id')
        if case_id in seen:
            reporter.error(f'{model_id}: duplicate case_id {case_id}')
        seen.add(case_id)
        command = case.get('command', '')
        display_id = case.get('display_id', '')
        if display_id and not command.startswith(display_id):
            reporter.warn(f'{model_id}:{case_id}: command does not start with display_id {display_id}')


def main():
    reporter = Reporter()
    schema = load_yaml(toolkit_path('schemas', 'test_cases.schema.json'))
    for model_file in iter_model_files():
        validate_model(model_file.stem, schema, reporter)
    if reporter.errors:
        print(f'Test case validation failed: {reporter.errors} error(s), {reporter.warnings} warning(s).')
        raise SystemExit(1)
    print(f'Test case validation completed. Warning(s): {reporter.warnings}')


if __name__ == '__main__':
    main()
