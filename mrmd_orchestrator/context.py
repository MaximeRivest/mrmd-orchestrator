"""Context-as-markdown resolver for AI commands."""

from __future__ import annotations

import math
import mimetypes
import os
import re
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
import html

import httpx

DOC_SUFFIXES = {".md", ".qmd"}
DEFAULT_CONTEXT_TEMPLATE = """# Context Configuration

<!-- This file controls what context is sent to AI commands. -->
<!-- Edit it directly or use the Context panel in the editor. -->
<!-- AI agents can also modify this file to adjust their own context. -->

## Document
<!-- context:document mode=\"full\" -->

## Linked Pages
<!-- context:links depth=\"1\" -->

## Images
<!-- context:images -->

## Runtime State
<!-- context:runtime -->
<!-- context:runtime-variables -->
<!-- context:runtime-docstrings symbols=\"auto\" -->

## Pinned Files
<!-- context:files -->

## Notes

(Add project conventions, domain knowledge, or constraints here.)
"""

DIRECTIVE_RE = re.compile(r"<!--\s*context:([a-zA-Z0-9_-]+)(.*?)-->")
ATTR_RE = re.compile(r"([a-zA-Z0-9_-]+)=\"([^\"]*)\"|([a-zA-Z0-9_-]+)=([^\s]+)")
LIST_ITEM_RE = re.compile(r"^\s*[-*+]\s+(.*?)(?:\s+<!--\s*(enabled|disabled).*?-->)?\s*$")
HEADING_RE = re.compile(r"^(#+)\s+(.*)$")
WIKI_LINK_RE = re.compile(r"\[\[([^\]|#]+)(?:#[^\]|]+)?(?:\|[^\]]+)?\]\]")
MD_LINK_RE = re.compile(r"(?<!\!)\[([^\]]+)\]\(([^)]+)\)")
IMAGE_RE = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")
HTML_TAG_RE = re.compile(r"<[^>]+>")
SCRIPT_STYLE_RE = re.compile(r"<(script|style)[^>]*>.*?</\1>", re.IGNORECASE | re.DOTALL)
CODE_BLOCK_RE = re.compile(r"```([a-zA-Z0-9_-]*)\n([\s\S]*?)```", re.MULTILINE)
IDENT_RE = re.compile(r"\b[A-Za-z_][A-Za-z0-9_]*\b")
PY_DEF_RE = re.compile(r"^\s*(?:def|class)\s+([A-Za-z_][A-Za-z0-9_]*)", re.MULTILINE)
PY_ASSIGN_RE = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=", re.MULTILINE)
PY_FROM_IMPORT_RE = re.compile(r"^\s*from\s+[A-Za-z0-9_\.]+\s+import\s+(.+)$", re.MULTILINE)
PY_IMPORT_RE = re.compile(r"^\s*import\s+(.+)$", re.MULTILINE)


def estimate_tokens(text: str | None) -> int:
    if not text:
        return 0
    return max(1, math.ceil(len(text) / 4))


def normalize_doc_name(doc_name: str) -> str:
    name = doc_name.strip().lstrip("/")
    if not name:
        raise ValueError("Document name is required")
    path = Path(name)
    if any(part in {"", ".", ".."} for part in path.parts):
        raise ValueError(f"Invalid document name: {doc_name}")
    normalized = str(path)
    lower = normalized.lower()
    if any(lower.endswith(suffix) for suffix in DOC_SUFFIXES):
        return normalized
    return f"{normalized}.md"


def context_relpath_for_doc(doc_name: str) -> Path:
    return Path("_assets") / "context" / normalize_doc_name(doc_name)


def context_relpath_default() -> Path:
    return Path("_assets") / "context" / "_default.md"


def context_path_for_doc(docs_dir: Path, doc_name: str) -> Path:
    return docs_dir / context_relpath_for_doc(doc_name)


def context_path_default(docs_dir: Path) -> Path:
    return docs_dir / context_relpath_default()


def parse_attrs(raw: str) -> dict[str, str]:
    attrs: dict[str, str] = {}
    for match in ATTR_RE.finditer(raw or ""):
        key = match.group(1) or match.group(3)
        value = match.group(2) or match.group(4) or ""
        if key:
            attrs[key] = value
    return attrs


