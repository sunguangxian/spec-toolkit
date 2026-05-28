import argparse
import re
import shutil
from datetime import date

from jinja2 import Environment, FileSystemLoader

from atspec.code_appendix import load_code_appendices
from atspec.core import (
    ROOT,
    choose_variant,
    get_commands_for_model,
    get_localized,
    get_variant_description,
    load_command_specs,
    load_model_profile,
    toolkit_path,
    write_text,
)
from atspec.image_appendix import copy_image_assets, load_image_appendices
from atspec.revision_history import collect_revision_history

DEFAULT_RESPONSE = {
    "timeout_ms": 1000,
    "success": [{"pattern": "OK", "final": True}],
    "error": [{"pattern": "+CME ERROR:<code>", "final": True}],
}

DEFAULT_SERIAL_COMMUNICATION = {
    "description": {
        "zh": "本机型默认通过 UART 串口收发 AT 指令。除产品硬件说明另有定义外，串口参数如下。",
        "en": "This model uses a UART serial port for AT command communication by default. Unless otherwise specified by the hardware design, use the following settings.",
    },
    "rows": [
        {"name": {"zh": "接口类型", "en": "Interface"}, "value": {"zh": "UART 串口", "en": "UART serial port"}},
        {"name": {"zh": "用途", "en": "Purpose"}, "value": {"zh": "AT 指令收发", "en": "AT command and response"}},
        {"name": {"zh": "波特率", "en": "Baud rate"}, "value": "115200 bps"},
        {"name": {"zh": "数据位", "en": "Data bits"}, "value": "8"},
        {"name": {"zh": "校验位", "en": "Parity"}, "value": {"zh": "无", "en": "None"}},
        {"name": {"zh": "停止位", "en": "Stop bits"}, "value": "1"},
        {"name": {"zh": "流控", "en": "Flow control"}, "value": {"zh": "无", "en": "None"}},
        {"name": {"zh": "字符编码", "en": "Encoding"}, "value": "ASCII"},
        {"name": {"zh": "行结束符", "en": "Line ending"}, "value": "CRLF (\\r\\n)"},
    ],
    "notes": {
        "zh": ["具体 UART 引脚、电平标准和接口座定义以对应产品硬件规格为准。"],
        "en": ["UART pins, voltage level, and connector definition depend on the product hardware specification."],
    },
}

DEFAULT_USB_COMMUNICATION = {
    "description": {
        "zh": "本机型通过 USB 虚拟串口收发 AT 指令。PC 端枚举出对应的 USB CDC/VCOM 端口后，通过该端口发送和接收 AT 指令。",
        "en": "This model uses a USB virtual COM port for AT command communication. After the USB CDC/VCOM port is enumerated on the PC, send and receive AT commands through that port.",
    },
    "rows": [
        {"name": {"zh": "接口类型", "en": "Interface"}, "value": "USB CDC ACM / Virtual COM Port"},
        {"name": {"zh": "用途", "en": "Purpose"}, "value": {"zh": "AT 指令收发", "en": "AT command and response"}},
        {"name": {"zh": "PC 端表现", "en": "PC-side port"}, "value": {"zh": "虚拟串口 COM 端口", "en": "Virtual COM port"}},
        {"name": {"zh": "波特率", "en": "Baud rate"}, "value": {"zh": "不适用，由 USB 虚拟串口承载", "en": "Not applicable; carried by USB CDC/VCOM"}},
        {"name": {"zh": "字符编码", "en": "Encoding"}, "value": "ASCII"},
        {"name": {"zh": "行结束符", "en": "Line ending"}, "value": "CRLF (\\r\\n)"},
    ],
    "notes": {
        "zh": ["DP990DLF 使用 USB 端口进行 AT 指令通信，不按 UART 串口波特率配置。"],
        "en": ["DP990DLF uses the USB port for AT command communication and does not use UART baud-rate settings."],
    },
}

USB_MODEL_IDS = {"dp990dlf", "dp990_dlf"}
A4_VIEWPORT_WIDTH_CSS_PX = round(210 * 96 / 25.4)
A4_VIEWPORT_HEIGHT_CSS_PX = round(297 * 96 / 25.4)


def get_generated_date() -> str:
    return date.today().isoformat()


def make_anchor(value: str) -> str:
    text = re.sub(r"[^0-9A-Za-z_+-]+", "-", value or "")
    return text.strip("-").lower() or "command"


