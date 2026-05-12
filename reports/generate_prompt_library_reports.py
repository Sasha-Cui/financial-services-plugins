#!/usr/bin/env python3
"""Build long-form LaTeX/PDF prompt-library reports from Anthropic's financial-services repo."""

from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import posixpath
import re
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1]
REPORTS_DIR = ROOT / "reports"
UPSTREAM_REPO_URL = "https://github.com/anthropics/financial-services"

HEADING_CMDS = {
    1: "section",
    2: "subsection",
    3: "subsubsection",
    4: "paragraph",
    5: "subparagraph",
}

SYMBOL_FALLBACK_CHARS = {"✓", "✔", "✗", "✘", "☑", "☒", "■", "□", "‣", "▸", "⟹", "⟨", "⟩", "★"}
SPECIAL_UNICODE_LATEX = {
    "⟹": r"$\Longrightarrow$",
    "⟨": r"$\langle$",
    "⟩": r"$\rangle$",
    "★": r"$\star$",
}

LATEX_ESCAPES = {
    "\\": r"\textbackslash{}",
    "&": r"\&",
    "%": r"\%",
    "$": r"\$",
    "#": r"\#",
    "_": r"\_\allowbreak{}",
    "{": r"\{",
    "}": r"\}",
    "~": r"\textasciitilde{}",
    "^": r"\textasciicircum{}",
}

HTML_TAG_RE = re.compile(r"</?[A-Za-z][^>]*>")
HTML_COMMENT_RE = re.compile(r"<!--.*?-->", flags=re.DOTALL)
HTML_DECL_RE = re.compile(r"<![^>]*>")
HTML_PI_RE = re.compile(r"<\?[^>]*\?>")

INCLUDED_SUFFIXES = {".md", ".json", ".yaml", ".yml", ".py", ".txt", ".mjs", ".sh", ".example"}
INCLUDED_NAME_SUFFIXES = (".md.example", ".local.md.example")
IGNORED_DIRS = {".git", "__pycache__"}
IGNORED_NAMES = {".DS_Store", ".gitignore", "LICENSE", "LICENSE.txt"}


@dataclass(frozen=True)
class ReportSpec:
    key: str
    source_dir: str
    output_stem: str
    title: str


@dataclass
class ParsedFile:
    rel_path: Path
    front_matter: dict[str, str]
    body: str
    file_kind: str


REPORT_SPECS = [
    ReportSpec("financial-analysis", "plugins/vertical-plugins/financial-analysis", "financial-analysis-prompts", "Financial Analysis"),
    ReportSpec("investment-banking", "plugins/vertical-plugins/investment-banking", "investment-banking-prompts", "Investment Banking"),
    ReportSpec("equity-research", "plugins/vertical-plugins/equity-research", "equity-research-prompts", "Equity Research"),
    ReportSpec("private-equity", "plugins/vertical-plugins/private-equity", "private-equity-prompts", "Private Equity"),
    ReportSpec("wealth-management", "plugins/vertical-plugins/wealth-management", "wealth-management-prompts", "Wealth Management"),
    ReportSpec("fund-admin", "plugins/vertical-plugins/fund-admin", "fund-admin-prompts", "Fund Administration"),
    ReportSpec("operations", "plugins/vertical-plugins/operations", "operations-prompts", "Operations"),
    ReportSpec("partner-built", "plugins/partner-built", "partner-built-prompts", "Partner Built"),
    ReportSpec("agent-plugins", "plugins/agent-plugins", "agent-plugins-prompts", "Agent Plugins"),
    ReportSpec("managed-agent-cookbooks", "managed-agent-cookbooks", "managed-agent-cookbooks", "Managed Agent Cookbooks"),
    ReportSpec(
        "claude-for-msft-365-install",
        "claude-for-msft-365-install",
        "claude-for-msft-365-install-prompts",
        "Claude For Microsoft 365 Install",
    ),
]


def is_emoji_char(ch: str) -> bool:
    cp = ord(ch)
    if ch in SYMBOL_FALLBACK_CHARS:
        return False
    return (
        0x1F1E6 <= cp <= 0x1F1FF
        or 0x1F300 <= cp <= 0x1FAFF
        or 0x2600 <= cp <= 0x27BF
        or 0x2B00 <= cp <= 0x2BFF
    )


def sanitize_unicode(text: str) -> str:
    return text.replace("\ufe0f", "")


def strip_html_markup(text: str) -> str:
    cleaned = text
    for _ in range(2):
        decoded = html.unescape(cleaned)
        if decoded == cleaned:
            break
        cleaned = decoded

    cleaned = HTML_COMMENT_RE.sub("", cleaned)
    cleaned = HTML_DECL_RE.sub("", cleaned)
    cleaned = HTML_PI_RE.sub("", cleaned)
    cleaned = HTML_TAG_RE.sub("", cleaned)
    cleaned = cleaned.replace("\xa0", " ")
    return cleaned


def escape_latex(text: str) -> str:
    return "".join(LATEX_ESCAPES.get(ch, ch) for ch in text)


def smart_double_quotes(text: str) -> str:
    out: list[str] = []
    open_quote = True
    for ch in text:
        if ch == '"':
            out.append("``" if open_quote else "''")
            open_quote = not open_quote
        else:
            out.append(ch)
    return "".join(out)


def split_front_matter(text: str) -> tuple[dict[str, str], str]:
    if not text.startswith("---\n"):
        return {}, text

    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, text

    end_idx = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end_idx = i
            break

    if end_idx is None:
        return {}, text

    metadata: dict[str, str] = {}
    for raw_line in lines[1:end_idx]:
        if ":" not in raw_line:
            continue
        key, value = raw_line.split(":", 1)
        metadata[key.strip()] = value.strip().strip('"')

    body = "\n".join(lines[end_idx + 1 :])
    return metadata, body


