import subprocess
import sys

from atspec.core import ROOT, iter_model_ids


def run(args: list[str]) -> None:
    print("==>", " ".join(args))
    result = subprocess.run(args, cwd=ROOT)
    if result.returncode != 0:
        raise SystemExit(result.returncode)


def main() -> None:
    model_ids = list(iter_model_ids())
    if not model_ids:
        print("No model YAML files found.")
        sys.exit(1)

    for model_id in model_ids:
        run([sys.executable, "scripts/export_changelog.py", "--model", model_id])


if __name__ == "__main__":
    main()
