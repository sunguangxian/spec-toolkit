from __future__ import annotations

from typing import Any, Dict, Iterable, List

from .core import get_localized


def _same_version(left: Any, right: Any) -> bool:
    return str(left or '').strip().lower() == str(right or '').strip().lower()


def _as_list(value: Any, language: str) -> List[str]:
    if value in [None, '']:
        return []
    if isinstance(value, dict):
        text = get_localized(value, language)
        return [str(text).strip()] if str(text).strip() else []
    if isinstance(value, list):
        result: List[str] = []
        for item in value:
            result.extend(_as_list(item, language))
        return result
    text = str(value).strip()
    return [text] if text else []


def _manual_entry(item: Dict[str, Any], model: Dict[str, Any], generated_date: str, language: str) -> Dict[str, Any]:
    changes = _as_list(item.get('changes'), language)
    if not changes:
        changes = _as_list(item.get('description') or item.get('change') or item.get('summary'), language)
    return {
        'version': item.get('version') or model.get('version') or '',
        'date': item.get('date') or item.get('release_date') or generated_date,
        'changes': changes or (['当前版本发布。'] if language == 'zh' else ['Current release.']),
        'source': 'manual',
    }


def _changed_item_visible(item: Dict[str, Any]) -> bool:
    if item.get('internal') is True:
        return False
    if item.get('customer') is False:
        return False
    if str(item.get('visibility', '')).lower() == 'internal':
        return False
    return True


def _append_unique(target: List[str], seen: set[str], value: str) -> None:
    key = value.strip()
    if key and key not in seen:
        seen.add(key)
        target.append(key)


def _auto_changes_from_commands(model: Dict[str, Any], rendered_items: Iterable[Dict[str, Any]], language: str) -> List[str]:
    version = model.get('version')
    changes: List[str] = []
    seen: set[str] = set()

    for rendered in rendered_items:
        command = rendered.get('command') or {}
        if command.get('category') == 'Error Code':
            continue
        display_id = rendered.get('display_id') or command.get('display_id') or command.get('id') or ''
        for item in command.get('changed', []) or []:
            if not isinstance(item, dict):
                continue
            if not _same_version(item.get('version'), version):
                continue
            if not _changed_item_visible(item):
                continue
            descriptions = _as_list(item.get('description') or item.get('changes'), language)
            for description in descriptions:
                if display_id:
                    _append_unique(changes, seen, f'{display_id}: {description}')
                else:
                    _append_unique(changes, seen, description)

    return changes


def collect_revision_history(
    model: Dict[str, Any],
    rendered_items: Iterable[Dict[str, Any]],
    generated_date: str,
    language: str,
) -> List[Dict[str, Any]]:
    """Build customer-facing revision history.

    Priority:
    1. models/<model>.yaml revision_history, maintained by users.
    2. command YAML changed entries for the current model version.
    3. A single default current-release row.

    Git commits, scripts, templates, README, CI and other tool maintenance changes
    are intentionally not used here.
    """
    manual_items = model.get('revision_history') or []
    if manual_items:
        return [
            _manual_entry(item, model, generated_date, language)
            for item in manual_items
            if isinstance(item, dict)
        ]

    auto_changes = _auto_changes_from_commands(model, rendered_items, language)
    if auto_changes:
        return [{
            'version': model.get('version') or '',
            'date': generated_date,
            'changes': auto_changes,
            'source': 'auto-command-changed',
        }]

    return [{
        'version': model.get('version') or '',
        'date': generated_date,
        'changes': ['当前版本发布。'] if language == 'zh' else ['Current release.'],
        'source': 'auto-default',
    }]