def format_bool(value) -> str:
    return "Yes" if bool(value) else "No"


def format_range_values(param: dict) -> str:
    if param.get("range") not in [None, ""]:
        return str(param.get("range"))
    values = param.get("values")
    if values in [None, ""]:
        return "-"
    if isinstance(values, list):
        return ", ".join(str(item) for item in values)
    return str(values)


def normalize_response_block(response: dict) -> dict:
    if not isinstance(response, dict):
        return {}
    result = dict(response)
    for key in ["success", "error", "urc"]:
        entries = result.get(key) or []
        normalized = []
        for entry in entries:
            if isinstance(entry, dict):
                normalized.append({
                    "pattern": entry.get("pattern", ""),
                    "final": bool(entry.get("final", False)),
                })
            elif isinstance(entry, str):
                normalized.append({"pattern": entry, "final": False})
        result[key] = normalized
    return result


def default_communication_for_model(model: dict) -> dict:
    model_id = str(model.get("model_id", "")).lower()
    if model_id in USB_MODEL_IDS:
        return DEFAULT_USB_COMMUNICATION
    return DEFAULT_SERIAL_COMMUNICATION


def normalize_communication(model: dict) -> dict:
    language = model.get("language", "zh")
    config = model.get("communication") or default_communication_for_model(model)
    rows = []
    for row in config.get("rows", []) or []:
        if isinstance(row, dict):
            rows.append({
                "name": get_localized(row.get("name"), language),
                "value": get_localized(row.get("value"), language),
            })
    notes_value = config.get("notes", []) or []
    if isinstance(notes_value, dict):
        notes = notes_value.get(language, []) or []
    elif isinstance(notes_value, list):
        notes = notes_value
    else:
        notes = []
    return {
        "description": get_localized(config.get("description"), language),
        "rows": rows,
        "notes": notes,
    }


def collect_render_items(model, commands):
    language = model.get("language", "zh")
    items = []
    for cmd in commands:
        syntax = choose_variant(cmd.get("syntax", {}), model) or {}
        response = normalize_response_block(choose_variant(cmd.get("response", {}), model) or DEFAULT_RESPONSE)
        parameters = choose_variant(cmd.get("parameters", {}), model) or []
        examples = choose_variant(cmd.get("examples", {}), model) or []

        normalized_params = []
        for param in parameters:
            if isinstance(param, dict):
                p = dict(param)
                p["description_text"] = get_localized(p.get("description"), language)
                p["required_text"] = format_bool(p.get("required"))
                p["range_values_text"] = format_range_values(p)
                normalized_params.append(p)

        normalized_examples = []
        for example in examples:
            if isinstance(example, dict):
                e = dict(example)
                e["title_text"] = get_localized(e.get("title"), language)
                normalized_examples.append(e)

        notes = []
        opt = model.get("options", {})
        cmd_notes = cmd.get("notes", {})
        if opt.get("show_customer_notes", True):
            notes += cmd_notes.get("customer", {}).get(language, [])
        if opt.get("show_internal_notes", False):
            notes += cmd_notes.get("internal", {}).get(language, [])

        display_id = cmd.get("display_id") or cmd.get("id")
        items.append({
            "anchor": make_anchor(cmd.get("id") or display_id),
            "command": cmd,
            "display_id": display_id,
            "name": get_localized(cmd.get("name"), language),
            "summary": get_localized(cmd.get("summary"), language),
            "syntax": syntax,
            "syntax_description": get_variant_description(cmd.get("syntax", {}), model, language),
            "response": response,
            "parameters": normalized_params,
            "examples": normalized_examples,
            "notes": notes,
        })
    return items


def is_error_code_item(item: dict) -> bool:
    return item.get("command", {}).get("category") == "Error Code"


def render_markdown_communication(communication: dict) -> str:
    out = ["\n## 通信端口配置\n"]
    if communication.get("description"):
        out.append(str(communication["description"]))
        out.append("")
    out.append("| 项目 | 配置 |")
    out.append("|---|---|")
    for row in communication.get("rows", []):
        out.append(f"| {row.get('name', '')} | {row.get('value', '')} |")
    if communication.get("notes"):
        out.append("\n说明：")
        for note in communication["notes"]:
            out.append(f"- {note}")
    out.append("")
    return "\n".join(out)


