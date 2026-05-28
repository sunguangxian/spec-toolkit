from openpyxl import Workbook

from atspec.core import (
    ROOT,
    command_visible_for_model,
    describe_variant_choice,
    get_localized,
    iter_model_files,
    load_command_specs,
    load_model_profile,
)


def version_map_text(value) -> str:
    if not isinstance(value, dict) or not value:
        return ""
    return "; ".join(f"{model}:{version}" for model, version in sorted(value.items()))


def variant_sources(cmd, model) -> str:
    parts = []
    for field in ["syntax", "parameters", "response", "examples"]:
        choice = describe_variant_choice(cmd.get(field), model)
        source = choice.get("source", "")
        if source and source not in ["default", "raw"]:
            parts.append(f"{field}:{source}")
    return "; ".join(parts)


def variant_details(cmd, model) -> str:
    parts = []
    for field in ["syntax", "parameters", "response", "examples"]:
        choice = describe_variant_choice(cmd.get(field), model)
        source = choice.get("source", "")
        reason = choice.get("reason", "")
        if source:
            parts.append(f"{field}: {source} ({reason})")
    return "\n".join(parts)


def syntax_text(value) -> str:
    if not isinstance(value, dict):
        return ""
    lines = []
    for key in ["execute", "set", "read", "test", "write", "urc"]:
        text = value.get(key)
        if text:
            lines.append(f"{key}: {text}")
    return "\n".join(lines)


def selected_syntax(cmd, model) -> str:
    return syntax_text(describe_variant_choice(cmd.get("syntax"), model).get("value"))


def selected_since(cmd, model) -> str:
    since = cmd.get("since")
    if not isinstance(since, dict):
        return ""
    model_id = model.get("model_id")
    return since.get(model_id) or since.get("default") or ""


def selected_deprecated_since(cmd, model) -> str:
    deprecated_since = cmd.get("deprecated_since")
    if not isinstance(deprecated_since, dict):
        return ""
    model_id = model.get("model_id")
    return deprecated_since.get(model_id) or deprecated_since.get("default") or ""


def main():
    commands = load_command_specs()
    models = [load_model_profile(p.stem) for p in iter_model_files()]

    wb = Workbook()
    ws = wb.active
    ws.title = "Support Matrix"

    headers = [
        "Internal ID",
        "Command",
        "Name",
        "Category",
        "Status",
        "Source File",
        "Since Map",
        "Deprecated Since Map",
        "Replacement",
    ]
    for model in models:
        model_id = model["model_id"]
        headers.append(f"{model_id} Support")
        headers.append(f"{model_id} Since")
        headers.append(f"{model_id} Deprecated Since")
        headers.append(f"{model_id} Variant")
        headers.append(f"{model_id} Variant Detail")
        headers.append(f"{model_id} Selected Syntax")
    ws.append(headers)

    for cmd in commands:
        row = [
            cmd.get("id", ""),
            cmd.get("display_id", cmd.get("id", "")),
            get_localized(cmd.get("name", {}), "zh"),
            cmd.get("category", ""),
            cmd.get("status", ""),
            cmd.get("__source", ""),
            version_map_text(cmd.get("since")),
            version_map_text(cmd.get("deprecated_since")),
            cmd.get("replacement", ""),
        ]
        for model in models:
            supported = command_visible_for_model(cmd, model)
            row.append("Y" if supported else "N")
            row.append(selected_since(cmd, model) if supported else "")
            row.append(selected_deprecated_since(cmd, model) if supported else "")
            row.append(variant_sources(cmd, model) if supported else "")
            row.append(variant_details(cmd, model) if supported else "")
            row.append(selected_syntax(cmd, model) if supported else "")
        ws.append(row)

    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions
    for cell in ws[1]:
        cell.style = "Headline 4"
    for column in ws.columns:
        max_len = 0
        column_letter = column[0].column_letter
        for cell in column:
            max_len = max(max_len, len(str(cell.value or "")))
        ws.column_dimensions[column_letter].width = min(max(max_len + 2, 10), 80)

    out = ROOT / "output" / "AT_Command_Support_Matrix.xlsx"
    out.parent.mkdir(exist_ok=True)
    wb.save(out)
    print(f"Generated: {out}")


if __name__ == "__main__":
    main()
