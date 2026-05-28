import subprocess
import sys

CHECKS = [
    [sys.executable, "scripts/validate_commands.py"],
    [sys.executable, "scripts/validate_examples.py"],
    [sys.executable, "scripts/validate_variants.py"],
    [sys.executable, "scripts/validate_binary_examples.py"],
    [sys.executable, "scripts/validate_strict.py"],
    [sys.executable, "scripts/validate_catalogs.py"],
    [sys.executable, "scripts/validate_test_cases.py"],
    [sys.executable, "scripts/validate_model_diff.py"],
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