def convert_inline(text: str) -> str:
    text = strip_html_markup(sanitize_unicode(text))
    placeholders: dict[str, str] = {}
    placeholder_prefix = f"CDEXTOKEN{abs(hash(text)) & 0xFFFFFFFF}X"

    def stash(value: str) -> str:
        key = f"{placeholder_prefix}{len(placeholders)}Z"
        placeholders[key] = value
        return key

    link_pattern = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
    code_pattern = re.compile(r"`([^`]+)`")
    bold_pattern = re.compile(r"\*\*([^*]+)\*\*")
    italic_pattern = re.compile(r"(?<!\*)\*([^*\n]+)\*(?!\*)")

    def link_sub(match: re.Match[str]) -> str:
        label = convert_inline(match.group(1))
        url = escape_latex(match.group(2).strip())
        return stash(rf"\href{{{url}}}{{{label}}}")

    text = link_pattern.sub(link_sub, text)
    text = code_pattern.sub(lambda m: stash(rf"\emph{{{escape_latex(m.group(1))}}}"), text)
    text = bold_pattern.sub(lambda m: stash(rf"\textbf{{{convert_inline(m.group(1))}}}"), text)
    text = italic_pattern.sub(lambda m: stash(rf"\emph{{{convert_inline(m.group(1))}}}"), text)

    escaped = escape_latex(text)

    for _ in range(len(placeholders) + 2):
        replaced_any = False
        for key, value in placeholders.items():
            if key in escaped:
                escaped = escaped.replace(key, value)
                replaced_any = True
        if not replaced_any:
            break

    return smart_double_quotes(escaped)


def latex_heading(level: int, title: str) -> str:
    adjusted = min(max(level, 1), 5)
    cmd = HEADING_CMDS[adjusted]
    text = convert_inline(title.strip())
    if cmd in {"paragraph", "subparagraph"}:
        return rf"\{cmd}{{{text}}}\mbox{{}}\par"
    return rf"\{cmd}{{{text}}}"


def is_heading(line: str) -> bool:
    return bool(re.match(r"^\s{0,3}#{1,6}\s+", line))


def is_fence_start(line: str) -> bool:
    return line.strip().startswith("```")


def is_list_item(line: str) -> bool:
    return bool(re.match(r"^\s*([-*+]\s+|\d+\.\s+)", line))


def is_quote(line: str) -> bool:
    return line.strip().startswith(">")


def is_hr(line: str) -> bool:
    return bool(re.match(r"^\s*([-*_]\s*){3,}$", line.strip()))


def is_table_separator(line: str) -> bool:
    stripped = line.strip()
    if "|" not in stripped:
        return False
    return bool(re.match(r"^\|?\s*[:\- ]+\|[|:\- ]+\|?\s*$", stripped))


def split_pipe_row(line: str) -> list[str]:
    row = line.strip()
    if row.startswith("|"):
        row = row[1:]
    if row.endswith("|"):
        row = row[:-1]
    return [cell.strip() for cell in row.split("|")]