def heading_key(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", title.strip().lower()).strip("-")


def section_type_for_heading(section: str | None) -> str | None:
    mapping = {
        "linked-pages": "links",
        "links": "links",
        "images": "images",
        "pinned-files": "files",
        "files": "files",
        "web-pages": "urls",
        "urls": "urls",
        "notes": "notes",
        "docstrings": "runtime-docstrings",
        "source-code": "runtime-source",
        "source-paths": "runtime-paths",
    }
    return mapping.get(section or "")


def parse_enabled(line: str, default: bool = True) -> bool:
    if "<!--" not in line:
        return default
    if "disabled" in line:
        return False
    if "enabled" in line:
        return True
    return default


def parse_boolish(value: Any, default: bool = True) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "on", "enabled"}:
        return True
    if text in {"0", "false", "no", "off", "disabled"}:
        return False
    return default


def clean_item_text(text: str) -> str:
    text = re.sub(r"\s*<!--.*?-->\s*$", "", text).strip()
    if text.startswith("`") and text.endswith("`") and len(text) >= 2:
        return text[1:-1]
    return text.strip()


def parse_context_markdown(content: str) -> dict[str, Any]:
    config: dict[str, Any] = {
        "document": {"enabled": False, "mode": "full", "budget": None},
        "links": {"enabled": False, "depth": 0, "items": []},
        "images": {"enabled": False, "items": []},
        "runtime": {"enabled": False},
        "runtime-variables": {"enabled": False},
        "runtime-docstrings": {"enabled": False, "symbols": "auto", "items": []},
        "runtime-source": {"enabled": False, "symbols": None, "items": []},
        "runtime-paths": {"enabled": False, "items": []},
        "files": {"enabled": False, "items": []},
        "urls": {"enabled": False, "items": [], "max-size": "50kb"},
        "notes": {"enabled": True, "content": ""},
    }

    current_section: str | None = None
    current_target_type: str | None = None
    notes_lines: list[str] = []

    for raw_line in content.splitlines():
        heading_match = HEADING_RE.match(raw_line)
        if heading_match:
            current_section = heading_key(heading_match.group(2))
            mapped = section_type_for_heading(current_section)
            current_target_type = mapped
            continue

        directive_match = DIRECTIVE_RE.search(raw_line)
        if directive_match:
            dtype = directive_match.group(1).strip().lower()
            attrs = parse_attrs(directive_match.group(2))
            entry = config.setdefault(dtype, {"enabled": False})
            entry.update(attrs)
            entry["enabled"] = parse_boolish(entry.get("enabled"), True)
            current_target_type = dtype
            continue

        item_match = LIST_ITEM_RE.match(raw_line)
        if item_match:
            target_type = current_target_type or section_type_for_heading(current_section)
            item_text = clean_item_text(item_match.group(1))
            if target_type and item_text:
                item = {"value": item_text, "enabled": parse_enabled(raw_line)}
                config.setdefault(target_type, {"enabled": False, "items": []})
                config[target_type].setdefault("items", []).append(item)
            continue

        if current_section == "notes":
            if raw_line.strip().startswith("<!--") and raw_line.strip().endswith("-->"):
                continue
            notes_lines.append(raw_line)

    config["document"]["enabled"] = bool(config["document"].get("enabled"))
    config["document"]["mode"] = str(config["document"].get("mode") or "full")
    budget = config["document"].get("budget")
    try:
        config["document"]["budget"] = int(budget) if budget is not None else None
    except Exception:
        config["document"]["budget"] = None

    depth = config["links"].get("depth")
    try:
        config["links"]["depth"] = int(depth) if depth is not None else 0
    except Exception:
        config["links"]["depth"] = 0

    notes_content = "\n".join(notes_lines).strip()
    if notes_content == "(Add project conventions, domain knowledge, or constraints here.)":
        notes_content = ""
    config["notes"]["content"] = notes_content
    return config


def load_context_markdown(docs_dir: Path, doc_name: str, ensure_exists: bool = False) -> tuple[str, Path, bool, str]:
    doc_path = context_path_for_doc(docs_dir, doc_name)
    default_path = context_path_default(docs_dir)

    if doc_path.exists():
        return doc_path.read_text(encoding="utf-8"), doc_path, False, "document"
    if default_path.exists():
        return default_path.read_text(encoding="utf-8"), default_path, True, "default"
    if ensure_exists:
        doc_path.parent.mkdir(parents=True, exist_ok=True)
        doc_path.write_text(DEFAULT_CONTEXT_TEMPLATE, encoding="utf-8")
        return DEFAULT_CONTEXT_TEMPLATE, doc_path, False, "created"
    return DEFAULT_CONTEXT_TEMPLATE, doc_path, False, "builtin"


