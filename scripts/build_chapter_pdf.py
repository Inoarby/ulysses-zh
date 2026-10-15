"""Build Chinese, paragraph-aligned bilingual, and side-commented chapter PDFs.

Usage: python scripts/build_chapter_pdf.py 01 [--edition both|zh|parallel|commented]
Requires reportlab. Input files are never changed. Source and translation must
have matching blank-line paragraphs, including original part/chapter headings.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import KeepTogether, Paragraph, SimpleDocTemplate, Table, TableStyle


ROOT = Path(__file__).resolve().parent.parent
NOTE = re.compile(r"(【注：[^】]*】)")
BODY_SIZE, NOTE_SIZE, LEADING = 10.5, 8, 16.3
ENGLISH_SIZE, ENGLISH_LEADING = 9.5, 13.7
NOTE_COLOR, ENGLISH_COLOR = "#A66F73", "#929CA6"
COMMENT_SIZE, COMMENT_LEADING, COMMENT_COLOR = 9, 14, "#466D68"
COMMENT_GAP = 9 * mm
PAGE_SIZES = {"zh": (152 * mm, 228 * mm), "parallel": (170 * mm, 240 * mm),
              "commented": (240 * mm, 240 * mm)}
EDITION_NAMES = {"zh": "中文译本", "parallel": "中英对照本", "commented": "中英对照·旁注导读本"}
MARGIN_X, TOP_MARGIN, BOTTOM_MARGIN = 18 * mm, 20 * mm, 19 * mm
TOKEN = re.compile(r"[A-Za-zÀ-ÖØ-öø-ÿ\u0338]+(?:[.’'-][A-Za-zÀ-ÖØ-öø-ÿ\u0338]+)*\.?|[0-9]+(?:\.[0-9]+)*|——|……|\s+|.")
NO_START = set("，。！？；：、）》】〉〕』」”’,.!?;:%％·")
NO_END = set("（《【〈〔『「“‘·")
GLYPH_FONTS = {"✠": "TextSymbols", "\u0338": "TextMarks"}
SYMBOL_CHARACTERS = frozenset(GLYPH_FONTS)


class ChapterParagraph(Paragraph):
    def split(self, available_width, available_height):
        pieces = super().split(available_width, available_height)
        # Bring a line of context with a note that would start on the next page.
        if len(pieces) > 1:
            first = next((f for f in pieces[1].frags if getattr(f, "text", "").strip()), None)
            if first is not None and first.fontSize == NOTE_SIZE:
                return super().split(available_width, available_height - self.style.leading)
        return pieces


def paragraphs(text: str) -> list[str]:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    return re.split(r"\n\s*\n", text.strip())


def publication_sources(directory: Path, sources: list[str]) -> list[str]:
    """Apply explicitly marked publication omissions without editing the source."""
    path = directory / "source-overrides.json"
    if not path.exists():
        return sources
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema_version") != 1 or not isinstance(data.get("paragraphs"), dict):
        raise ValueError("Invalid source-overrides.json schema")
    result = list(sources)
    for key, entry in data["paragraphs"].items():
        if not key.isdigit() or key != str(int(key)) or not 1 <= int(key) <= len(sources):
            raise ValueError(f"Invalid source override paragraph: {key}")
        original = sources[int(key) - 1]
        if not isinstance(entry, dict) or entry.get("original_sha256") != hashlib.sha256(original.encode("utf-8")).hexdigest():
            raise ValueError(f"Source override needs review after changes to paragraph {key}")
        replacement = entry.get("text")
        if (not isinstance(replacement, str) or not replacement.strip()
                or len(paragraphs(replacement)) != 1 or "[Editorial omission:" not in replacement
                or not isinstance(entry.get("reason"), str) or not entry["reason"].strip()):
            raise ValueError(f"Source override must retain one paragraph and visibly mark its omission: {key}")
        result[int(key) - 1] = replacement
    return result


def note_text(text: str) -> str:
    """Visible text; labels and brackets are internal source markup only."""
    return NOTE.sub(lambda m: m.group(0)[3:-1], text)


def escaped_with_symbols(text: str) -> str:
    """Preserve rare symbols and the source's combining deletion strokes."""
    return "".join(f'<font name="{GLYPH_FONTS[c]}">{c}</font>' if c in SYMBOL_CHARACTERS
                   else escape(c) for c in text)