def normalize_code_line(line: str) -> str:
    text = strip_html_markup(sanitize_unicode(line.rstrip()))
    text = text.replace("`", "")
    text = re.sub(r"[┌┐└┘├┤┬┴┼─│═]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return ""
    if re.fullmatch(r"[-_=]{3,}", text):
        return ""
    return text


def table_from_rows(rows: list[list[str]], header: bool = True) -> str:
    if not rows:
        return ""

    col_count = max(len(row) for row in rows)
    normalized_rows: list[list[str]] = []
    for row in rows:
        normalized_rows.append(row + [""] * (col_count - len(row)))

    table_width = 0.96 if col_count <= 4 else 0.92
    width = max(0.07, table_width / col_count)
    col_spec = "".join(
        rf">{{\RaggedRight\arraybackslash\hspace{{0pt}}}}p{{{width:.3f}\textwidth}}"
        for _ in range(col_count)
    )

    lines = [
        r"\begingroup",
        r"\small",
        r"\setlength{\tabcolsep}{2pt}",
        rf"\begin{{longtable}}{{{col_spec}}}",
        r"\toprule",
    ]

    for idx, row in enumerate(normalized_rows):
        softened = [cell.replace("/", "/ ").replace("_", "_ ") for cell in row]
        cells = [convert_inline(cell) for cell in softened]
        if header and idx == 0:
            cells = [rf"\textbf{{{cell}}}" for cell in cells]
            lines.append("{} " + " & ".join(cells) + r" \\")
            lines.append(r"\midrule")
            continue
        lines.append("{} " + " & ".join(cells) + r" \\")

    lines.extend([r"\bottomrule", r"\end{longtable}", r"\endgroup"])
    return "\n".join(lines)


def summarize_web_block(lines: list[str]) -> str:
    raw = "\n".join(lines).lower()
    points: list[str] = []

    if "<!doctype" in raw or "<html" in raw:
        points.append("Includes a full HTML document scaffold (doctype, head, and body).")
    if "<style" in raw or "@media print" in raw or "font-family" in raw:
        points.append("Defines embedded CSS, including print-oriented layout and typography rules.")
    if "chart.js" in raw or "chart.register" in raw or "chart." in raw:
        points.append("Configures Chart.js usage, including plugin registration and chart rendering behavior.")
    if "function create" in raw or "getcontext(" in raw:
        points.append("Implements reusable chart helper functions for consistent figure generation.")
    if "<table" in raw or "<tr" in raw or "<td" in raw:
        points.append("Contains HTML table structures for presenting formatted metric outputs.")
    if "<canvas" in raw:
        points.append("Defines canvas placeholders for interactive chart components.")
    if "<script" in raw:
        points.append("Loads and runs JavaScript needed for dynamic report visuals.")

    if not points:
        points.append("Contains implementation-level web template code for rendering the report.")

    out = [
        r"\textbf{Web Template Summary}",
        r"\begin{itemize}[leftmargin=*,itemsep=2pt,topsep=2pt]",
    ]
    for point in points:
        out.append(r"\item {} " + convert_inline(point))
    out.append(r"\item {} HTML/CSS/JavaScript implementation lines are intentionally omitted in print output for readability.")
    out.append(r"\end{itemize}")
    return "\n".join(out)


def is_web_template_block(lines: list[str], fence_info: str) -> bool:
    lang = fence_info.strip().lower()
    if lang in {"html", "xml", "javascript", "js", "css"}:
        return True

    raw = "\n".join(lines).lower()
    indicators = [
        "<!doctype",
        "<html",
        "<head",
        "<body",
        "<script",
        "<style",
        "</html",
        "chart.register",
        "document.getelementbyid(",
    ]
    return any(token in raw for token in indicators)


def convert_code_block(lines: list[str], fence_info: str = "", title: str = "Structured Template") -> str:
    if is_web_template_block(lines, fence_info):
        return summarize_web_block(lines)

    cleaned = [normalize_code_line(line) for line in lines]
    cleaned = [line for line in cleaned if line]
    if not cleaned:
        return ""

    out = [rf"\textbf{{{convert_inline(title)}}}", r"\begin{itemize}[leftmargin=*,itemsep=2pt,topsep=2pt]"]
    for line in cleaned:
        out.append(r"\item {} " + convert_inline(line))
    out.append(r"\end{itemize}")
    return "\n".join(out)


def collect_list_block(lines: list[str], start: int) -> tuple[list[str], int]:
    block: list[str] = []
    i = start
    while i < len(lines):
        line = lines[i]
        if not line.strip():
            if i + 1 < len(lines) and (is_list_item(lines[i + 1]) or lines[i + 1].startswith("  ")):
                block.append(line)
                i += 1
                continue
            break
        if not block and not is_list_item(line):
            break
        if block and not (is_list_item(line) or line.startswith(" ") or line.startswith("\t")):
            break
        block.append(line)
        i += 1
    return block, i


def convert_list_block(lines: list[str]) -> str:
    entries: list[dict[str, object]] = []

    for raw in lines:
        if not raw.strip():
            continue
        match = re.match(r"^(\s*)([-*+]|\d+\.)\s+(.*)$", raw)
        if match:
            indent = len(match.group(1).replace("\t", "    "))
            marker = match.group(2)
            content = match.group(3).strip()
            list_type = "enumerate" if marker.endswith(".") and marker[:-1].isdigit() else "itemize"
            entries.append({"indent": indent, "type": list_type, "text": content})
            continue
        if entries:
            entries[-1]["text"] = (str(entries[-1]["text"]) + " " + raw.strip()).strip()

    out: list[str] = []
    stack: list[tuple[int, str]] = []

    def open_env(env: str) -> None:
        out.append(rf"\begin{{{env}}}[leftmargin=*,itemsep=2pt,topsep=2pt]")

    def close_env() -> None:
        if stack:
            _, env = stack.pop()
            out.append(rf"\end{{{env}}}")

    for entry in entries:
        indent = int(entry["indent"])
        env = str(entry["type"])
        text = str(entry["text"])

        while stack and indent < stack[-1][0]:
            close_env()

        if not stack or indent > stack[-1][0]:
            open_env(env)
            stack.append((indent, env))
        elif env != stack[-1][1]:
            close_env()
            open_env(env)
            stack.append((indent, env))

        check_match = re.match(r"^\[( |x|X)\]\s+(.*)$", text)
        if check_match:
            mark = r"\CheckedBox" if check_match.group(1).lower() == "x" else r"\UncheckedBox"
            body = convert_inline(check_match.group(2).strip())
            out.append(rf"\item {{}} {mark} {body}")
        else:
            out.append(r"\item {} " + convert_inline(text))

    while stack:
        close_env()

    return "\n".join(out)


def convert_quote_block(lines: list[str]) -> str:
    text_parts = [re.sub(r"^\s*>\s?", "", line) for line in lines]
    text = convert_inline(" ".join(part.strip() for part in text_parts if part.strip()))
    return "\n".join([r"\begin{quote}", "``" + text + "''", r"\end{quote}"])


def is_table_start(lines: list[str], idx: int) -> bool:
    if idx + 1 >= len(lines):
        return False
    return "|" in lines[idx] and is_table_separator(lines[idx + 1])


def collect_table(lines: list[str], start: int) -> tuple[list[list[str]], int]:
    header = split_pipe_row(lines[start])
    i = start + 2
    rows = [header]
    while i < len(lines):
        raw = lines[i]
        if not raw.strip() or "|" not in raw:
            break
        rows.append(split_pipe_row(raw))
        i += 1
    return rows, i


def block_start(lines: list[str], idx: int) -> bool:
    line = lines[idx]
    return (
        is_heading(line)
        or is_fence_start(line)
        or is_list_item(line)
        or is_quote(line)
        or is_hr(line)
        or is_table_start(lines, idx)
    )


def markdown_to_latex(text: str, heading_offset: int = 0) -> str:
    lines = sanitize_unicode(text).splitlines()
    out: list[str] = []
    i = 0

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        if not stripped:
            out.append("")
            i += 1
            continue

        if is_heading(line):
            match = re.match(r"^\s{0,3}(#{1,6})\s+(.*)$", line)
            assert match is not None
            level = len(match.group(1)) + heading_offset
            out.append(latex_heading(level, match.group(2).strip()))
            i += 1
            continue

        if is_fence_start(line):
            fence_info = line.strip()[3:].strip()
            i += 1
            block_lines: list[str] = []
            while i < len(lines) and not is_fence_start(lines[i]):
                block_lines.append(lines[i])
                i += 1
            if i < len(lines):
                i += 1
            converted = convert_code_block(block_lines, fence_info=fence_info)
            if converted:
                out.append(converted)
            continue

        if is_table_start(lines, i):
            rows, i = collect_table(lines, i)
            out.append(table_from_rows(rows, header=True))
            continue

        if is_quote(line):
            quote_lines: list[str] = []
            while i < len(lines) and is_quote(lines[i]):
                quote_lines.append(lines[i])
                i += 1
            out.append(convert_quote_block(quote_lines))
            continue

        if is_list_item(line):
            block, i = collect_list_block(lines, i)
            out.append(convert_list_block(block))
            continue

        if is_hr(line):
            out.append(r"\vspace{0.5em}\hrule\vspace{0.5em}")
            i += 1
            continue

        para_lines = [line.strip()]
        i += 1
        while i < len(lines) and lines[i].strip() and not block_start(lines, i):
            para_lines.append(lines[i].strip())
            i += 1

        out.append(convert_inline(" ".join(para_lines)) + "\n")

    return "\n".join(out)


def classify_file(path: Path) -> str:
    name = path.name
    if name.endswith(".md") or any(name.endswith(sfx) for sfx in INCLUDED_NAME_SUFFIXES):
        return "markdown"
    if name.endswith(".json"):
        return "json"
    if name.endswith(".yaml") or name.endswith(".yml"):
        return "yaml"
    if name.endswith(".py") or name.endswith(".mjs") or name.endswith(".sh"):
        return "script"
    return "text"


def is_included_file(path: Path) -> bool:
    if not path.is_file():
        return False
    if any(part in IGNORED_DIRS for part in path.parts):
        return False
    if path.name in IGNORED_NAMES:
        return False
    if path.name.endswith(INCLUDED_NAME_SUFFIXES):
        return True
    return any(sfx in INCLUDED_SUFFIXES for sfx in path.suffixes)


def collect_source_files(source_dir: Path) -> list[Path]:
    return sorted(
        [path for path in source_dir.rglob("*") if is_included_file(path)],
        key=lambda path: path.relative_to(source_dir).as_posix().lower(),
    )


def parse_files(paths: Iterable[Path], source_dir: Path) -> list[ParsedFile]:
    parsed: list[ParsedFile] = []
    for path in paths:
        raw = path.read_text(encoding="utf-8", errors="ignore")
        file_kind = classify_file(path)
        if file_kind == "markdown":
            meta, body = split_front_matter(raw)
        else:
            meta, body = {}, raw
        parsed.append(ParsedFile(rel_path=path.relative_to(source_dir), front_matter=meta, body=body, file_kind=file_kind))
    return parsed


def emit_tree(paths: list[Path], root_label: str) -> str:
    nodes: set[tuple[int, str]] = set()
    for path in paths:
        for depth in range(1, len(path.parts) + 1):
            sub = Path(*path.parts[:depth]).as_posix()
            nodes.add((depth - 1, sub))

    rendered = [
        r"\subsection{Folder Tree}",
        rf"\textbf{{Root directory: {convert_inline(root_label)}}}",
        r"\begin{itemize}[leftmargin=*,itemsep=1pt,topsep=2pt]",
    ]

    for depth, node in sorted(nodes, key=lambda x: (x[1].count("/"), x[1].lower())):
        indent = rf"\hspace*{{{depth * 0.9:.1f}em}}"
        rendered.append(rf"\item {indent}{convert_inline(node)}")

    rendered.append(r"\end{itemize}")
    return "\n".join(rendered)


def resolve_relative(base: str, rel_target: str) -> str:
    joined = posixpath.normpath(posixpath.join(posixpath.dirname(base), rel_target))
    return joined.lstrip("./")


def is_command_file(rel_path: Path) -> bool:
    parts = rel_path.parts
    return rel_path.name.endswith(".md") and "commands" in parts


def skill_name_from_path(rel_path: Path) -> str | None:
    parts = list(rel_path.parts)
    if rel_path.name != "SKILL.md":
        return None
    if "skills" not in parts:
        return None
    idx = parts.index("skills")
    if idx + 1 >= len(parts):
        return None
    return parts[idx + 1]


def build_skill_index(parsed_files: list[ParsedFile]) -> dict[str, list[str]]:
    index: dict[str, list[str]] = {}
    for parsed in parsed_files:
        name = skill_name_from_path(parsed.rel_path)
        if not name:
            continue
        index.setdefault(name.lower(), []).append(parsed.rel_path.as_posix())
    return index


def extract_command_skill_dependencies(parsed_files: list[ParsedFile]) -> list[tuple[str, str]]:
    rows: set[tuple[str, str]] = set()
    skill_index = build_skill_index(parsed_files)

    for parsed in parsed_files:
        if not is_command_file(parsed.rel_path):
            continue

        rel = parsed.rel_path.as_posix()
        text = parsed.body
        found = set(re.findall(r"Load the [`\"]?([a-z0-9\-]+)[`\"]? skill", text, flags=re.IGNORECASE))
        found.update(re.findall(r"skill:\s*[\"']([a-z0-9\-]+)[\"']", text, flags=re.IGNORECASE))

        for skill in found:
            candidates = skill_index.get(skill.lower())
            if candidates:
                for candidate in candidates:
                    rows.add((rel, candidate))
            else:
                rows.add((rel, f"skills/{skill}/SKILL.md"))

    return sorted(rows)


def extract_skill_resource_dependencies(parsed_files: list[ParsedFile]) -> list[tuple[str, str]]:
    rows: set[tuple[str, str]] = set()

    for parsed in parsed_files:
        rel = parsed.rel_path.as_posix()
        if skill_name_from_path(parsed.rel_path) is None:
            continue

        text = parsed.body
        links = re.findall(r"\[[^\]]+\]\(([^)]+)\)", text)
        for link in links:
            if link.startswith("http"):
                continue
            target = resolve_relative(rel, link.split("#")[0])
            if target.endswith(".md"):
                rows.add((rel, target))

        for raw_target in re.findall(r"((?:references|assets)/[A-Za-z0-9_\-./]+\.md)", text):
            rows.add((rel, resolve_relative(rel, raw_target)))

    return sorted(rows)


def extract_config_file_dependencies(parsed_files: list[ParsedFile]) -> list[tuple[str, str]]:
    rows: set[tuple[str, str]] = set()
    known_paths = {parsed.rel_path.as_posix() for parsed in parsed_files}

    patterns = [
        r"(?:from_plugin|manifest|file|path):\s*['\"]?([./A-Za-z0-9_\-/]+(?:\.[A-Za-z0-9_.-]+)?)",
        r'"(?:from_plugin|manifest|file|path)"\s*:\s*"([^"]+)"',
    ]

    for parsed in parsed_files:
        if parsed.file_kind not in {"json", "yaml", "script", "text"}:
            continue
        rel = parsed.rel_path.as_posix()
        for pattern in patterns:
            for raw_target in re.findall(pattern, parsed.body):
                if raw_target.startswith("http"):
                    continue
                target = resolve_relative(rel, raw_target)
                if target in known_paths:
                    rows.add((rel, target))

    return sorted(rows)


def extract_task_dependency_rows(parsed_files: list[ParsedFile]) -> list[list[str]]:
    task_rows: list[list[str]] = []

    for parsed in parsed_files:
        rel = parsed.rel_path.as_posix()
        if "initiating-coverage/SKILL.md" not in rel:
            continue
        for line in parsed.body.splitlines():
            match = re.match(r"^\|\s*\*\*(\d+)\*\*\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|", line)
            if not match:
                continue
            task_rows.append([f"Task {match.group(1)}", match.group(2).strip(), match.group(3).strip(), match.group(4).strip()])

    return task_rows


def render_dependency_section(parsed_files: list[ParsedFile]) -> str:
    lines = [r"\section{Prompt Dependency Structure}"]

    cmd_skill = extract_command_skill_dependencies(parsed_files)
    if cmd_skill:
        lines.append(r"\subsection{Command-to-Skill Dependencies}")
        rows = [["Command Prompt", "Loaded Skill Prompt"]] + [list(item) for item in cmd_skill]
        lines.append(table_from_rows(rows, header=True))

    skill_resources = extract_skill_resource_dependencies(parsed_files)
    if skill_resources:
        lines.append(r"\subsection{Skill-to-Resource Dependencies}")
        rows = [["Skill Prompt", "Referenced Prompt File"]] + [list(item) for item in skill_resources]
        lines.append(table_from_rows(rows, header=True))

    config_refs = extract_config_file_dependencies(parsed_files)
    if config_refs:
        lines.append(r"\subsection{Config-to-File Dependencies}")
        rows = [["Config or Script File", "Referenced File"]] + [list(item) for item in config_refs]
        lines.append(table_from_rows(rows, header=True))

    task_rows = extract_task_dependency_rows(parsed_files)
    if task_rows:
        lines.append(r"\subsection{Initiating Coverage Task Dependency Chain}")
        rows = [["Task", "Name", "Prerequisites", "Output"]] + task_rows
        lines.append(table_from_rows(rows, header=True))

    return "\n\n".join(lines)


def emit_file_header(parsed: ParsedFile) -> str:
    rel = parsed.rel_path
    rel_posix = rel.as_posix()
    safe_label = re.sub(r"[^A-Za-z0-9]+", "-", rel_posix).strip("-") or "file"

    if is_command_file(rel):
        return f"\\subsection{{Command: {convert_inline(rel.name)}}}\\label{{file:{safe_label}}}"

    skill_name = skill_name_from_path(rel)
    if skill_name:
        return f"\\subsection{{Skill: {convert_inline(skill_name)}}}\\label{{file:{safe_label}}}"

    if rel.name == "plugin.json":
        return f"\\subsection{{Plugin Manifest: {convert_inline(rel.parent.as_posix())}}}\\label{{file:{safe_label}}}"
    if rel.name == ".mcp.json":
        return f"\\subsection{{MCP Configuration: {convert_inline(rel.parent.as_posix())}}}\\label{{file:{safe_label}}}"
    if rel.name == "agent.yaml":
        return f"\\subsection{{Managed Agent Manifest: {convert_inline(rel.parent.as_posix())}}}\\label{{file:{safe_label}}}"
    if rel.name == "steering-examples.json":
        return f"\\subsection{{Steering Examples: {convert_inline(rel.parent.as_posix())}}}\\label{{file:{safe_label}}}"

    if parsed.file_kind == "json":
        return f"\\subsection{{Config File: {convert_inline(rel_posix)}}}\\label{{file:{safe_label}}}"
    if parsed.file_kind == "yaml":
        return f"\\subsection{{Manifest File: {convert_inline(rel_posix)}}}\\label{{file:{safe_label}}}"
    if parsed.file_kind == "script":
        return f"\\subsection{{Script File: {convert_inline(rel_posix)}}}\\label{{file:{safe_label}}}"
    if "skills" in rel.parts:
        return f"\\subsection{{Skill Resource: {convert_inline(rel_posix)}}}\\label{{file:{safe_label}}}"

    return f"\\subsection{{File: {convert_inline(rel_posix)}}}\\label{{file:{safe_label}}}"


def emit_front_matter_table(metadata: dict[str, str]) -> str:
    if not metadata:
        return ""
    rows = [["Field", "Value"]] + [[k, v] for k, v in metadata.items()]
    return "\n".join([r"\paragraph{File Metadata}\mbox{}\par", table_from_rows(rows, header=True)])


def summarize_json_value(value: object) -> str:
    if isinstance(value, dict):
        return f"object with {len(value)} key(s)"
    if isinstance(value, list):
        return f"list with {len(value)} item(s)"
    if value is None:
        return "null"
    return str(value)


def render_json_summary(parsed: ParsedFile) -> str:
    try:
        data = json.loads(parsed.body)
    except json.JSONDecodeError:
        return ""

    sections: list[str] = [r"\paragraph{JSON Summary}\mbox{}\par"]

    if isinstance(data, dict):
        rows = [["Key", "Type", "Summary"]]
        for key, value in data.items():
            rows.append([str(key), type(value).__name__, summarize_json_value(value)])
        sections.append(table_from_rows(rows, header=True))

        if "mcpServers" in data and isinstance(data["mcpServers"], dict):
            rows = [["Connector", "Type", "URL"]]
            for name, config in data["mcpServers"].items():
                if isinstance(config, dict):
                    rows.append([str(name), str(config.get("type", "")), str(config.get("url", ""))])
            sections.append(r"\paragraph{MCP Server Inventory}\mbox{}\par")
            sections.append(table_from_rows(rows, header=True))

        if "plugins" in data and isinstance(data["plugins"], list):
            rows = [["Plugin", "Source", "Description"]]
            for item in data["plugins"]:
                if isinstance(item, dict):
                    rows.append([str(item.get("name", "")), str(item.get("source", "")), str(item.get("description", ""))])
            sections.append(r"\paragraph{Marketplace Plugins}\mbox{}\par")
            sections.append(table_from_rows(rows, header=True))

        if "callable_agents" in data and isinstance(data["callable_agents"], list):
            rows = [["Agent", "Type", "Summary"]]
            for idx, item in enumerate(data["callable_agents"], start=1):
                if isinstance(item, dict):
                    rows.append([f"Callable {idx}", str(item.get("type", "")), summarize_json_value(item)])
            sections.append(r"\paragraph{Callable Agents}\mbox{}\par")
            sections.append(table_from_rows(rows, header=True))

    elif isinstance(data, list):
        rows = [["Item", "Type", "Summary"]]
        for idx, value in enumerate(data, start=1):
            rows.append([str(idx), type(value).__name__, summarize_json_value(value)])
        sections.append(table_from_rows(rows, header=True))

    return "\n".join(sections)


def render_yaml_summary(parsed: ParsedFile) -> str:
    rows = [["Key", "Value or Block"]]
    seen = 0
    for line in parsed.body.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if line.startswith((" ", "\t", "-")):
            continue
        if ":" not in stripped:
            continue
        key, value = stripped.split(":", 1)
        rows.append([key.strip(), value.strip() or "(nested block)"])
        seen += 1

    if seen == 0:
        return ""

    refs = re.findall(r"(?:from_plugin|manifest|file|path):\s*([^\n]+)", parsed.body)
    sections = [r"\paragraph{YAML Summary}\mbox{}\par", table_from_rows(rows, header=True)]
    if refs:
        ref_rows = [["Reference Field", "Value"]]
        for ref in refs:
            ref_rows.append(["linked path", ref.strip().strip("'\"")])
        sections.append(r"\paragraph{Referenced Paths}\mbox{}\par")
        sections.append(table_from_rows(ref_rows, header=True))
    return "\n".join(sections)


def render_script_summary(parsed: ParsedFile) -> str:
    text = parsed.body
    summary_rows = [["Signal", "Details"]]
    imports = re.findall(r"^(?:from|import)\s+([A-Za-z0-9_., ]+)", text, flags=re.MULTILINE)
    funcs = re.findall(r"^def\s+([A-Za-z0-9_]+)\(", text, flags=re.MULTILINE)
    classes = re.findall(r"^class\s+([A-Za-z0-9_]+)\b", text, flags=re.MULTILINE)
    shell_funcs = re.findall(r"^([A-Za-z0-9_]+)\s*\(\)\s*\{", text, flags=re.MULTILINE)

    if imports:
        summary_rows.append(["Imports", ", ".join(imports[:8])])
    if classes:
        summary_rows.append(["Classes", ", ".join(classes[:12])])
    if funcs:
        summary_rows.append(["Functions", ", ".join(funcs[:16])])
    if shell_funcs:
        summary_rows.append(["Shell functions", ", ".join(shell_funcs[:16])])
    if "__main__" in text:
        summary_rows.append(["Entry point", "Defines an executable main entry point"])
    if "argparse" in text or "ArgumentParser" in text:
        summary_rows.append(["CLI", "Exposes command-line argument parsing"])
    if "subprocess" in text or "Popen(" in text or "run(" in text:
        summary_rows.append(["Process execution", "Invokes subprocesses or external commands"])

    if len(summary_rows) == 1:
        return ""

    return "\n".join([r"\paragraph{Script Summary}\mbox{}\par", table_from_rows(summary_rows, header=True)])


def render_inventory_section(parsed_files: list[ParsedFile]) -> str:
    rows = [["Metric", "Count"]]
    rows.append(["Total included files", str(len(parsed_files))])
    rows.append(["Markdown or markdown-like files", str(sum(1 for p in parsed_files if p.file_kind == "markdown"))])
    rows.append(["JSON config files", str(sum(1 for p in parsed_files if p.file_kind == "json"))])
    rows.append(["YAML manifest files", str(sum(1 for p in parsed_files if p.file_kind == "yaml"))])
    rows.append(["Scripts", str(sum(1 for p in parsed_files if p.file_kind == "script"))])
    rows.append(["Other text files", str(sum(1 for p in parsed_files if p.file_kind == "text"))])
    rows.append(["Commands", str(sum(1 for p in parsed_files if is_command_file(p.rel_path)))])
    rows.append(["Skills", str(sum(1 for p in parsed_files if skill_name_from_path(p.rel_path) is not None))])
    rows.append(["Plugin manifests", str(sum(1 for p in parsed_files if p.rel_path.name == "plugin.json"))])
    rows.append(["Managed-agent manifests", str(sum(1 for p in parsed_files if p.rel_path.name == "agent.yaml"))])
    return "\n".join([r"\subsection{Inventory Summary}", table_from_rows(rows, header=True)])


def extract_unicode_chars(parsed_files: list[ParsedFile]) -> tuple[list[str], list[str]]:
    emoji_chars: set[str] = set()
    symbol_chars: set[str] = set()
    for parsed in parsed_files:
        text = sanitize_unicode("\n".join([parsed.body, "\n".join(parsed.front_matter.values())]))
        for ch in text:
            if is_emoji_char(ch):
                emoji_chars.add(ch)
            if ch in SYMBOL_FALLBACK_CHARS:
                symbol_chars.add(ch)
    return sorted(emoji_chars), sorted(symbol_chars)


def render_non_markdown_body(parsed: ParsedFile) -> str:
    sections: list[str] = []
    if parsed.file_kind == "json":
        summary = render_json_summary(parsed)
        if summary:
            sections.append(summary)
        sections.append(convert_code_block(parsed.body.splitlines(), fence_info="json", title="Structured JSON Content"))
    elif parsed.file_kind == "yaml":
        summary = render_yaml_summary(parsed)
        if summary:
            sections.append(summary)
        sections.append(convert_code_block(parsed.body.splitlines(), fence_info="yaml", title="Structured YAML Content"))
    elif parsed.file_kind == "script":
        summary = render_script_summary(parsed)
        if summary:
            sections.append(summary)
        sections.append(convert_code_block(parsed.body.splitlines(), fence_info=parsed.rel_path.suffix.lstrip("."), title="Normalized Script Content"))
    else:
        sections.append(convert_code_block(parsed.body.splitlines(), title="Structured File Content"))
    return "\n\n".join(section for section in sections if section)


def build_document(parsed_files: list[ParsedFile], title_prefix: str, source_label: str, out_tex: Path) -> None:
    rel_paths = [p.rel_path for p in parsed_files]
    emoji_chars, symbol_chars = extract_unicode_chars(parsed_files)
    now = dt.datetime.now().strftime("%Y-%m-%d %H:%M %Z")

    preamble = [
        r"\documentclass[11pt]{article}",
        r"\usepackage[margin=0.85in]{geometry}",
        r"\usepackage{fontspec}",
        r"\setmainfont{Times New Roman}",
        r"\newfontfamily\EmojiFont[Renderer=HarfBuzz]{Apple Color Emoji}",
        r"\newfontfamily\SymbolFont{Arial Unicode MS}",
        r"\newcommand{\EmojiGlyph}[1]{{\normalfont\EmojiFont #1}}",
        r"\newcommand{\SymbolGlyph}[1]{{\normalfont\SymbolFont #1}}",
        r"\usepackage{newunicodechar}",
        r"\usepackage{microtype}",
        r"\usepackage{setspace}",
        r"\setstretch{1.08}",
        r"\usepackage{hyperref}",
        r"\usepackage{xurl}",
        r"\urlstyle{same}",
        r"\hypersetup{colorlinks=true,linkcolor=blue,urlcolor=blue}",
        r"\usepackage{enumitem}",
        r"\setlist{leftmargin=*,itemsep=2pt,topsep=2pt}",
        r"\usepackage{array}",
        r"\usepackage{longtable}",
        r"\usepackage{booktabs}",
        r"\usepackage{amssymb}",
        r"\usepackage{ragged2e}",
        r"\renewcommand{\arraystretch}{1.15}",
        r"\setlength{\parskip}{0.45em}",
        r"\setlength{\parindent}{0pt}",
        r"\setlength{\emergencystretch}{3em}",
        r"\sloppy",
        r"\newcommand{\UncheckedBox}{$\square$}",
        r"\newcommand{\CheckedBox}{$\blacksquare$}",
        rf"\title{{{escape_latex(title_prefix)} Prompt Library\\Comprehensive Translation, Config Coverage, and Dependency Map}}",
        r"\author{financial-services-plugins repository}",
        rf"\date{{Generated on {escape_latex(now)}}}",
    ]

    for emoji in emoji_chars:
        preamble.append(rf"\newunicodechar{{{emoji}}}{{{{\EmojiGlyph{{{emoji}}}}}}}")
    for symbol in symbol_chars:
        if symbol in SPECIAL_UNICODE_LATEX:
            preamble.append(rf"\newunicodechar{{{symbol}}}{{{SPECIAL_UNICODE_LATEX[symbol]}}}")
            continue
        preamble.append(rf"\newunicodechar{{{symbol}}}{{{{\SymbolGlyph{{{symbol}}}}}}}")

    preamble.extend([r"\begin{document}", r"\maketitle", r"\tableofcontents", r"\newpage"])

    latex_parts = ["\n".join(preamble)]
    latex_parts.append(r"\section{Repository Structure Overview}")
    latex_parts.append(render_inventory_section(parsed_files))
    latex_parts.append(emit_tree(rel_paths, source_label))
    latex_parts.append(render_dependency_section(parsed_files))
    latex_parts.append(r"\newpage")
    latex_parts.append(r"\section{Translated Prompt Corpus}")
    latex_parts.append(
        f"This section translates the prompt, manifest, configuration, and script files under {convert_inline(source_label)} into a print-oriented format that preserves structure while improving readability."
    )

    last_top_group = None
    for parsed in parsed_files:
        top_group = parsed.rel_path.parts[0] if parsed.rel_path.parts else parsed.rel_path.as_posix()
        if top_group != last_top_group:
            latex_parts.append(rf"\subsection{{Directory: {convert_inline(top_group)}}}")
            last_top_group = top_group

        latex_parts.append(emit_file_header(parsed))

        front_tex = emit_front_matter_table(parsed.front_matter)
        if front_tex:
            latex_parts.append(front_tex)

        if parsed.file_kind == "markdown":
            latex_parts.append(markdown_to_latex(parsed.body, heading_offset=3))
        else:
            latex_parts.append(render_non_markdown_body(parsed))
        latex_parts.append(r"\vspace{0.8em}\hrule\vspace{0.8em}")

    latex_parts.append(r"\end{document}")
    out_tex.write_text("\n\n".join(part for part in latex_parts if part), encoding="utf-8")


def compile_pdf(tex_path: Path) -> None:
    stem = re.sub(r"[^A-Za-z0-9_-]", "_", tex_path.stem)
    log_paths = [Path(f"/tmp/{stem}_lualatex_1.log"), Path(f"/tmp/{stem}_lualatex_2.log")]
    compile_cmd = ["lualatex", "-interaction=nonstopmode", "-halt-on-error", tex_path.name]

    for suffix in [".aux", ".log", ".out", ".toc", ".pdf"]:
        artifact = tex_path.with_suffix(suffix)
        if artifact.exists():
            artifact.unlink()

    for log_path in log_paths:
        with log_path.open("w", encoding="utf-8") as handle:
            result = subprocess.run(
                compile_cmd,
                cwd=tex_path.parent,
                stdout=handle,
                stderr=subprocess.STDOUT,
                check=False,
            )
        if result.returncode != 0:
            raise RuntimeError(f"LuaLaTeX compilation failed. Check {log_paths[0]} and {log_paths[1]}")

    for suffix in [".aux", ".log", ".out", ".toc"]:
        artifact = tex_path.with_suffix(suffix)
        if artifact.exists():
            artifact.unlink()


def clone_upstream_repo(target_dir: Path) -> Path:
    subprocess.run(["git", "clone", "--depth", "1", UPSTREAM_REPO_URL, str(target_dir)], check=True)
    return target_dir


def build_report(spec: ReportSpec, upstream_root: Path, skip_compile: bool) -> None:
    source_dir = upstream_root / spec.source_dir
    if not source_dir.exists():
        raise FileNotFoundError(f"Source directory not found: {source_dir}")

    files = collect_source_files(source_dir)
    if not files:
        raise RuntimeError(f"No supported text files found under: {source_dir}")

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    out_tex = REPORTS_DIR / f"{spec.output_stem}.tex"
    parsed = parse_files(files, source_dir)
    build_document(parsed, spec.title, spec.source_dir, out_tex)

    if not skip_compile:
        compile_pdf(out_tex)


def resolve_specs(selected_keys: list[str] | None) -> list[ReportSpec]:
    if not selected_keys:
        return REPORT_SPECS
    wanted = {key.strip() for key in selected_keys}
    specs = [spec for spec in REPORT_SPECS if spec.key in wanted or spec.output_stem in wanted]
    if len(specs) != len(wanted):
        found = {spec.key for spec in specs} | {spec.output_stem for spec in specs}
        missing = sorted(wanted - found)
        raise SystemExit(f"Unknown report key(s): {', '.join(missing)}")
    return specs


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate long-form LaTeX/PDF prompt-library reports from Anthropic's financial-services repo.")
    parser.add_argument("--upstream-dir", type=Path, default=None, help="Use an existing local checkout instead of cloning upstream")
    parser.add_argument("--report", action="append", help="Specific report key or output stem to build; can be repeated")
    parser.add_argument("--skip-compile", action="store_true", help="Generate .tex only")
    args = parser.parse_args()

    specs = resolve_specs(args.report)

    if args.upstream_dir:
        upstream_root = args.upstream_dir.resolve()
        for spec in specs:
            build_report(spec, upstream_root, skip_compile=args.skip_compile)
        return

    with tempfile.TemporaryDirectory(prefix="financial-services-upstream-") as tmp:
        upstream_root = clone_upstream_repo(Path(tmp) / "upstream")
        for spec in specs:
            build_report(spec, upstream_root, skip_compile=args.skip_compile)


if __name__ == "__main__":
    main()