def resolve_doc_disk_path(docs_dir: Path, doc_name: str) -> Path:
    return docs_dir / normalize_doc_name(doc_name)


def read_doc_content_from_disk(docs_dir: Path, doc_name: str) -> str:
    path = resolve_doc_disk_path(docs_dir, doc_name)
    if path.exists():
        return path.read_text(encoding="utf-8")
    return ""


def slice_around(content: str, cursor_pos: int | None = None, window_chars: int = 2000) -> str:
    if not content:
        return ""
    if cursor_pos is None or cursor_pos < 0 or cursor_pos > len(content):
        return content[:window_chars]
    half = max(200, window_chars // 2)
    start = max(0, cursor_pos - half)
    end = min(len(content), cursor_pos + half)
    return content[start:end]


def extract_outline(content: str, max_level: int = 3) -> str:
    lines = []
    for line in content.splitlines():
        match = HEADING_RE.match(line)
        if match and len(match.group(1)) <= max_level:
            lines.append(line)
    return "\n".join(lines).strip()


def resolve_document_block(content: str, mode: str, budget: int | None, cursor_pos: int | None) -> str:
    mode = (mode or "full").lower()
    if mode == "local":
        return slice_around(content, cursor_pos, window_chars=2500)
    if mode == "outline+local":
        outline = extract_outline(content)
        local = slice_around(content, cursor_pos, window_chars=2500)
        if outline and local:
            return f"## Outline\n{outline}\n\n## Local Context\n{local}"
        return outline or local
    if mode == "budget":
        char_budget = max(800, (budget or 2000) * 4)
        return slice_around(content, cursor_pos, window_chars=char_budget)
    if budget and len(content) > budget * 4:
        return slice_around(content, cursor_pos, window_chars=budget * 4)
    return content


def is_probably_markdown_ref(ref: str) -> bool:
    ref = ref.strip()
    if not ref or ref.startswith("#"):
        return False
    if ref.startswith("http://") or ref.startswith("https://"):
        return False
    suffix = Path(ref.split("#", 1)[0]).suffix.lower()
    if suffix in {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".pdf"}:
        return False
    return suffix in DOC_SUFFIXES or suffix == ""


def extract_markdown_links(content: str) -> list[dict[str, str]]:
    refs: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()

    for match in WIKI_LINK_RE.finditer(content or ""):
        target = match.group(1).strip()
        key = ("wiki", target)
        if target and key not in seen:
            seen.add(key)
            refs.append({"type": "wiki", "target": target})

    for match in MD_LINK_RE.finditer(content or ""):
        target = match.group(2).strip()
        if not is_probably_markdown_ref(target):
            continue
        key = ("markdown", target)
        if key not in seen:
            seen.add(key)
            refs.append({"type": "markdown", "target": target})

    return refs


def build_doc_index(docs_dir: Path) -> dict[str, list[Path]]:
    index: dict[str, list[Path]] = {}
    for path in docs_dir.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in DOC_SUFFIXES:
            continue
        rel_parts = path.relative_to(docs_dir).parts
        if any(part.startswith(".") or part.startswith("_") for part in rel_parts):
            continue
        index.setdefault(path.stem.lower(), []).append(path)
    return index


def resolve_link_target(
    docs_dir: Path,
    doc_index: dict[str, list[Path]],
    current_doc_path: Path,
    ref: dict[str, str],
) -> Path | None:
    target = ref.get("target", "").strip()
    if not target:
        return None

    if ref.get("type") == "wiki":
        candidates = doc_index.get(target.lower(), [])
        if len(candidates) == 1:
            return candidates[0]
        if len(candidates) > 1:
            current_parent = current_doc_path.parent
            for candidate in candidates:
                if candidate.parent == current_parent:
                    return candidate
            return candidates[0]
        return None

    parsed = target.split("#", 1)[0]
    if parsed.startswith("/"):
        path = docs_dir / parsed.lstrip("/")
    else:
        path = current_doc_path.parent / parsed
    if path.suffix.lower() not in DOC_SUFFIXES:
        path = path.with_suffix(".md")
    try:
        resolved = path.resolve()
        resolved.relative_to(docs_dir.resolve())
    except Exception:
        return None
    return resolved if resolved.exists() else None


def current_doc_path_for_name(docs_dir: Path, doc_name: str) -> Path:
    return (docs_dir / normalize_doc_name(doc_name)).resolve()


def parse_image_refs(content: str) -> list[dict[str, str]]:
    refs = []
    seen: set[str] = set()
    for match in IMAGE_RE.finditer(content or ""):
        alt = match.group(1).strip()
        src = match.group(2).strip()
        if src and src not in seen:
            seen.add(src)
            refs.append({"alt": alt, "src": src})
    return refs


def resolve_local_image(doc_path: Path, docs_dir: Path, src: str) -> Path | None:
    if src.startswith("http://") or src.startswith("https://") or src.startswith("data:"):
        return None
    base = src.split("#", 1)[0]
    candidate = (doc_path.parent / base).resolve()
    try:
        candidate.relative_to(docs_dir.resolve())
    except Exception:
        return None
    return candidate if candidate.exists() else None


def parse_size_limit(value: str | None, default_kb: int = 50) -> int:
    if not value:
        return default_kb * 1024
    value = str(value).strip().lower()
    try:
        if value.endswith("kb"):
            return int(float(value[:-2]) * 1024)
        if value.endswith("mb"):
            return int(float(value[:-2]) * 1024 * 1024)
        return int(value)
    except Exception:
        return default_kb * 1024


def html_to_text(content: str) -> str:
    content = SCRIPT_STYLE_RE.sub("", content or "")
    content = HTML_TAG_RE.sub(" ", content)
    content = html.unescape(content)
    content = re.sub(r"\s+", " ", content).strip()
    return content


def parse_symbol_list(raw: str | None) -> list[str]:
    if not raw:
        return []
    values = []
    for part in str(raw).split(","):
        value = clean_item_text(part.strip())
        if value:
            values.append(value)
    return values


def extract_python_symbols(content: str, limit: int = 20) -> list[str]:
    symbols: list[str] = []
    seen: set[str] = set()

    def add(symbol: str):
        if symbol and symbol not in seen and symbol not in {"print", "len", "range", "str", "int", "float", "list", "dict", "set"}:
            seen.add(symbol)
            symbols.append(symbol)

    for match in CODE_BLOCK_RE.finditer(content or ""):
        lang = (match.group(1) or "").strip().lower()
        if lang not in {"", "python", "py"}:
            continue
        code = match.group(2)
        for name in PY_DEF_RE.findall(code):
            add(name)
        for name in PY_ASSIGN_RE.findall(code):
            add(name)
        for group in PY_FROM_IMPORT_RE.findall(code):
            for part in group.split(","):
                token = part.strip().split(" as ")[-1].strip()
                if token and token != "*":
                    add(token)
        for group in PY_IMPORT_RE.findall(code):
            for part in group.split(","):
                token = part.strip().split(" as ")[-1].split(".")[0].strip()
                if token:
                    add(token)
        for name in IDENT_RE.findall(code):
            if "(" in code[code.find(name):code.find(name) + len(name) + 2]:
                add(name)
        if len(symbols) >= limit:
            break

    return symbols[:limit]


async def inspect_runtime_symbol(runtime_url: str, symbol: str, detail: int = 1) -> dict[str, Any] | None:
    async with httpx.AsyncClient(timeout=5.0) as client:
        response = await client.post(f"{runtime_url}/inspect", json={"code": symbol, "cursor": len(symbol), "detail": detail})
        response.raise_for_status()
        data = response.json()
        return data if data.get("found") else None


async def fetch_runtime_variables(runtime_url: str) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=5.0) as client:
        response = await client.post(f"{runtime_url}/variables", json={})
        response.raise_for_status()
        return response.json()