def markup(text: str, style: ParagraphStyle, text_width: float) -> str:
    """Set explicit legal CJK breaks across mixed-size font fragments."""
    lines = []
    for hard_line in text.splitlines():
        tokens = []
        for part in NOTE.split(hard_line):
            is_note = part.startswith("【注：")
            if is_note:
                part = " " + part[3:-1] + " "
            size = NOTE_SIZE if is_note else style.fontSize
            for token in TOKEN.findall(part):
                width = (sum(pdfmetrics.stringWidth(c, GLYPH_FONTS.get(c, "Song"), size) for c in token)
                         if any(c in SYMBOL_CHARACTERS for c in token)
                         else pdfmetrics.stringWidth(token, "Song", size))
                tokens.append((token, is_note, width))
        while tokens:
            while tokens and tokens[0][0].isspace():
                tokens.pop(0)
            if not tokens:
                break
            width = text_width - style.leftIndent - style.rightIndent - 0.5
            if not lines:
                width -= style.firstLineIndent
            used, fit = 0, 0
            for token, _, token_width in tokens:
                if used + token_width > width:
                    break
                used += token_width
                fit += 1
            if fit == 0:
                raise ValueError(f"Unbreakable word exceeds line width: {tokens[0][0]}")
            if fit < len(tokens):
                while fit > 0:
                    before = next((t[0] for t in reversed(tokens[:fit]) if not t[0].isspace()), "")
                    after = next((t[0] for t in tokens[fit:] if not t[0].isspace()), "")
                    if before and after and before[-1] not in NO_END and after[0] not in NO_START:
                        break
                    fit -= 1
                if fit == 0:
                    raise ValueError("Cannot find a legal Chinese line break")
            line, tokens = tokens[:fit], tokens[fit:]
            while line and line[-1][0].isspace():
                line.pop()
            groups = []
            for token, is_note, _ in line:
                if groups and groups[-1][0] == is_note:
                    groups[-1][1] += token
                else:
                    groups.append([is_note, token])
            line_xml = []
            for is_note, value in groups:
                value = escaped_with_symbols(value)
                if is_note:
                    value = f'<font size="{NOTE_SIZE}" color="{NOTE_COLOR}">{value}</font>'
                line_xml.append(value)
            lines.append("".join(line_xml))
    return "<br/>".join(lines)


class EnglishMarkup:
    """Convert Gutenberg underscores to italics, including across paragraphs."""
    def __init__(self):
        self.italic = False

    def format(self, text: str, verse: bool) -> str:
        lines = [line.strip() for line in text.splitlines()]
        text = "\n".join(lines) if verse else " ".join(lines)
        result = ["<i>"] if self.italic else []
        for index, part in enumerate(text.split("_")):
            if index:
                result.append("</i>" if self.italic else "<i>")
                self.italic = not self.italic
            result.append(escaped_with_symbols(part).replace("\n", "<br/>"))
        if self.italic:
            result.append("</i>")
        return "".join(result)


def split_after(text: str, anchors: list[str]) -> list[str]:
    result = []
    for anchor in anchors:
        if text.count(anchor) != 1:
            raise ValueError(f"Parallel split anchor must occur exactly once: {anchor!r}")
        end = text.index(anchor) + len(anchor)
        result.append(text[:end].strip())
        text = text[end:].strip()
    if not text:
        raise ValueError("Parallel split produced an empty final segment")
    result.append(text)
    return result