def render_markdown_revision_history(revision_history: list[dict]) -> str:
    if not revision_history:
        return ""
    out = ["\n## 修改记录\n", "| Version | Date | Description |", "|---|---|---|"]
    for item in revision_history:
        changes = item.get("changes") or []
        if isinstance(changes, list):
            description = "<br>".join(str(change) for change in changes)
        else:
            description = str(changes)
        out.append(f"| {item.get('version', '')} | {item.get('date', '')} | {description} |")
    out.append("")
    return "\n".join(out)


def render_markdown_error_code_appendix(rendered_commands: list) -> str:
    error_items = [item for item in rendered_commands if is_error_code_item(item)]
    if not error_items:
        return ""
    item = error_items[0]
    out = ["\n### A.1 错误码说明\n"]
    if item.get("summary"):
        out.append(str(item["summary"]))
        out.append("")
    out.append("| ErrorCode | Description |")
    out.append("|---:|---|")
    for p in item.get("parameters", []):
        out.append(f"| {p.get('name', '')} | {p.get('description_text', '')} |")
    out.append("")
    return "\n".join(out)


def render_markdown_image_appendices(image_appendices: list, language: str) -> str:
    if not image_appendices:
        return ""
    title = "A.2 流程图" if language == "zh" else "A.2 Flow Diagrams"
    out = [f"\n### {title}\n"]
    for index, appendix in enumerate(image_appendices, 1):
        out.append(f"#### A.2.{index} {appendix['title']}")
        if appendix.get("description"):
            out.append("")
            out.append(str(appendix["description"]))
        for image_index, image in enumerate(appendix.get("images", []), 1):
            out.append("")
            out.append(f"![{image.get('alt', '')}]({image.get('src', '')})")
            if image.get("caption"):
                out.append(f"图 A.2.{index}-{image_index} {image['caption']}")
        out.append("")
    return "\n".join(out)


def render_markdown_code_appendices(code_appendices: list, language: str, appendix_no: str = "A.2") -> str:
    if not code_appendices:
        return ""
    title = f"{appendix_no} 参考代码" if language == "zh" else f"{appendix_no} Reference Code"
    out = [f"\n### {title}\n"]
    for index, appendix in enumerate(code_appendices, 1):
        out.append(f"#### {appendix_no}.{index} {appendix['title']}")
        if appendix.get("description"):
            out.append("")
            out.append(str(appendix["description"]))
        for file_item in appendix.get("files", []):
            out.append("")
            out.append(f"##### `{file_item['path']}`")
            code = str(file_item.get("content", "")).rstrip()
            out.append(f"```{file_item.get('language', 'text')}")
            out.append(code)
            out.append("```")
        out.append("")
    return "\n".join(out)


def render_markdown(model, commands):
    language = model.get("language", "zh")
    env = Environment(loader=FileSystemLoader(toolkit_path("templates")), autoescape=False)
    tpl = env.get_template("command.md.j2")
    code_appendices = load_code_appendices(model)
    image_appendices = load_image_appendices(model)
    rendered_items = collect_render_items(model, commands)
    command_items = [item for item in rendered_items if not is_error_code_item(item)]
    generated_date = get_generated_date()
    revision_history = collect_revision_history(model, rendered_items, generated_date, language)

    out = []
    out.append(f"# {model['document_title']}\n")
    out.append(f"版本：{model['version']}\n")
    out.append(f"发布日期：{generated_date}\n")
    out.append(render_markdown_revision_history(revision_history))
    out.append(render_markdown_communication(normalize_communication(model)))
    out.append("\n## 支持指令列表\n")
    for i, item in enumerate(command_items, 1):
        out.append(f"{i}. `{item['display_id']}` - {item['name']}")
    out.append("\n---\n")

    for i, item in enumerate(command_items, 1):
        out.append(tpl.render(
            index=i,
            command=item["command"],
            language=language,
            syntax=item["syntax"],
            syntax_description=item["syntax_description"],
            response=item["response"],
            parameters=item["parameters"],
            examples=item["examples"],
            notes=item["notes"],
        ))
        out.append("\n---\n")

    if render_markdown_error_code_appendix(rendered_items) or image_appendices or code_appendices:
        out.append("\n## 附录\n")
        out.append(render_markdown_error_code_appendix(rendered_items))
        out.append(render_markdown_image_appendices(image_appendices, language))
        code_no = "A.3" if image_appendices else "A.2"
        out.append(render_markdown_code_appendices(code_appendices, language, code_no))
    return "\n".join(out)


