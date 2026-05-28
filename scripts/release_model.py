import argparse
import datetime as dt
import hashlib
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

from atspec.core import (
    ROOT,
    get_base_profile_ids,
    get_commands_for_model,
    load_command_specs,
    load_model_profile,
    script_path,
    write_text,
)

GENERATED_DIR_PREFIXES = (
    "output/",
    "releases/",
)

RELEASE_ASSET_DIRS = (
    "assets",
)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def run(cmd: list[str]) -> None:
    print("==>", " ".join(cmd))
    result = subprocess.run(cmd, cwd=ROOT)
    if result.returncode != 0:
        raise SystemExit(result.returncode)


def git_text(args: list[str]) -> str:
    result = subprocess.run(["git", *args], cwd=ROOT, text=True, capture_output=True)
    return result.stdout.strip() if result.returncode == 0 else "unknown"


def git_commit() -> str:
    return git_text(["rev-parse", "HEAD"])


def status_path(line: str) -> str:
    if line.startswith("?? "):
        return line[3:].strip().strip('"')
    if len(line) >= 4:
        value = line[3:].strip().strip('"')
        if " -> " in value:
            value = value.split(" -> ", 1)[1].strip().strip('"')
        return value
    return line.strip().strip('"')


def is_generated_path(path: str) -> bool:
    normalized = path.replace("\\", "/")
    return any(normalized.startswith(prefix) for prefix in GENERATED_DIR_PREFIXES)


def ensure_clean_worktree() -> None:
    status = git_text(["status", "--porcelain"])
    if not status or status == "unknown":
        return
    dirty_lines = [line for line in status.splitlines() if line.strip()]
    blocking = [line for line in dirty_lines if not is_generated_path(status_path(line))]
    ignored = [line for line in dirty_lines if is_generated_path(status_path(line))]
    if ignored:
        print(f"Release note: ignoring {len(ignored)} generated file change(s) under output/ or releases/.")
    if blocking:
        print("Release aborted: source working tree is not clean. Commit or discard these changes first:")
        for line in blocking:
            print(f"  {line}")
        raise SystemExit(1)


def zip_release_dir(release_dir: Path, zip_path: Path) -> None:
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(release_dir.rglob("*")):
            if path.is_file():
                zf.write(path, path.relative_to(release_dir))


def replace_release_dir(staging_dir: Path, release_dir: Path) -> None:
    backup_dir = release_dir.with_name(f".{release_dir.name}.backup")
    if backup_dir.exists():
        shutil.rmtree(backup_dir)

    if release_dir.exists():
        release_dir.rename(backup_dir)
    try:
        staging_dir.rename(release_dir)
    except Exception:
        if release_dir.exists():
            shutil.rmtree(release_dir)
        if backup_dir.exists():
            backup_dir.rename(release_dir)
        raise
    if backup_dir.exists():
        shutil.rmtree(backup_dir)


def copy_release_asset_dirs(output: Path, staging_dir: Path) -> list[Path]:
    copied: list[Path] = []
    for dirname in RELEASE_ASSET_DIRS:
        src_dir = output / dirname
        if not src_dir.exists():
            continue
        dst_dir = staging_dir / dirname
        if dst_dir.exists():
            shutil.rmtree(dst_dir)
        shutil.copytree(src_dir, dst_dir)
        copied.extend(path for path in sorted(dst_dir.rglob("*")) if path.is_file())
    return copied