def aligned_units(directory: Path, sources: list[str], targets: list[str]) -> list[dict]:
    """Join poem fragments and divide long passages using checked end anchors.

    Optional parallel-segments.json uses 1-based source paragraph numbers.
    """
    path = directory / "parallel-segments.json"
    split_config = json.loads(path.read_text(encoding="utf-8"))["paragraphs"] if path.exists() else {}
    verse_breaks = load_verse_breaks(directory, sources)
    units = []
    for index, (source, target) in enumerate(zip(sources, targets)):
        heading = bool(re.fullmatch(r"— [IVX]+ —|\[ *\d+ *\]|\*(?:\s+\*){2}", source))
        is_verse = target.startswith("    ")
        if is_verse and units and units[-1]["verse"] and index + 1 not in verse_breaks:
            units[-1]["source"] += "\n" + source
            units[-1]["target"] += "\n" + target
            units[-1]["paragraph_numbers"].append(index + 1)
            continue
        entry = split_config.get(str(index + 1))
        if entry:
            if heading:
                raise ValueError("Headings may not have reading splits")
            if is_verse:
                for text, anchors in ((source, entry["source_after"]), (target, entry["translation_after"])):
                    for anchor in anchors:
                        if text.count(anchor) != 1 or not text[text.index(anchor) + len(anchor):].startswith("\n"):
                            raise ValueError("A line-preserving split must end at a complete line")
            source_segments = split_after(source if is_verse else " ".join(source.split()), entry["source_after"])
            target_segments = split_after(target, entry["translation_after"])
            if len(source_segments) != len(target_segments):
                raise ValueError(f"Split count mismatch in paragraph {index + 1}")
        else:
            source_segments, target_segments = [source], [target]
        for segment_index, (source_segment, target_segment) in enumerate(zip(source_segments, target_segments)):
            units.append({"source": source_segment, "target": target_segment,
                          "heading": heading, "verse": is_verse,
                          "paragraph_numbers": [index + 1], "segment_index": segment_index})
    return units


def load_side_comments(directory: Path, units: list[dict]) -> dict:
    """Validate selective comments; omitted paragraphs and null segments are intentional."""
    path = directory / "side-comments.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema_version") != 2:
        raise ValueError("Unsupported side-comments.json schema version")
    for filename in ("original.txt", "translation.txt", "parallel-segments.json"):
        input_path = directory / filename
        actual = hashlib.sha256(input_path.read_bytes()).hexdigest() if input_path.exists() else None
        if filename not in data.get("input_sha256", {}) or data["input_sha256"][filename] != actual:
            raise ValueError(f"Side comments need review after changes to {filename}")
    expected = {}
    for unit in units:
        if not unit["heading"]:
            for number in unit["paragraph_numbers"]:
                expected[str(number)] = expected.get(str(number), 0) + 1
    comments = data.get("paragraphs", {})
    if not isinstance(comments, dict) or not set(comments).issubset(expected):
        raise ValueError("Side comments may refer only to non-heading source paragraphs")
    for number, values in comments.items():
        if not isinstance(values, list) or len(values) != expected[number]:
            raise ValueError(f"Side-comment segment count mismatch in paragraph {number}")
        if any(value is not None and (not isinstance(value, str) or not value.strip() or "【" in value or "】" in value)
               for value in values):
            raise ValueError(f"Empty or malformed side comment in paragraph {number}")
        if not any(values):
            raise ValueError(f"Omit entirely unannotated paragraph {number} instead of storing all nulls")
    return comments


def load_heading_paragraphs(directory: Path, sources: list[str]) -> set[int]:
    """Read explicitly checked in-chapter headings, such as Aeolus's headlines."""
    path = directory / "layout.json"
    if not path.exists():
        return set()
    values = json.loads(path.read_text(encoding="utf-8")).get("heading_paragraphs", [])
    if (not isinstance(values, list) or any(type(n) is not int or not 1 <= n <= len(sources) for n in values)
            or len(values) != len(set(values))):
        raise ValueError("Invalid or duplicate heading paragraph numbers in layout.json")
    return set(values)


