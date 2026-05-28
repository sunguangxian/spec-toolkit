import argparse
import sys
from pathlib import Path

from atspec.core import ROOT, load_model_profile


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


def expected_files(model, include_pdf, previous_version=''):
    model_name = model['model_name']
    version = model['version']
    model_id = model['model_id']
    files = [
        f'{model_name}_AT_Command_{version}.md',
        f'{model_name}_AT_Command_{version}.html',
        f'{model_name}_AT_Command_Changelog.md',
        'AT_Command_Support_Matrix.xlsx',
        f'release_review_{model_id}.md',
        f'{model_name}_AT_Command_{version}_catalog.json',
        f'{model_name}_AT_Command_{version}_test_cases.json',
        f'{model_id}_at_command_ids.h',
        f'{model_id}_AtCommandId.cs',
        f'{model_id}_at_command_ids.py',
        'style.css',
        'release_info.yaml',
    ]
    if previous_version:
        files.append(f'release_diff_{model_id}_{previous_version}_to_{version}.json')
        files.append(f'release_diff_{model_id}_{previous_version}_to_{version}.md')
    if include_pdf:
        files.append(f'{model_name}_AT_Command_{version}.pdf')
    return files


def validate_release_dir(model_id, include_pdf, release_dir, previous_version, reporter):
    model = load_model_profile(model_id)
    if release_dir is None:
        release_dir = ROOT / 'releases' / model_id / model['version']
    else:
        release_dir = Path(release_dir)

    if not release_dir.exists():
        reporter.error(f'release directory does not exist: {release_dir}')
        return

    for name in expected_files(model, include_pdf, previous_version):
        path = release_dir / name
        if not path.exists():
            reporter.error(f'missing release artifact: {path}')
        elif path.stat().st_size == 0:
            reporter.error(f'release artifact is empty: {path}')

    release_info = release_dir / 'release_info.yaml'
    if release_info.exists():
        text = release_info.read_text(encoding='utf-8')
        for token in ['validate_all: passed', 'validate_release: passed', 'commit:', 'files:']:
            if token not in text:
                reporter.error(f'{release_info}: missing token {token}')
        if previous_version and 'previous_release:' not in text:
            reporter.error(f'{release_info}: missing previous_release section')


def main():
    parser = argparse.ArgumentParser(description='Validate generated release artifacts.')
    parser.add_argument('--model', required=True, help='model id, for example dp5x')
    parser.add_argument('--pdf', action='store_true', help='expect PDF artifact')
    parser.add_argument('--release-dir', default='', help='optional staged release directory to validate')
    parser.add_argument('--previous-version', default='', help='expect release diff artifacts against this previous version')
    args = parser.parse_args()

    reporter = Reporter()
    validate_release_dir(args.model, args.pdf, args.release_dir or None, args.previous_version, reporter)
    if reporter.errors:
        print(f'Release artifact validation failed: {reporter.errors} error(s), {reporter.warnings} warning(s).')
        sys.exit(1)
    print(f'Release artifact validation completed. Warning(s): {reporter.warnings}')


if __name__ == '__main__':
    main()
