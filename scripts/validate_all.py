import subprocess
import sys

from atspec.core import script_path

CHECKS = [
    [sys.executable, script_path("validate_commands.py")],
    [sys.executable, script_path("validate_examples.py")],
    [sys.executable, script_path("validate_variants.py")],
    [sys.executable, script_path("validate_binary_examples.py")],
    [sys.executable, script_path("validate_strict.py")],
    [sys.executable, script_path("validate_catalogs.py")],
    [sys.executable, script_path("validate_test_cases.py")],
    [sys.executable, script_path("validate_model_diff.py")],
]


def main() -> None:
    for cmd in CHECKS:
        print("==>", " ".join(cmd))
        result = subprocess.run(cmd)
        if result.returncode != 0:
            sys.exit(result.returncode)
    print("All AT spec checks passed.")


if __name__ == "__main__":
    main()