def release_model(model_id: str, include_pdf: bool, force: bool, customer: bool, previous_version: str) -> None:
    model_id = model_id.lower()
    ensure_clean_worktree()

    model = load_model_profile(model_id)
    model_name = model["model_name"]
    version = model["version"]
    release_root = ROOT / "releases" / model_id
    release_dir = release_root / version
    staging_dir = release_root / f".{version}.staging"
    zip_path = release_root / f"{model_id}_{version}_release.zip"
    zip_sha_path = release_root / f"{model_id}_{version}_release.zip.sha256"

    if release_dir.exists() and not force:
        print(f"Release aborted: {release_dir} already exists. Use --force to overwrite.")
        raise SystemExit(1)
    if staging_dir.exists():
        shutil.rmtree(staging_dir)

    run([sys.executable, script_path("validate_all.py")])
    release_check = [sys.executable, script_path("validate_release.py"), "--model", model_id]
    if customer:
        release_check.append("--customer")
    run(release_check)
    run([sys.executable, script_path("build_doc.py"), "--model", model_id, "--format", "md"])
    run([sys.executable, script_path("build_doc.py"), "--model", model_id, "--format", "html"])
    if include_pdf:
        run([sys.executable, script_path("build_doc.py"), "--model", model_id, "--format", "pdf"])
    run([sys.executable, script_path("export_changelog.py"), "--model", model_id])
    run([sys.executable, script_path("export_matrix.py")])
    run([sys.executable, script_path("export_release_review.py"), "--model", model_id])
    run([sys.executable, script_path("export_model_catalog.py"), "--model", model_id])
    run([sys.executable, script_path("export_test_cases.py"), "--model", model_id])
    for language in ["c", "csharp", "python"]:
        run([sys.executable, script_path("generate_command_bindings.py"), "--model", model_id, "--language", language])

    output = ROOT / "output"
    bindings_output = output / "bindings"
    base_name = f"{model_name}_AT_Command_{version}"
    release_review_name = f"release_review_{model_id}.md"
    catalog_name = f"{model_name}_AT_Command_{version}_catalog.json"
    test_cases_name = f"{model_name}_AT_Command_{version}_test_cases.json"
    if previous_version:
        run([
            sys.executable,
            script_path("diff_releases.py"),
            "--model",
            model_id,
            "--left",
            previous_version,
            "--right",
            version,
            "--right-catalog",
            str(output / catalog_name),
        ])
    release_root.mkdir(parents=True, exist_ok=True)
    staging_dir.mkdir(parents=True, exist_ok=False)

    candidates = [
        output / f"{base_name}.md",
        output / f"{base_name}.html",
        output / f"{model_name}_AT_Command_Changelog.md",
        output / "AT_Command_Support_Matrix.xlsx",
        output / release_review_name,
        output / catalog_name,
        output / test_cases_name,
        output / "style.css",
        bindings_output / f"{model_id}_at_command_ids.h",
        bindings_output / f"{model_id}_AtCommandId.cs",
        bindings_output / f"{model_id}_at_command_ids.py",
    ]
    if previous_version:
        candidates.append(output / f"release_diff_{model_id}_{previous_version}_to_{version}.json")
        candidates.append(output / f"release_diff_{model_id}_{previous_version}_to_{version}.md")
    if include_pdf:
        candidates.append(output / f"{base_name}.pdf")

    copied = []
    for path in candidates:
        if path.exists():
            target = staging_dir / path.name
            shutil.copy2(path, target)
            copied.append(target)
    copied.extend(copy_release_asset_dirs(output, staging_dir))

    commands = get_commands_for_model(model, load_command_specs())
    base_profile_ids = get_base_profile_ids(model)

    lines = [
        f"model: {model_id}",
        f"model_name: {model_name}",
        f"version: {version}",
        f"release_type: {'customer' if customer else 'internal'}",
        f"generated_at: {dt.datetime.now(dt.timezone.utc).isoformat()}",
        f"commit: {git_commit()}",
        "source:",
        f"  model_file: models/{model_id}.yaml",
        "  base_profiles:",
    ]
    if base_profile_ids:
        for profile_id in base_profile_ids:
            lines.append(f"    - profiles/{profile_id}.yaml")
    else:
        lines.append("    - null")
    lines.append(f"  command_count: {len(commands)}")
    if previous_version:
        lines.append("  previous_release:")
        lines.append(f"    version: {previous_version}")
    lines.append("checks:")
    lines.append("  validate_all: passed")
    lines.append("  validate_release: passed")
    lines.append("files:")
    for path in copied:
        lines.append(f"  - name: {path.relative_to(staging_dir).as_posix()}")
        lines.append(f"    sha256: {sha256_file(path)}")

    write_text(staging_dir / "release_info.yaml", "\n".join(lines) + "\n")
    artifact_check = [
        sys.executable,
        script_path("validate_release_artifacts.py"),
        "--model",
        model_id,
        "--release-dir",
        str(staging_dir),
    ]
    if include_pdf:
        artifact_check.append("--pdf")
    if previous_version:
        artifact_check.extend(["--previous-version", previous_version])
    run(artifact_check)

    replace_release_dir(staging_dir, release_dir)
    zip_release_dir(release_dir, zip_path)
    write_text(zip_sha_path, f"{sha256_file(zip_path)}  {zip_path.name}\n")
    print(f"Released: {release_dir}")
    print(f"Package: {zip_path}")
    print(f"Package SHA256: {zip_sha_path}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True, help="model id, for example dp5x")
    parser.add_argument("--pdf", action="store_true", help="also build and archive PDF")
    parser.add_argument("--force", action="store_true", help="overwrite existing release directory")
    parser.add_argument("--customer", action="store_true", help="enforce customer-document release checks")
    parser.add_argument("--previous-version", default="", help="include release diff against this archived version")
    args = parser.parse_args()
    release_model(args.model, args.pdf, args.force, args.customer, args.previous_version)


if __name__ == "__main__":
    main()
