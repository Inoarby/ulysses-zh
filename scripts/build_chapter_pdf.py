"""Build Chinese and paragraph-aligned bilingual chapter PDFs.

Usage: python scripts/build_chapter_pdf.py 01 [--edition both|zh|parallel]
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
from reportlab.platypus import KeepTogether, Paragraph, SimpleDocTemplate


ROOT = Path(__file__).resolve().parent.parent
NOTE = re.compile(r"(【注：[^】]*】)")
BODY_SIZE, NOTE_SIZE, LEADING = 10.5, 8, 16.3
ENGLISH_SIZE, ENGLISH_LEADING = 9.5, 13.7
NOTE_COLOR, ENGLISH_COLOR = "#A66F73", "#929CA6"
PAGE_SIZES = {"zh": (152 * mm, 228 * mm), "parallel": (170 * mm, 240 * mm)}
EDITION_NAMES = {"zh": "中文译本", "parallel": "中英对照本"}
MARGIN_X, TOP_MARGIN, BOTTOM_MARGIN = 18 * mm, 20 * mm, 19 * mm
TOKEN = re.compile(r"[A-Za-zÀ-ÖØ-öø-ÿ]+(?:[.’'-][A-Za-zÀ-ÖØ-öø-ÿ]+)*\.?|[0-9]+(?:\.[0-9]+)*|——|……|\s+|.")
NO_START = set("，。！？；：、）》】〉〕』」”’,.!?;:%％·")
NO_END = set("（《【〈〔『「“‘·")


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


def note_text(text: str) -> str:
    """Visible text; labels and brackets are internal source markup only."""
    return NOTE.sub(lambda m: m.group(0)[3:-1], text)


def markup(text: str, style: ParagraphStyle, text_width: float) -> str:
    """Set explicit legal CJK breaks across mixed-size font fragments."""
    lines = []
    for hard_line in text.splitlines():
        tokens = []
        for part in NOTE.split(hard_line):
            is_note = part.startswith("【注：")
            if is_note:
                part = " " + part[3:-1] + " "
            size = NOTE_SIZE if is_note else BODY_SIZE
            for token in TOKEN.findall(part):
                tokens.append((token, is_note, pdfmetrics.stringWidth(token, "Song", size)))
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
                value = escape(value)
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
            result.append(escape(part).replace("\n", "<br/>"))
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
    units = []
    for index, (source, target) in enumerate(zip(sources, targets)):
        heading = bool(re.fullmatch(r"— [IVX]+ —|\[ *\d+ *\]", source))
        is_verse = target.startswith("    ")
        if is_verse and units and units[-1]["verse"]:
            units[-1]["source"] += "\n" + source
            units[-1]["target"] += "\n" + target
            continue
        entry = split_config.get(str(index + 1))
        if entry:
            if heading or is_verse:
                raise ValueError("Only prose paragraphs may have reading splits")
            source_segments = split_after(" ".join(source.split()), entry["source_after"])
            target_segments = split_after(target, entry["translation_after"])
            if len(source_segments) != len(target_segments):
                raise ValueError(f"Split count mismatch in paragraph {index + 1}")
        else:
            source_segments, target_segments = [source], [target]
        for source_segment, target_segment in zip(source_segments, target_segments):
            units.append({"source": source_segment, "target": target_segment,
                          "heading": heading, "verse": is_verse})
    return units


def build_edition(chapter: int, directory: Path, sources: list[str], targets: list[str], edition: str) -> dict:
    parallel = edition == "parallel"
    page_size = PAGE_SIZES[edition]
    text_width = page_size[0] - 2 * MARGIN_X - 12
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
    part_style = ParagraphStyle(
        "Part", parent=body, alignment=TA_CENTER, firstLineIndent=0, fontSize=12,
        leading=18, spaceBefore=12, spaceAfter=3, keepWithNext=True,
    )
    chapter_style = ParagraphStyle("Chapter", parent=part_style, fontSize=15, leading=22, spaceBefore=0, spaceAfter=16)
    title_style = ParagraphStyle("Title", parent=part_style, fontSize=21, leading=30, spaceBefore=0, spaceAfter=5)
    author_style = ParagraphStyle("Author", parent=part_style, fontSize=9, leading=14, spaceBefore=0, spaceAfter=4)
    edition_style = ParagraphStyle("Edition", parent=part_style, fontSize=8, leading=12, spaceBefore=0,
                                   spaceAfter=0, textColor=colors.HexColor("#777777"))
    story = [Paragraph("尤利西斯", title_style), Paragraph("詹姆斯·乔伊斯", author_style),
             Paragraph(edition_name, edition_style)]
    if parallel:
        units = aligned_units(directory, sources, targets)
    else:
        units = [{"source": source, "target": target, "verse": target.startswith("    ")}
                 for source, target in zip(sources, targets)]
    english_markup = EnglishMarkup()
    pairs = 0
    parallel_group = []
    for index, unit in enumerate(units):
        source, target, is_verse = unit["source"], unit["target"], unit["verse"]
        if re.fullmatch(r"— [IVX]+ —|\[ *\d+ *\]", source):
            if target != source:
                raise ValueError("Preserve the source's part/chapter markers verbatim")
            style = part_style if source.startswith("—") else chapter_style
            story.append(Paragraph(escape(target), style))
            continue
        content = "\n".join(line.strip() for line in target.splitlines())
        style = verse if is_verse else body
        paragraph = ChapterParagraph(markup(content, style, text_width), style)
        if parallel:
            en_style = english_verse if is_verse else english
            en_paragraph = Paragraph(english_markup.format(source, is_verse), en_style)
            paragraph.keepWithNext = True
            parallel_group.extend([paragraph, en_paragraph])
            # Flatten linked pairs: KeepTogether nested inside another
            # KeepTogether does not reliably preserve an introductory colon.
            if not target.rstrip().endswith("：") and index != len(units) - 2:
                story.append(KeepTogether(parallel_group))
                parallel_group = []
            pairs += 1
        else:
            paragraph.is_verse = is_verse
            if target.rstrip().endswith("：") or index == len(units) - 2:
                paragraph.keepWithNext = True
            if is_verse and index + 1 < len(units) and units[index + 1]["verse"]:
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
                while index < len(story) and getattr(story[index], "is_verse", False):
                    stanzas.append(story[index])
                    index += 1
                grouped_story.append(KeepTogether(stanzas))
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
        canvas.drawCentredString(page_size[0] / 2, 10.5 * mm, str(document.page))
        page_numbers.append(document.page)
        canvas.restoreState()

    doc = SimpleDocTemplate(str(output), pagesize=page_size, leftMargin=MARGIN_X, rightMargin=MARGIN_X,
                            topMargin=TOP_MARGIN, bottomMargin=BOTTOM_MARGIN, pageCompression=1)
    doc.build(story, onFirstPage=decorate, onLaterPages=decorate)
    return {"output": str(output), "pages": len(page_numbers), "reading_pairs": pairs if parallel else None}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("chapter", type=int, choices=range(1, 19))
    parser.add_argument("--edition", choices=["both", "zh", "parallel"], default="both")
    parser.add_argument("--font", type=Path, default=Path(os.environ.get("ULYSSES_SONG_FONT", "C:/Windows/Fonts/simsun.ttc")))
    parser.add_argument("--english-font", type=Path, default=Path(os.environ.get("ULYSSES_ENGLISH_FONT", "C:/Windows/Fonts/georgia.ttf")))
    parser.add_argument("--english-italic-font", type=Path, default=Path(os.environ.get("ULYSSES_ENGLISH_ITALIC_FONT", "C:/Windows/Fonts/georgiai.ttf")))
    args = parser.parse_args()
    directory = ROOT / "chapters" / f"{args.chapter:02d}"
    original, translation = directory / "original.txt", directory / "translation.txt"
    source_bytes, translation_bytes = original.read_bytes(), translation.read_bytes()
    source_paragraphs = paragraphs(source_bytes.decode("utf-8"))
    translated_paragraphs = paragraphs(translation_bytes.decode("utf-8"))
    if len(source_paragraphs) != len(translated_paragraphs):
        raise ValueError(f"Paragraph mismatch: source={len(source_paragraphs)}, translation={len(translated_paragraphs)}")
    text = translation_bytes.decode("utf-8")
    if text.count("【") != text.count("】") or text.count("【注：") != len(NOTE.findall(text)):
        raise ValueError("Unbalanced or malformed inline notes")
    font = TTFont("Song", str(args.font), subfontIndex=0)
    pdfmetrics.registerFont(font)
    pdfmetrics.registerFontFamily("Song", normal="Song", bold="Song", italic="Song", boldItalic="Song")
    required_characters = set(note_text(text) + "尤利西斯詹姆斯·乔伊斯中文译本中英对照本第章0123456789 / ")
    missing = sorted(c for c in required_characters if not c.isspace() and ord(c) not in font.face.charWidths)
    if missing:
        raise ValueError(f"Song font lacks characters: {missing}")
    if args.edition != "zh":
        for name, path in [("English", args.english_font), ("EnglishItalic", args.english_italic_font)]:
            en_font = TTFont(name, str(path))
            pdfmetrics.registerFont(en_font)
            missing = sorted(c for c in set(source_bytes.decode("utf-8")) if not c.isspace() and ord(c) not in en_font.face.charWidths)
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
