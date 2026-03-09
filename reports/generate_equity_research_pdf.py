#!/usr/bin/env python3
"""Generate LaTeX/PDF prompt libraries from markdown folders."""

from __future__ import annotations

import argparse
import datetime as dt
import html
import posixpath
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1]
REPORTS_DIR = ROOT / "reports"

HEADING_CMDS = {
    1: "section",
    2: "subsection",
    3: "subsubsection",
    4: "paragraph",
    5: "subparagraph",
}

SYMBOL_FALLBACK_CHARS = {"✓", "✔", "✗", "✘", "☑", "☒", "■", "□", "‣", "▸", "⟹"}

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


@dataclass
class ParsedFile:
    rel_path: Path
    front_matter: dict[str, str]
    body: str


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

    # Resolve placeholders iteratively so nested replacements are fully expanded.
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


def convert_code_block(lines: list[str], fence_info: str = "") -> str:
    if is_web_template_block(lines, fence_info):
        return summarize_web_block(lines)

    cleaned = [normalize_code_line(line) for line in lines]
    cleaned = [line for line in cleaned if line]
    if not cleaned:
        return ""

    out = [r"\textbf{Structured Template}", r"\begin{itemize}[leftmargin=*,itemsep=2pt,topsep=2pt]"]
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


def parse_files(paths: Iterable[Path], source_dir: Path) -> list[ParsedFile]:
    parsed: list[ParsedFile] = []
    for path in paths:
        raw = path.read_text(encoding="utf-8")
        meta, body = split_front_matter(raw)
        parsed.append(ParsedFile(rel_path=path.relative_to(source_dir), front_matter=meta, body=body))
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
    return rel_path.suffix == ".md" and "commands" in parts


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

    task_rows = extract_task_dependency_rows(parsed_files)
    if task_rows:
        lines.append(r"\subsection{Initiating Coverage Task Dependency Chain}")
        rows = [["Task", "Name", "Prerequisites", "Output"]] + task_rows
        lines.append(table_from_rows(rows, header=True))

    return "\n\n".join(lines)


def emit_file_header(rel: Path) -> str:
    rel_posix = rel.as_posix()
    safe_label = escape_latex(rel_posix).replace("/", "-")

    if is_command_file(rel):
        return f"\\subsection{{Command: {convert_inline(rel.name)}}}\\label{{file:{safe_label}}}"

    skill_name = skill_name_from_path(rel)
    if skill_name:
        return f"\\subsection{{Skill: {convert_inline(skill_name)}}}\\label{{file:{safe_label}}}"

    if "skills" in rel.parts:
        return f"\\subsection{{Skill Resource: {convert_inline(rel_posix)}}}\\label{{file:{safe_label}}}"

    return f"\\subsection{{File: {convert_inline(rel_posix)}}}\\label{{file:{safe_label}}}"


def emit_front_matter_table(metadata: dict[str, str]) -> str:
    if not metadata:
        return ""
    rows = [["Field", "Value"]] + [[k, v] for k, v in metadata.items()]
    return "\n".join([r"\paragraph{File Metadata}\mbox{}\par", table_from_rows(rows, header=True)])


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


def build_document(parsed_files: list[ParsedFile], source_label: str, out_tex: Path) -> None:
    rel_paths = [p.rel_path for p in parsed_files]
    emoji_chars, symbol_chars = extract_unicode_chars(parsed_files)

    title_prefix = source_label.replace("-", " ").replace("/", " / ").title()
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
        rf"\title{{{escape_latex(title_prefix)} Prompt Library\\LaTeX Translation and Dependency Map}}",
        r"\author{financial-services-plugins repository}",
        rf"\date{{Generated on {escape_latex(now)}}}",
    ]

    for emoji in emoji_chars:
        preamble.append(rf"\newunicodechar{{{emoji}}}{{{{\EmojiGlyph{{{emoji}}}}}}}")
    for symbol in symbol_chars:
        if symbol == "⟹":
            preamble.append(r"\newunicodechar{⟹}{$\Longrightarrow$}")
            continue
        preamble.append(rf"\newunicodechar{{{symbol}}}{{{{\SymbolGlyph{{{symbol}}}}}}}")

    preamble.extend([r"\begin{document}", r"\maketitle", r"\tableofcontents", r"\newpage"])

    latex_parts = ["\n".join(preamble)]
    latex_parts.append(r"\section{Repository Structure Overview}")
    latex_parts.append(emit_tree(rel_paths, source_label))
    latex_parts.append(render_dependency_section(parsed_files))
    latex_parts.append(r"\newpage")
    latex_parts.append(r"\section{Translated Prompt Corpus}")
    latex_parts.append(
        f"This section translates every markdown prompt under the {convert_inline(source_label)} directory into LaTeX-native structure, preserving hierarchy and dependency flow."
    )

    last_top_group = None
    for parsed in parsed_files:
        top_group = parsed.rel_path.parts[0]
        if top_group != last_top_group:
            latex_parts.append(rf"\subsection{{Directory: {convert_inline(top_group)}}}")
            last_top_group = top_group

        latex_parts.append(emit_file_header(parsed.rel_path))

        front_tex = emit_front_matter_table(parsed.front_matter)
        if front_tex:
            latex_parts.append(front_tex)

        latex_parts.append(markdown_to_latex(parsed.body, heading_offset=3))
        latex_parts.append(r"\vspace{0.8em}\hrule\vspace{0.8em}")

    latex_parts.append(r"\end{document}")
    out_tex.write_text("\n\n".join(part for part in latex_parts if part), encoding="utf-8")


def compile_pdf(tex_path: Path) -> None:
    stem = re.sub(r"[^A-Za-z0-9_-]", "_", tex_path.stem)
    log_paths = [Path(f"/tmp/{stem}_lualatex_1.log"), Path(f"/tmp/{stem}_lualatex_2.log")]
    compile_cmd = ["lualatex", "-interaction=nonstopmode", "-halt-on-error", tex_path.name]

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


def default_output_tex_for(source_dir: Path) -> Path:
    source_id = source_dir.as_posix().replace("/", "-")
    return REPORTS_DIR / f"{source_id}-prompts.tex"


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate LaTeX/PDF corpus for markdown prompts in a folder.")
    parser.add_argument("--source-dir", type=Path, default=Path("equity-research"), help="Folder under repo root to convert")
    parser.add_argument("--skip-compile", action="store_true", help="Generate .tex only")
    parser.add_argument("--output-tex", type=Path, default=None, help="Output .tex path")
    args = parser.parse_args()

    source_dir = (ROOT / args.source_dir).resolve() if not args.source_dir.is_absolute() else args.source_dir.resolve()
    if not source_dir.exists() or not source_dir.is_dir():
        raise FileNotFoundError(f"Source directory not found: {source_dir}")

    md_files = sorted(source_dir.rglob("*.md"))
    if not md_files:
        raise RuntimeError(f"No markdown files found under: {source_dir}")

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    out_tex = args.output_tex.resolve() if args.output_tex else default_output_tex_for(source_dir.relative_to(ROOT))

    parsed = parse_files(md_files, source_dir)
    build_document(parsed, source_dir.relative_to(ROOT).as_posix(), out_tex)

    if not args.skip_compile:
        compile_pdf(out_tex)


if __name__ == "__main__":
    main()