def load_verse_breaks(directory: Path, sources: list[str]) -> set[int]:
    """Keep distinct neighbouring verse blocks separate when explicitly checked."""
    path = directory / "layout.json"
    if not path.exists():
        return set()
    values = json.loads(path.read_text(encoding="utf-8")).get("verse_group_break_before", [])
    if (not isinstance(values, list) or any(type(n) is not int or not 2 <= n <= len(sources) for n in values)
            or len(values) != len(set(values))):
        raise ValueError("Invalid or duplicate verse group breaks in layout.json")
    return set(values)


def load_paragraph_layout(directory: Path, sources: list[str], field: str) -> set[int]:
    """Read explicitly reviewed paragraph-level pagination choices."""
    path = directory / "layout.json"
    if not path.exists():
        return set()
    values = json.loads(path.read_text(encoding="utf-8")).get(field, [])
    maximum = len(sources) - (field == "keep_with_next_paragraphs")
    if (not isinstance(values, list)
            or any(type(n) is not int or not 1 <= n <= maximum for n in values)
            or len(values) != len(set(values))):
        raise ValueError(f"Invalid or duplicate {field} in layout.json")
    return set(values)


def accounting_table(content: str, style: ParagraphStyle, text_width: float, english: bool = False):
    """Set explicitly marked ledger lines with an aligned amount column."""
    ledger_style = ParagraphStyle("Ledger" + style.name, parent=style,
                                  leading=13.2 if english else 14.2,
                                  firstLineIndent=0, leftIndent=0, rightIndent=0,
                                  spaceBefore=0, spaceAfter=0)
    number_style = ParagraphStyle("LedgerAmount" + style.name, parent=ledger_style, alignment=2)
    amounts_width = 88
    rows, spans = [], []
    for line in content.splitlines():
        line = line.strip()
        match = re.fullmatch(r"(.*?)\s+([0-9]+—[0-9]+—[0-9]+)", line)
        if match:
            label, amount = match.groups()
        elif re.fullmatch(r"[0-9]+—[0-9]+—[0-9]+|—+|£\.\s*s\.\s*d\.|镑—先令—便士", line):
            label, amount = "", line
        else:
            label, amount = line, ""
            spans.append(len(rows))
        width = text_width if not amount else text_width - amounts_width
        formatted = escape(label) if english else markup(label, ledger_style, width)
        rows.append([Paragraph(formatted, ledger_style), Paragraph(escape(amount), number_style)])
    table = Table(rows, colWidths=[text_width - amounts_width, amounts_width], hAlign="LEFT")
    table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        *[("SPAN", (0, row), (1, row)) for row in spans],
    ]))
    table.spaceAfter = style.spaceAfter
    return table


