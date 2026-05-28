import subprocess
import sys

from atspec.core import iter_model_files


LANGUAGES = ['c', 'csharp', 'python']


def run(cmd):
    print('==>', ' '.join(cmd))
    result = subprocess.run(cmd)
    if result.returncode != 0:
        raise SystemExit(result.returncode)


def main():
    for model_file in iter_model_files():
        for language in LANGUAGES:
            run([sys.executable, 'scripts/generate_command_bindings.py', '--model', model_file.stem, '--language', language])


if __name__ == '__main__':
    main()
