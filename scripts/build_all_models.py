import argparse
import sys

from atspec.core import iter_model_ids
from build_doc import build_model


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--format",
        dest="formats",
        action="append",
        choices=["md", "html", "pdf"],
        help="Output format. Can be specified multiple times. Default: md + html.",
    )
    args = parser.parse_args()

    model_ids = list(iter_model_ids())
    if not model_ids:
        print("No model YAML files found.")
        sys.exit(1)

    formats = args.formats or ["md", "html"]
    for model_id in model_ids:
        for fmt in formats:
            build_model(model_id, fmt)


if __name__ == "__main__":
    main()