def render_html(model, commands):
    language = model.get("language", "zh")
    env = Environment(loader=FileSystemLoader(toolkit_path("templates")), autoescape=True)
    tpl = env.get_template("document.html.j2")

    generated_date = get_generated_date()
    rendered_commands = collect_render_items(model, commands)
    revision_history = collect_revision_history(model, rendered_commands, generated_date, language)
    code_appendices = load_code_appendices(model)
    image_appendices = load_image_appendices(model)
    command_rows = []
    for item in rendered_commands:
        cmd = item["command"]
        row = dict(cmd)
        row["anchor"] = item["anchor"]
        row["localized_name"] = item["name"]
        row["display_id"] = item["display_id"]
        command_rows.append(row)

    return tpl.render(
        model=model,
        language=language,
        generated_date=generated_date,
        revision_history=revision_history,
        communication=normalize_communication(model),
        commands=command_rows,
        rendered_commands=rendered_commands,
        code_appendices=code_appendices,
        image_appendices=image_appendices,
    )


def normalize_pdf_text(value: str) -> str:
    return re.sub(r"\s+", "", str(value or "")).lower()


def build_pdf_outline_entries(model: dict, commands: list) -> list[dict]:
    rendered_items = collect_render_items(model, commands)
    code_appendices = load_code_appendices(model)
    image_appendices = load_image_appendices(model)
    command_items = [item for item in rendered_items if not is_error_code_item(item)]
    has_error_code = any(is_error_code_item(item) for item in rendered_items)

    entries = [
        {"title": model.get("document_title", model.get("model_name", "Document")), "level": 1, "marker": "__PDF_BM_COVER__"},
        {"title": "文档说明", "level": 1, "marker": "__PDF_BM_FRONT_MATTER__"},
        {"title": "修改记录", "level": 1, "marker": "__PDF_BM_REVISION_HISTORY__"},
        {"title": "目录", "level": 1, "marker": "__PDF_BM_TOC__"},
        {"title": "1. 通信端口配置", "level": 1, "marker": "__PDF_BM_COMMUNICATION__"},
        {"title": "2. 支持指令列表", "level": 1, "marker": "__PDF_BM_COMMAND_LIST__"},
        {"title": "3. 指令详细说明", "level": 1, "marker": "__PDF_BM_COMMAND_DETAILS__"},
    ]

    for index, item in enumerate(command_items, 1):
        title = f"3.{index} {item['display_id']} {item['name']}"
        entries.append({"title": title, "level": 2, "marker": f"__PDF_BM_CMD_{index}__"})

    if has_error_code or image_appendices or code_appendices:
        entries.append({"title": "附录", "level": 1, "marker": "__PDF_BM_APPENDIX__"})
    if has_error_code:
        entries.append({"title": "A.1 错误码说明", "level": 2, "marker": "__PDF_BM_ERROR_CODES__"})
    if image_appendices:
        entries.append({"title": "A.2 流程图", "level": 2, "marker": "__PDF_BM_IMAGE_APPENDICES__"})
        for index, appendix in enumerate(image_appendices, 1):
            entries.append({"title": f"A.2.{index} {appendix['title']}", "level": 3, "marker": f"__PDF_BM_IMAGE_{index}__"})
    if code_appendices:
        code_no = "A.3" if image_appendices else "A.2"
        entries.append({"title": f"{code_no} 参考代码", "level": 2, "marker": "__PDF_BM_REFERENCE_CODE__"})
        for index, appendix in enumerate(code_appendices, 1):
            title = f"{code_no}.{index} {appendix['title']}"
            entries.append({"title": title, "level": 3, "marker": f"__PDF_BM_CODE_{index}__"})

    return entries


def find_outline_page(entry: dict, page_texts: list[str], start_page: int) -> int | None:
    marker = normalize_pdf_text(entry.get("marker", ""))
    if marker:
        for page_index, page_text in enumerate(page_texts):
            if marker in page_text:
                return page_index

    title = normalize_pdf_text(entry.get("title", ""))
    if title:
        for page_index in range(start_page, len(page_texts)):
            if title in page_texts[page_index]:
                return page_index
    return None