def build_edition(chapter: int, directory: Path, sources: list[str], targets: list[str], edition: str) -> dict:
    parallel = edition in ("parallel", "commented")
    commented = edition == "commented"
    page_size = PAGE_SIZES[edition]
    frame_width = page_size[0] - 2 * MARGIN_X - 12
    text_width = (PAGE_SIZES["parallel"][0] - 2 * MARGIN_X - 12) if commented else frame_width
    comment_width = frame_width - text_width - COMMENT_GAP
    output = directory / f"chapter-{chapter:02d}-{edition}.pdf"
    edition_name = EDITION_NAMES[edition]
    body = ParagraphStyle(
        "Body", fontName="Song", fontSize=BODY_SIZE, leading=LEADING,
        firstLineIndent=2 * BODY_SIZE, spaceAfter=0 if parallel else 3.5,
        textColor=colors.HexColor("#171717"), alignment=TA_JUSTIFY,
        wordWrap="CJK", allowWidows=0, allowOrphans=0, splitLongWords=0, justifyBreaks=1,
    )
    verse = ParagraphStyle(
        "Verse", parent=body, firstLineIndent=0, leftIndent=2 * BODY_SIZE, rightIndent=BODY_SIZE,
        alignment=TA_LEFT, spaceBefore=2, spaceAfter=0 if parallel else 5,
    )
    english = ParagraphStyle(
        "English", fontName="English", fontSize=ENGLISH_SIZE, leading=ENGLISH_LEADING,
        leftIndent=2 * BODY_SIZE, textColor=colors.HexColor(ENGLISH_COLOR), alignment=TA_LEFT,
        spaceBefore=3, spaceAfter=8, allowWidows=0, allowOrphans=0, splitLongWords=0,
    )
    english_verse = ParagraphStyle("EnglishVerse", parent=english, spaceBefore=4, spaceAfter=9)
    newspaper_heading = ParagraphStyle(
        "NewspaperHeading", parent=body, firstLineIndent=0, alignment=TA_CENTER,
        spaceBefore=12, spaceAfter=4, keepWithNext=True,
    )
    english_heading = ParagraphStyle("EnglishHeading", parent=english, leftIndent=0,
                                     alignment=TA_CENTER, spaceAfter=7)
    comment_style = ParagraphStyle(
        "SideComment", fontName="Song", fontSize=COMMENT_SIZE, leading=COMMENT_LEADING,
        textColor=colors.HexColor(COMMENT_COLOR), alignment=TA_LEFT, wordWrap="CJK",
        firstLineIndent=0, splitLongWords=0,
    )
    part_style = ParagraphStyle(
        "Part", parent=body, alignment=TA_CENTER, firstLineIndent=0, fontSize=12,
        leading=18, spaceBefore=12, spaceAfter=3, keepWithNext=True,
    )
    chapter_style = ParagraphStyle("Chapter", parent=part_style, fontSize=15, leading=22, spaceBefore=0, spaceAfter=16)
    separator_style = ParagraphStyle("SectionSeparator", parent=part_style, spaceBefore=12, spaceAfter=12)
    title_style = ParagraphStyle("Title", parent=part_style, fontSize=21, leading=30, spaceBefore=0, spaceAfter=5)
    author_style = ParagraphStyle("Author", parent=part_style, fontSize=9, leading=14, spaceBefore=0, spaceAfter=4)
    edition_style = ParagraphStyle("Edition", parent=part_style, fontSize=8, leading=12, spaceBefore=0,
                                   spaceAfter=0, textColor=colors.HexColor("#777777"))
    story = [Paragraph("尤利西斯", title_style), Paragraph("詹姆斯·乔伊斯", author_style),
             Paragraph(edition_name, edition_style)]
    if parallel:
        units = aligned_units(directory, sources, targets)
    else:
        units = [{"source": source, "target": target, "verse": target.startswith("    "),
                  "paragraph_numbers": [number], "segment_index": 0}
                 for number, (source, target) in enumerate(zip(sources, targets), 1)]
    heading_paragraphs = load_heading_paragraphs(directory, sources)
    verse_breaks = load_verse_breaks(directory, sources)
    keep_with_next = load_paragraph_layout(directory, sources, "keep_with_next_paragraphs")
    zh_keep_together = load_paragraph_layout(directory, sources, "zh_keep_together_paragraphs")
    accounting_paragraphs = load_paragraph_layout(directory, sources, "accounting_paragraphs")
    comments = load_side_comments(directory, units) if commented else {}
    if commented:
        font = pdfmetrics.getFont("Song")
        comment_chars = set("".join(value for values in comments.values() for value in values if value))
        missing = sorted(c for c in comment_chars if not c.isspace() and ord(c) not in font.face.charWidths)
        if missing:
            raise ValueError(f"Song font lacks side-comment characters: {missing}")
    english_markup = EnglishMarkup()
    pairs = 0
    parallel_group = []
    for index, unit in enumerate(units):
        source, target, is_verse = unit["source"], unit["target"], unit["verse"]
        if re.fullmatch(r"— [IVX]+ —|\[ *\d+ *\]|\*(?:\s+\*){2}", source):
            if target != source:
                raise ValueError("Preserve the source's part/chapter markers verbatim")
            style = part_style if source.startswith("—") else separator_style if source.startswith("*") else chapter_style
            marker = Paragraph(escape(target), style)
            if parallel and source.startswith("*"):
                # A marker followed by a nested KeepTogether can otherwise be
                # stranded. Include it in the next flat bilingual group.
                if parallel_group:
                    story.append(KeepTogether(parallel_group))
                parallel_group = [marker]
            else:
                story.append(marker)
            continue
        content = "\n".join(line.strip() for line in target.splitlines())
        is_newspaper_heading = bool(heading_paragraphs.intersection(unit["paragraph_numbers"]))
        joins_next = (bool(keep_with_next.intersection(unit["paragraph_numbers"]))
                      and index + 1 < len(units)
                      and units[index + 1]["paragraph_numbers"][0] != unit["paragraph_numbers"][-1])
        introduces_next = (target.rstrip().endswith("：") and index + 1 < len(units)
                           and units[index + 1]["paragraph_numbers"][0] != unit["paragraph_numbers"][-1])
        if is_newspaper_heading and (is_verse or len(unit["paragraph_numbers"]) != 1
                                     or unit["segment_index"] != 0):
            raise ValueError("An in-chapter heading must be one unsplit prose paragraph")
        style = newspaper_heading if is_newspaper_heading else verse if is_verse else body
        is_accounting = bool(accounting_paragraphs.intersection(unit["paragraph_numbers"]))
        paragraph = (accounting_table(content, style, text_width) if is_accounting
                     else ChapterParagraph(markup(content, style, text_width), style))
        # Martha's closing is grammatically completed by her signature in the
        # next source paragraph; do not strand that signature on a new page.
        joins_signature = (source.rstrip().endswith("your longing")
                           and index + 1 < len(units)
                           and units[index + 1]["source"].strip() == "Martha")
        if parallel:
            en_style = english_heading if is_newspaper_heading else english_verse if is_verse else english
            en_paragraph = (accounting_table(source, en_style, text_width, english=True) if is_accounting
                            else Paragraph(english_markup.format(source, is_verse), en_style))
            if commented:
                side_text = "\n".join(value for number in unit["paragraph_numbers"]
                                      if str(number) in comments
                                      if (value := comments[str(number)][unit["segment_index"]]))
                side = Paragraph(markup(side_text, comment_style, comment_width), comment_style) if side_text else ""
                row = Table([[[paragraph, en_paragraph], "", side]],
                            colWidths=[text_width, COMMENT_GAP, comment_width], hAlign="LEFT")
                row.setStyle(TableStyle([
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 0),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                    ("TOPPADDING", (0, 0), (-1, -1), 0),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                ]))
                row.spaceAfter = 8
                parallel_group.append(row)
            else:
                paragraph.keepWithNext = True
                parallel_group.extend([paragraph, en_paragraph])
            # Flatten linked pairs: KeepTogether nested inside another
            # KeepTogether does not reliably preserve an introductory colon.
            if (not introduces_next
                    and not joins_signature and not is_newspaper_heading and not joins_next):
                story.append(KeepTogether(parallel_group))
                parallel_group = []
            pairs += 1
        else:
            paragraph.is_verse = is_verse
            paragraph.verse_group_start = unit["paragraph_numbers"][0] in verse_breaks
            paragraph.keep_whole = bool(zh_keep_together.intersection(unit["paragraph_numbers"]))
            if introduces_next or joins_signature or is_newspaper_heading or joins_next:
                paragraph.keepWithNext = True
            if (is_verse and index + 1 < len(units) and units[index + 1]["verse"]
                    and units[index + 1]["paragraph_numbers"][0] not in verse_breaks):
                paragraph.keepWithNext = True
                paragraph.spaceAfter = 0
            story.append(paragraph)
    if parallel_group:
        story.append(KeepTogether(parallel_group))
    if english_markup.italic:
        raise ValueError("Unbalanced Gutenberg italic markers")
    if not parallel:
        grouped_story = []
        index = 0
        while index < len(story):
            if getattr(story[index], "is_verse", False):
                stanzas = []
                if grouped_story and getattr(grouped_story[-1], "keepWithNext", False):
                    stanzas.append(grouped_story.pop())
                block_start = index
                while (index < len(story) and getattr(story[index], "is_verse", False)
                       and (index == block_start or not getattr(story[index], "verse_group_start", False))):
                    stanzas.append(story[index])
                    index += 1
                grouped_story.append(KeepTogether(stanzas))
            else:
                if getattr(story[index], "keep_whole", False):
                    grouped_story.append(KeepTogether([story[index]]))
                else:
                    grouped_story.append(story[index])
                index += 1
        story = grouped_story
    page_numbers = []

    def decorate(canvas, document):
        canvas.saveState()
        canvas.setTitle(f"尤利西斯 · 第{chapter}章（{edition_name}）")
        canvas.setAuthor("詹姆斯·乔伊斯")
        canvas.setSubject("中文宋体，8磅淡红夹注；" + ("逐段英文对照，Georgia字体" if parallel else "中文译稿"))
        canvas.setFont("Song", 8)
        canvas.setFillColor(colors.HexColor("#5a5a5a"))
        if document.page > 1:
            canvas.drawString(MARGIN_X, page_size[1] - 12.5 * mm, f"尤利西斯  /  第{chapter}章  /  {edition_name}")
            canvas.setStrokeColor(colors.HexColor("#b8b8b8"))
            canvas.setLineWidth(0.25)
            canvas.line(MARGIN_X, page_size[1] - 15.1 * mm, page_size[0] - MARGIN_X, page_size[1] - 15.1 * mm)
        else:
            canvas.bookmarkPage("chapter")
            canvas.addOutlineEntry(f"第{chapter}章", "chapter", level=0)
        if commented:
            divider_x = MARGIN_X + 6 + text_width + COMMENT_GAP / 2
            canvas.setStrokeColor(colors.HexColor("#D8E2DF"))
            canvas.setLineWidth(0.4)
            canvas.line(divider_x, BOTTOM_MARGIN + 6, divider_x,
                        page_size[1] - TOP_MARGIN - (100 if document.page == 1 else 0))
        canvas.drawCentredString(page_size[0] / 2, 10.5 * mm, str(document.page))
        page_numbers.append(document.page)
        canvas.restoreState()

    doc = SimpleDocTemplate(str(output), pagesize=page_size, leftMargin=MARGIN_X, rightMargin=MARGIN_X,
                            topMargin=TOP_MARGIN, bottomMargin=BOTTOM_MARGIN, pageCompression=1)
    doc.build(story, onFirstPage=decorate, onLaterPages=decorate)
    return {"output": str(output), "pages": len(page_numbers), "reading_pairs": pairs if parallel else None,
            "side_comments": sum(bool(value) for values in comments.values() for value in values) if commented else None}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("chapter", type=int, choices=range(1, 19))
    parser.add_argument("--edition", choices=["both", "zh", "parallel", "commented"], default="both")
    parser.add_argument("--font", type=Path, default=Path(os.environ.get("ULYSSES_SONG_FONT", "C:/Windows/Fonts/simsun.ttc")))
    parser.add_argument("--english-font", type=Path, default=Path(os.environ.get("ULYSSES_ENGLISH_FONT", "C:/Windows/Fonts/georgia.ttf")))
    parser.add_argument("--english-italic-font", type=Path, default=Path(os.environ.get("ULYSSES_ENGLISH_ITALIC_FONT", "C:/Windows/Fonts/georgiai.ttf")))
    parser.add_argument("--symbol-font", type=Path, default=Path(os.environ.get("ULYSSES_SYMBOL_FONT", "C:/Windows/Fonts/seguisym.ttf")))
    parser.add_argument("--mark-font", type=Path, default=Path(os.environ.get("ULYSSES_MARK_FONT", "C:/Windows/Fonts/times.ttf")))
    args = parser.parse_args()
    directory = ROOT / "chapters" / f"{args.chapter:02d}"
    original, translation = directory / "original.txt", directory / "translation.txt"
    source_bytes, translation_bytes = original.read_bytes(), translation.read_bytes()
    source_paragraphs = publication_sources(directory, paragraphs(source_bytes.decode("utf-8")))
    translated_paragraphs = paragraphs(translation_bytes.decode("utf-8"))
    if len(source_paragraphs) != len(translated_paragraphs):
        raise ValueError(f"Paragraph mismatch: source={len(source_paragraphs)}, translation={len(translated_paragraphs)}")
    text = translation_bytes.decode("utf-8")
    required_symbols = SYMBOL_CHARACTERS.intersection(text + source_bytes.decode("utf-8"))
    for name, path in (("TextSymbols", args.symbol_font), ("TextMarks", args.mark_font)):
        characters = {c for c in required_symbols if GLYPH_FONTS[c] == name}
        if characters:
            glyph_font = TTFont(name, str(path))
            pdfmetrics.registerFont(glyph_font)
            pdfmetrics.registerFontFamily(name, normal=name, bold=name, italic=name, boldItalic=name)
            if any(ord(c) not in glyph_font.face.charWidths for c in characters):
                raise ValueError(f"{name} font lacks characters: {sorted(characters)}")
    if text.count("【") != text.count("】") or text.count("【注：") != len(NOTE.findall(text)):
        raise ValueError("Unbalanced or malformed inline notes")
    font = TTFont("Song", str(args.font), subfontIndex=0)
    pdfmetrics.registerFont(font)
    pdfmetrics.registerFontFamily("Song", normal="Song", bold="Song", italic="Song", boldItalic="Song")
    required_characters = set(note_text(text) + "尤利西斯詹姆斯·乔伊斯中文译本中英对照本旁注导读第章0123456789 / ")
    missing = sorted(c for c in required_characters if not c.isspace() and c not in SYMBOL_CHARACTERS
                     and ord(c) not in font.face.charWidths)
    if missing:
        raise ValueError(f"Song font lacks characters: {missing}")
    if args.edition != "zh":
        for name, path in [("English", args.english_font), ("EnglishItalic", args.english_italic_font)]:
            en_font = TTFont(name, str(path))
            pdfmetrics.registerFont(en_font)
            missing = sorted(c for c in set(source_bytes.decode("utf-8")) if not c.isspace()
                             and c not in SYMBOL_CHARACTERS and ord(c) not in en_font.face.charWidths)
            if missing:
                raise ValueError(f"{name} font lacks characters: {missing}")
        pdfmetrics.registerFontFamily("English", normal="English", italic="EnglishItalic", bold="English", boldItalic="EnglishItalic")
    editions = ["zh", "parallel"] if args.edition == "both" else [args.edition]
    results = [build_edition(args.chapter, directory, source_paragraphs, translated_paragraphs, edition) for edition in editions]
    if original.read_bytes() != source_bytes or translation.read_bytes() != translation_bytes:
        raise RuntimeError("Input files changed during PDF generation")
    print(json.dumps({"editions": results, "paragraphs_including_headings": len(translated_paragraphs),
        "inline_notes": len(NOTE.findall(text)), "font": str(args.font),
        "body_pt": BODY_SIZE, "note_pt": NOTE_SIZE, "note_color": NOTE_COLOR,
        "english_pt": ENGLISH_SIZE, "english_color": ENGLISH_COLOR,
        "source_sha256": hashlib.sha256(source_bytes).hexdigest(),
        "translation_sha256": hashlib.sha256(translation_bytes).hexdigest(),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
