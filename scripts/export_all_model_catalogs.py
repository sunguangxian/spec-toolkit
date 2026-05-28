import subprocess
import sys

from atspec.core import iter_model_files


def run(cmd):
    print('==>', ' '.join(cmd))
    result = subprocess.run(cmd)
    if result.returncode != 0:
        raise SystemExit(result.returncode)


def main():
    for model_file in iter_model_files():
        run([sys.executable, 'scripts/export_model_catalog.py', '--model', model_file.stem])


if __name__ == '__main__':
    main()