def clone_pdf_writer(reader, pdf_path):
    """Clone the whole PDF document so Chromium-created link annotations are preserved."""
    try:
        from pypdf import PdfWriter
        return PdfWriter(clone_from=str(pdf_path))
    except TypeError:
        from pypdf import PdfWriter
        writer = PdfWriter()
        if hasattr(writer, "clone_document_from_reader"):
            writer.clone_document_from_reader(reader)
        elif hasattr(writer, "clone_reader_document_root"):
            writer.clone_reader_document_root(reader)
        else:
            # Last-resort fallback for very old pypdf versions. This may lose link annotations.
            writer.append_pages_from_reader(reader)
        return writer


def add_pdf_bookmarks(pdf_path, outline_entries: list[dict]) -> None:
    try:
        from pypdf import PdfReader
        from pypdf.generic import NameObject
    except ImportError as exc:
        raise RuntimeError("PDF bookmark export requires pypdf. Run: pip install -r requirements.txt") from exc

    if not outline_entries:
        return

    reader = PdfReader(str(pdf_path))
    page_texts = [normalize_pdf_text(page.extract_text() or "") for page in reader.pages]

    writer = clone_pdf_writer(reader, pdf_path)
    writer._root_object.update({NameObject("/PageMode"): NameObject("/UseOutlines")})

    page_count = len(reader.pages)
    parents = {}
    last_page = 0

    for entry in outline_entries:
        title = str(entry.get("title") or "").strip()
        if not title:
            continue

        resolved_page = find_outline_page(entry, page_texts, last_page)
        if resolved_page is None:
            resolved_page = last_page
        resolved_page = max(0, min(resolved_page, page_count - 1))
        last_page = resolved_page

        level = int(entry.get("level") or 1)
        parent = parents.get(level - 1)
        try:
            bookmark = writer.add_outline_item(title, resolved_page, parent=parent)
        except TypeError:
            bookmark = writer.addBookmark(title, resolved_page, parent=parent)
        parents[level] = bookmark
        for deeper_level in list(parents):
            if deeper_level > level:
                parents.pop(deeper_level, None)

    tmp_path = pdf_path.with_suffix(".bookmarked.tmp.pdf")
    with tmp_path.open("wb") as f:
        writer.write(f)
    tmp_path.replace(pdf_path)


def render_pdf(html_path, pdf_path, outline_entries: list[dict]):
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise RuntimeError("PDF export requires playwright. Run: pip install playwright && playwright install chromium") from exc

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": A4_VIEWPORT_WIDTH_CSS_PX, "height": A4_VIEWPORT_HEIGHT_CSS_PX})
        page.emulate_media(media="print")
        page.goto(html_path.as_uri(), wait_until="networkidle")
        page.pdf(
            path=str(pdf_path),
            format="A4",
            print_background=True,
            outline=False,
        )
        browser.close()

    add_pdf_bookmarks(pdf_path, outline_entries)


def build_model(model_id: str, fmt: str) -> None:
    model = load_model_profile(model_id)
    commands = get_commands_for_model(model, load_command_specs())

    output_dir = ROOT / "output"
    output_dir.mkdir(exist_ok=True)
    base_name = f"{model['model_name']}_AT_Command_{model['version']}"

    if fmt == "md":
        out_path = output_dir / f"{base_name}.md"
        write_text(out_path, render_markdown(model, commands))
        print(f"Generated: {out_path}")
        return

    if fmt in ["html", "pdf"]:
        image_appendices = load_image_appendices(model)
        copy_image_assets(image_appendices, output_dir)
        out_path = output_dir / f"{base_name}.html"
        write_text(out_path, render_html(model, commands))
        shutil.copyfile(toolkit_path("templates", "style.css"), output_dir / "style.css")
        print(f"Generated: {out_path}")
        if fmt == "pdf":
            pdf_path = output_dir / f"{base_name}.pdf"
            render_pdf(out_path.resolve(), pdf_path, build_pdf_outline_entries(model, commands))
            print(f"Generated: {pdf_path}")
        return

    raise ValueError(f"Unsupported format: {fmt}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True, help="model id, e.g. rsc, dp5x, u100")
    parser.add_argument("--format", default="md", choices=["md", "html", "pdf"], help="output format")
    args = parser.parse_args()
    build_model(args.model, args.format)


if __name__ == "__main__":
    main()
