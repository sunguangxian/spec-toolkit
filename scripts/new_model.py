import argparse

from atspec.core import ROOT, write_text


def normalize_model_id(value: str) -> str:
    return value.strip().lower().replace("-", "_").replace(" ", "_")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True, help="model id, e.g. hs8851")
    parser.add_argument("--name", required=True, help="model display name, e.g. HS8851")
    parser.add_argument("--base", default="dmr_pei_common", help="base profile id")
    parser.add_argument("--version", default="V1.00", help="document version")
    parser.add_argument("--language", default="zh", choices=["zh", "en"])
    args = parser.parse_args()

    model_id = normalize_model_id(args.model)
    path = ROOT / "models" / f"{model_id}.yaml"
    if path.exists():
        raise FileExistsError(f"Model profile already exists: {path}")

    content = f"""model_id: {model_id}
model_name: {args.name}
base_profiles:
  - {args.base}

document_title: {args.name} AT Command User Manual
version: {args.version}
language: {args.language}

# Add categories that are not provided by base profiles.
include_categories: []

# Remove commands inherited from base profiles.
exclude_commands: []

# Add model-specific commands here.
command_order: []

# Place model-specific commands near inherited commands.
order_after: {{}}

features: {{}}
"""
    write_text(path, content)
    print(f"Created: {path}")


if __name__ == "__main__":
    main()