async def fetch_url_text(url: str, max_bytes: int) -> tuple[str | None, dict[str, Any] | None]:
    async with httpx.AsyncClient(timeout=6.0, follow_redirects=True) as client:
        response = await client.get(url)
        response.raise_for_status()
        content_type = response.headers.get("content-type", "")
        raw = response.text
        if len(raw.encode("utf-8")) > max_bytes:
            raw = raw.encode("utf-8")[:max_bytes].decode("utf-8", errors="ignore")
        text = html_to_text(raw) if "html" in content_type else raw
        return text[:max_bytes], {
            "url": str(response.url),
            "content_type": content_type,
            "title": None,
        }


async def resolve_context(
    orchestrator: Any,
    doc_name: str,
    current_content: str | None = None,
    cursor_pos: int | None = None,
    selection: dict[str, int] | None = None,
    code_symbols: list[str] | None = None,
    ensure_exists: bool = False,
) -> dict[str, Any]:
    docs_dir = Path(orchestrator.config.sync.docs_dir).resolve()
    project_root = docs_dir.parent

    markdown, context_file_path, using_default, source_kind = load_context_markdown(docs_dir, doc_name, ensure_exists=ensure_exists)
    config = parse_context_markdown(markdown)

    current_doc_content = current_content if current_content is not None else read_doc_content_from_disk(docs_dir, doc_name)
    current_doc_path = current_doc_path_for_name(docs_dir, doc_name)

    blocks: list[str] = []
    sources: list[dict[str, Any]] = []
    images: list[dict[str, Any]] = []

    # Document
    if config["document"].get("enabled"):
        doc_block = resolve_document_block(
            current_doc_content,
            config["document"].get("mode", "full"),
            config["document"].get("budget"),
            cursor_pos,
        )
        if doc_block:
            blocks.append(f"=== DOCUMENT ===\n{doc_block}")
            sources.append({
                "type": "document",
                "mode": config["document"].get("mode", "full"),
                "tokens": estimate_tokens(doc_block),
                "enabled": True,
            })

    # Linked pages
    if config["links"].get("enabled"):
        doc_index = build_doc_index(docs_dir)
        depth = max(0, int(config["links"].get("depth", 0)))
        explicit_items = [item for item in config["links"].get("items", []) if item.get("enabled", True)]
        queue: list[tuple[int, Path, dict[str, str]]] = []
        visited: set[Path] = set()

        if explicit_items:
            for item in explicit_items:
                value = item["value"].strip()
                if value.startswith("[[") and value.endswith("]]"):
                    queue.append((1, current_doc_path, {"type": "wiki", "target": value[2:-2]}))
                else:
                    queue.append((1, current_doc_path, {"type": "markdown", "target": value}))
        elif depth > 0:
            for ref in extract_markdown_links(current_doc_content):
                queue.append((1, current_doc_path, ref))

        while queue:
            ref_depth, base_doc_path, ref = queue.pop(0)
            if ref_depth > depth:
                continue
            resolved = resolve_link_target(docs_dir, doc_index, base_doc_path, ref)
            if not resolved or resolved in visited:
                continue
            visited.add(resolved)

            try:
                linked_content = resolved.read_text(encoding="utf-8")
            except Exception:
                continue

            rel_path = str(resolved.relative_to(docs_dir))
            blocks.append(f"=== LINKED PAGE: {resolved.stem} ({rel_path}) ===\n{linked_content}")
            sources.append({
                "type": "linked-page",
                "name": resolved.stem,
                "path": rel_path,
                "depth": ref_depth,
                "tokens": estimate_tokens(linked_content),
                "enabled": True,
            })

            if ref_depth < depth:
                for child_ref in extract_markdown_links(linked_content):
                    queue.append((ref_depth + 1, resolved, child_ref))

    # Images (text summary only for now)
    if config["images"].get("enabled"):
        explicit_images = [item for item in config["images"].get("items", []) if item.get("enabled", True)]
        refs = []
        if explicit_images:
            for item in explicit_images:
                refs.append({"alt": "", "src": item["value"]})
        else:
            refs = parse_image_refs(current_doc_content)

        image_lines = []
        for ref in refs:
            src = ref["src"]
            local_path = resolve_local_image(current_doc_path, docs_dir, src)
            if local_path and local_path.exists():
                size = local_path.stat().st_size
                mime = mimetypes.guess_type(local_path.name)[0] or "application/octet-stream"
                rel = str(local_path.relative_to(docs_dir))
                image_lines.append(f"- {src} | local={rel} | mime={mime} | size={size} bytes")
                images.append({
                    "src": src,
                    "alt": ref.get("alt", ""),
                    "path": rel,
                    "mimeType": mime,
                    "sizeBytes": size,
                    "origin": "local",
                })
            else:
                image_lines.append(f"- {src} | external")
                images.append({
                    "src": src,
                    "alt": ref.get("alt", ""),
                    "path": src,
                    "mimeType": None,
                    "sizeBytes": None,
                    "origin": "external",
                })
        if image_lines:
            block = "Images referenced in the document:\n" + "\n".join(image_lines)
            blocks.append(f"=== IMAGES ===\n{block}")
            sources.append({
                "type": "images",
                "count": len(image_lines),
                "tokens": estimate_tokens(block),
                "enabled": True,
            })

    # Runtime state
    if config["runtime"].get("enabled"):
        session = orchestrator.get_session_info(doc_name)
        python_runtime = (session or {}).get("runtimes", {}).get("python", {}) if session else {}
        runtime_url = python_runtime.get("url")
        runtime_port = python_runtime.get("port")
        runtime_sections = []
        runtime_source_info = {
            "type": "runtime",
            "enabled": True,
            "runtimeUrl": runtime_url,
            "runtimePort": runtime_port,
            "available": bool(runtime_url),
        }

        if runtime_url:
            try:
                if config["runtime-variables"].get("enabled"):
                    variables = await fetch_runtime_variables(runtime_url)
                    items = variables.get("variables", [])[:30]
                    lines = []
                    for var in items:
                        size_bits = []
                        if var.get("shape"):
                            size_bits.append(f"shape={var['shape']}")
                        if var.get("dtype"):
                            size_bits.append(f"dtype={var['dtype']}")
                        if var.get("size"):
                            size_bits.append(var["size"])
                        meta = f" ({', '.join(size_bits)})" if size_bits else ""
                        lines.append(f"- {var.get('name')}: {var.get('type')} = {var.get('value')}{meta}")
                    if lines:
                        runtime_sections.append("## Variables\n" + "\n".join(lines))
                        sources.append({
                            "type": "runtime-variables",
                            "count": len(lines),
                            "tokens": estimate_tokens("\n".join(lines)),
                            "enabled": True,
                        })
            except Exception as exc:
                runtime_sections.append(f"## Variables\n- Failed to fetch runtime variables: {exc}")

            explicit_docstring_symbols = [item["value"] for item in config["runtime-docstrings"].get("items", []) if item.get("enabled", True)]
            explicit_source_symbols = [item["value"] for item in config["runtime-source"].get("items", []) if item.get("enabled", True)]
            explicit_path_symbols = [item["value"] for item in config["runtime-paths"].get("items", []) if item.get("enabled", True)]

            auto_symbols = code_symbols or extract_python_symbols(current_doc_content)
            doc_symbols = explicit_docstring_symbols or parse_symbol_list(config["runtime-docstrings"].get("symbols"))
            source_symbols = explicit_source_symbols or parse_symbol_list(config["runtime-source"].get("symbols"))
            path_symbols = explicit_path_symbols

            if config["runtime-docstrings"].get("enabled") and (not doc_symbols or doc_symbols == ["auto"]):
                doc_symbols = auto_symbols
            if config["runtime-source"].get("enabled") and (not source_symbols or source_symbols == ["auto"]):
                source_symbols = auto_symbols
            if config["runtime-paths"].get("enabled") and not path_symbols:
                path_symbols = auto_symbols

            symbols_to_inspect = []
            for symbol in doc_symbols + source_symbols + path_symbols:
                if symbol and symbol not in symbols_to_inspect:
                    symbols_to_inspect.append(symbol)
                if len(symbols_to_inspect) >= 20:
                    break

            inspections: dict[str, dict[str, Any]] = {}
            if symbols_to_inspect:
                detail = 2 if config["runtime-source"].get("enabled") else 1
                for symbol in symbols_to_inspect:
                    try:
                        result = await inspect_runtime_symbol(runtime_url, symbol, detail=detail)
                        if result:
                            inspections[symbol] = result
                    except Exception:
                        continue

            if config["runtime-docstrings"].get("enabled"):
                lines = []
                for symbol in doc_symbols:
                    info = inspections.get(symbol)
                    if not info:
                        continue
                    signature = info.get("signature") or ""
                    docstring = (info.get("docstring") or "").strip()
                    file_hint = info.get("file")
                    if len(docstring) > 500:
                        docstring = docstring[:500].rstrip() + "…"
                    line = f"- {symbol}{signature and f' {signature}'}"
                    if docstring:
                        line += f"\n  {docstring}"
                    if file_hint:
                        line += f"\n  File: {file_hint}"
                    lines.append(line)
                if lines:
                    runtime_sections.append("## Docstrings\n" + "\n".join(lines))
                    sources.append({
                        "type": "runtime-docstrings",
                        "count": len(lines),
                        "tokens": estimate_tokens("\n".join(lines)),
                        "enabled": True,
                    })

            if config["runtime-paths"].get("enabled"):
                lines = []
                for symbol in path_symbols:
                    info = inspections.get(symbol)
                    if not info or not info.get("file"):
                        continue
                    line = f"- {symbol}: {info['file']}"
                    if info.get("line") is not None:
                        line += f":{info['line']}"
                    lines.append(line)
                if lines:
                    runtime_sections.append("## Source Paths\n" + "\n".join(lines))
                    sources.append({
                        "type": "runtime-paths",
                        "count": len(lines),
                        "tokens": estimate_tokens("\n".join(lines)),
                        "enabled": True,
                    })

            if config["runtime-source"].get("enabled"):
                chunks = []
                count = 0
                for symbol in source_symbols:
                    info = inspections.get(symbol)
                    source_code = (info or {}).get("sourceCode")
                    if not source_code:
                        continue
                    chunks.append(f"### {symbol}\n```python\n{source_code}\n```")
                    count += 1
                    if count >= 5:
                        break
                if chunks:
                    runtime_sections.append("## Source Code\n" + "\n\n".join(chunks))
                    sources.append({
                        "type": "runtime-source",
                        "count": count,
                        "tokens": estimate_tokens("\n\n".join(chunks)),
                        "enabled": True,
                    })
        else:
            runtime_sections.append("No Python runtime attached to this document.")

        if runtime_sections:
            runtime_header = ["=== RUNTIME STATE ==="]
            if runtime_url:
                runtime_header.append(f"Runtime URL: {runtime_url}")
                if runtime_port is not None:
                    runtime_header.append(f"Runtime Port: {runtime_port}")
            blocks.append("\n".join(runtime_header) + "\n\n" + "\n\n".join(runtime_sections))
            sources.append(runtime_source_info)

    # Pinned files
    if config["files"].get("enabled"):
        file_items = [item for item in config["files"].get("items", []) if item.get("enabled", True)]
        file_chunks = []
        for item in file_items[:10]:
            raw_path = item["value"]
            path = Path(raw_path).expanduser()
            if not path.is_absolute():
                path = (project_root / path).resolve()
            try:
                text = path.read_text(encoding="utf-8")
            except Exception:
                continue
            rel = os.path.relpath(path, project_root)
            suffix = path.suffix.lstrip(".") or "text"
            trimmed = text[:12000]
            file_chunks.append(f"=== FILE: {rel} ===\n```{suffix}\n{trimmed}\n```")
            sources.append({
                "type": "file",
                "path": rel,
                "tokens": estimate_tokens(trimmed),
                "enabled": True,
            })
        blocks.extend(file_chunks)

    # URLs
    if config["urls"].get("enabled"):
        url_items = [item for item in config["urls"].get("items", []) if item.get("enabled", True)]
        max_bytes = parse_size_limit(config["urls"].get("max-size"))
        for item in url_items[:5]:
            url = item["value"]
            parsed = urlparse(url)
            if parsed.scheme not in {"http", "https"}:
                continue
            try:
                text, meta = await fetch_url_text(url, max_bytes=max_bytes)
            except Exception:
                continue
            if not text:
                continue
            blocks.append(f"=== WEB PAGE: {url} ===\n{text}")
            sources.append({
                "type": "url",
                "url": url,
                "tokens": estimate_tokens(text),
                "enabled": True,
            })

    # Notes
    notes_content = config["notes"].get("content", "").strip()
    if notes_content:
        blocks.append(f"=== NOTES ===\n{notes_content}")
        sources.append({
            "type": "notes",
            "tokens": estimate_tokens(notes_content),
            "enabled": True,
        })

    context_text = "\n\n".join(block for block in blocks if block).strip()
    token_estimate = sum(source.get("tokens", 0) for source in sources)

    return {
        "doc": doc_name,
        "contextText": context_text,
        "images": images,
        "tokenEstimate": token_estimate,
        "sources": sources,
        "contextFilePath": str(context_file_path.relative_to(docs_dir)),
        "contextFileSource": source_kind,
        "contextMarkdown": markdown,
        "usingDefault": using_default,
        "exists": context_file_path.exists(),
    }
