import subprocess
import sys

from atspec.core import iter_model_files, script_path


def run(cmd):
    print('==>', ' '.join(cmd))
    result = subprocess.run(cmd)
    if result.returncode != 0:
        raise SystemExit(result.returncode)


def main():
    for model_file in iter_model_files():
        run([sys.executable, script_path('export_release_review.py'), '--model', model_file.stem])


if __name__ == '__main__':
    main()
