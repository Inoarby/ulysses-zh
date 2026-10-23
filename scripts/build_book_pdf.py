"""Assemble the reviewed chapter PDFs without reflowing their text.

Usage: python scripts/build_book_pdf.py [--edition both|zh|parallel]
Requires reportlab and pypdf. Chapter inputs are never modified. The only
change to a chapter page is its existing footer's number and centred position.
"""

from __future__ import annotations

import argparse
from datetime import date
from decimal import Decimal
import hashlib
from io import BytesIO
import json
import os
from pathlib import Path
import re
from xml.sax.saxutils import escape

from pypdf import PdfReader, PdfWriter
from pypdf.annotations import Link
from pypdf.constants import PageLabelStyle
from pypdf.generic import DecodedStreamObject, NameObject, TextStringObject
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

from build_chapter_pdf import markup as chinese_markup


ROOT = Path(__file__).resolve().parent.parent
FRONT_PAGES = 3
PAGE_SIZES = {"zh": (152 * mm, 228 * mm), "parallel": (170 * mm, 240 * mm)}
EDITION_NAMES = {"zh": "中文译本", "parallel": "中英对照本"}
PARTS = ((1, "第一部", 1, 3), (2, "第二部", 4, 15), (3, "第三部", 16, 18))
INK = colors.HexColor("#303438")
MUTED = colors.HexColor("#65717A")
RULE = colors.HexColor("#CDD1D4")
FOOTER = re.compile(
    rb"BT 1 0 0 1 (?P<x>-?[\d.]+) (?P<y>-?[\d.]+) Tm "
    rb"(?P<font>/\S+) 8 Tf 9\.6 TL \((?P<number>\d+)\) Tj T\* ET"
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def renumber_page(page, local_number: int, book_number: int) -> bytes:
    """Return a content stream with only its verified footer changed."""
    contents = page.get_contents()
    if contents is None:
        raise ValueError("Chapter page has no content stream")
    data = contents.get_data()
    matches = [match for match in FOOTER.finditer(data)
               if abs(float(match["y"]) - 10.5 * mm) < 0.00001]
    if len(matches) != 1 or int(matches[0]["number"]) != local_number:
        raise ValueError(f"Unexpected footer on chapter page {local_number}")
    match = matches[0]
    font = page["/Resources"]["/Font"][match["font"].decode()].get_object()
    widths, first = font["/Widths"], int(font["/FirstChar"])

    def width(number: bytes) -> Decimal:
        return sum((Decimal(str(widths[c - first])) for c in number), Decimal(0)) * Decimal("0.008")

    new_number = str(book_number).encode("ascii")
    new_x = Decimal(match["x"].decode()) + (width(match["number"]) - width(new_number)) / 2
    x_text = format(new_x.normalize(), "f").encode("ascii")
    # Work backwards so the original byte offsets remain valid.
    for group, replacement in (("number", new_number), ("x", x_text)):
        data = data[:match.start(group)] + replacement + data[match.end(group):]
    return data


def folio(c, size, number: str) -> None:
    c.setFillColor(colors.HexColor("#5A5A5A"))
    c.setFont("Song", 8)
    c.drawCentredString(size[0] / 2, 10.5 * mm, number)


def front_matter(edition: str, chapters: list[dict], body_pages: int, version: str):
    size = PAGE_SIZES[edition]
    width, height = size
    left, right = 20 * mm, width - 20 * mm
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=size, pageCompression=1, invariant=1)

    c.setFillColor(MUTED)
    c.setFont("Song", 10)
    c.drawCentredString(width / 2, height - 34 * mm, "中文重译与夹注")
    c.setStrokeColor(RULE)
    c.setLineWidth(0.6)
    c.line(left, height - 43 * mm, right, height - 43 * mm)
    c.setFillColor(INK)
    c.setFont("Song", 31)
    c.drawCentredString(width / 2, height - 70 * mm, "尤利西斯")
    c.setFont("BookEnglish", 21)
    c.drawCentredString(width / 2, height - 85 * mm, "Ulysses")
    c.setFont("Song", 12)
    c.drawCentredString(width / 2, height - 107 * mm, "詹姆斯·乔伊斯")
    c.setFont("BookEnglish", 10)
    c.drawCentredString(width / 2, height - 115 * mm, "James Joyce")
    c.setFont("Song", 12)
    c.drawCentredString(width / 2, height - 141 * mm, EDITION_NAMES[edition] + " · 合订本")
    c.setFillColor(MUTED)
    c.setFont("Song", 10)
    c.drawCentredString(width / 2, height - 154 * mm, "第一部 · 第二部 · 第三部")
    c.drawCentredString(width / 2, 39 * mm, "十八章逐章复审本")
    c.setFont("BookEnglish", 9)
    c.drawCentredString(width / 2, 29 * mm, version)
    folio(c, size, "i")
    c.showPage()

    c.setFillColor(INK)
    c.setFont("Song", 18)
    c.drawString(left, height - 27 * mm, "版本与来源")
    note_style = ParagraphStyle("Notice", fontName="Song", fontSize=9.5,
                                leading=14, textColor=INK, wordWrap="CJK")
    link_style = ParagraphStyle("NoticeLink", fontName="BookEnglish", fontSize=8,
                                leading=11, textColor=MUTED)
    notices = [
        (f"《尤利西斯 · 中文重译与夹注》{EDITION_NAMES[edition]}合订本<br/>版本：{version}", False),
        ("本书汇集已逐章复审的十八章，保留各章正文、夹注及版式，统一连续页码，增设目录与书签。项目使用 AI 辅助翻译、核典与排版，译稿持续校订。", False),
        ("第 15、18 章涉及明确未成年人物的少量露骨性细节，在出版稿中作非露骨概述，中英文均以编者标记明示。本书不作为无删节译本；原始底本文件保持不动。", False),
        ("原著：James Joyce，Ulysses。英文底本为 Project Gutenberg eBook #4300，电子文本制作署名 Col Choat，所用底本更新于 2025-11-27。底本标示为 Public domain in the USA；完整许可附于书末。", False),
        ('<link href="https://www.gutenberg.org/ebooks/4300">https://www.gutenberg.org/ebooks/4300</link>', True),
        ("新增中文译文、夹注及说明由 Inoarby 与 ulysses-zh 项目贡献者按 CC BY-SA 4.0 提供：保留署名及链接、注明修改，并以相同许可分享改编成果。", False),
        ('<link href="https://creativecommons.org/licenses/by-sa/4.0/">https://creativecommons.org/licenses/by-sa/4.0/</link>', True),
        ("原文、第三方引文与嵌入字体保留各自权利，不纳入上述许可。宋体、Georgia 等字体仅以显示所需的子集嵌入。", False),
        ("可编辑译稿、各章校译记录、构建脚本及完整来源说明见项目仓库。本项目与 Project Gutenberg 无隶属或背书关系。", False),
        ('<link href="https://github.com/Inoarby/ulysses-zh">https://github.com/Inoarby/ulysses-zh</link>', True),
        ("Copyright © 2026 Inoarby and contributors.", True),
    ]
    y = height - 38 * mm
    for text, is_link in notices:
        if not is_link:
            text = chinese_markup(text.replace("<br/>", "\n"), note_style, right - left)
        p = Paragraph(text, link_style if is_link else note_style)
        _, paragraph_height = p.wrap(right - left, height)
        y -= paragraph_height
        if y < 23 * mm:
            raise ValueError("Edition notice does not fit its page")
        p.drawOn(c, left, y)
        y -= 7 if not is_link else 8
    folio(c, size, "ii")
    c.showPage()

    c.setFillColor(INK)
    c.setFont("Song", 18)
    c.drawString(left, height - 27 * mm, "目录")
    c.setFont("Song", 8)
    c.setFillColor(MUTED)
    c.drawRightString(right, height - 27 * mm, "点击章节跳转")
    y = height - 41 * mm
    links = []
    for _, part_name, first, last in PARTS:
        c.setFillColor(MUTED)
        c.setFont("Song", 10)
        c.drawString(left, y, part_name)
        y -= 21
        for chapter in chapters[first - 1:last]:
            c.setFillColor(INK)
            c.setFont("Song", 10.5)
            c.drawString(left + 6 * mm, y, f"第 {chapter['chapter']} 章")
            c.setFont("BookEnglish", 9.5)
            c.drawRightString(right, y, str(chapter["body_start"]))
            links.append(((left, y - 4, right, y + 12), chapter["pdf_start"] - 1))
            y -= 18
        y -= 9
    c.setStrokeColor(RULE)
    c.line(left, y + 3, right, y + 3)
    y -= 18
    c.setFont("Song", 10)
    c.setFillColor(INK)
    c.drawString(left, y, "底本附记与许可")
    c.setFont("BookEnglish", 9.5)
    c.drawRightString(right, y, str(body_pages + 1))
    links.append(((left, y - 4, right, y + 12), FRONT_PAGES + body_pages))
    if y < 23 * mm:
        raise ValueError("Contents does not fit its page")
    folio(c, size, "iii")
    c.save()
    buffer.seek(0)
    return PdfReader(buffer), links


def license_appendix(edition: str, body_pages: int) -> PdfReader:
    size = PAGE_SIZES[edition]
    buffer = BytesIO()
    document = SimpleDocTemplate(buffer, pagesize=size, leftMargin=18 * mm,
                                 rightMargin=18 * mm, topMargin=22 * mm,
                                 bottomMargin=21 * mm, pageCompression=1,
                                 invariant=1)
    heading = ParagraphStyle("AppendixHeading", fontName="Song", fontSize=16,
                             leading=22, spaceAfter=14, textColor=INK)
    english = ParagraphStyle("License", fontName="BookEnglish", fontSize=9,
                             leading=12.5, spaceAfter=7, textColor=INK,
                             allowWidows=0, allowOrphans=0)
    section = ParagraphStyle("LicenseSection", parent=english, keepWithNext=True)
    source = (ROOT / "chapters/back-matter.txt").read_text(encoding="utf-8")
    story = [Paragraph("底本附记与许可", heading), Spacer(1, 4)]
    for paragraph in re.split(r"\n\s*\n", source.strip()):
        text = " ".join(paragraph.split())
        if text:
            style = section if re.match(r"^(Section \d+\.|1\.F\.$|START:|THE FULL|PLEASE READ)", text) else english
            story.append(Paragraph(escape(text), style))

    def decorate(c, doc):
        c.saveState()
        if doc.page > 1:
            c.setFont("Song", 8)
            c.setFillColor(MUTED)
            c.drawString(18 * mm, size[1] - 12.5 * mm, "底本附记与许可")
            c.setStrokeColor(RULE)
            c.setLineWidth(0.4)
            c.line(18 * mm, size[1] - 15.1 * mm, size[0] - 18 * mm, size[1] - 15.1 * mm)
        folio(c, size, str(body_pages + doc.page))
        c.restoreState()

    document.build(story, onFirstPage=decorate, onLaterPages=decorate)
    buffer.seek(0)
    return PdfReader(buffer)


def build(edition: str, output_dir: Path, version: str) -> dict:
    chapters, readers, body_pages = [], [], 0
    for number in range(1, 19):
        path = ROOT / f"chapters/{number:02}/chapter-{number:02}-{edition}.pdf"
        reader = PdfReader(path, strict=True)
        if reader.is_encrypted or not len(reader.pages):
            raise ValueError(f"Invalid chapter input: {path}")
        chapters.append({"chapter": number, "path": path.relative_to(ROOT).as_posix(),
                         "sha256": sha256(path), "pages": len(reader.pages),
                         "body_start": body_pages + 1,
                         "pdf_start": FRONT_PAGES + body_pages + 1})
        readers.append(reader)
        body_pages += len(reader.pages)

    front, links = front_matter(edition, chapters, body_pages, version)
    appendix = license_appendix(edition, body_pages)
    writer = PdfWriter()
    for page in front.pages:
        writer.add_page(page)
    for chapter, reader in zip(chapters, readers):
        for local_number, source_page in enumerate(reader.pages, 1):
            if source_page.rotation or source_page.get("/Annots"):
                raise ValueError("Unexpected rotation or annotations in chapter input")
            if any(abs(float(a) - b) > 0.001 for a, b in
                   zip((source_page.mediabox.width, source_page.mediabox.height), PAGE_SIZES[edition])):
                raise ValueError("Unexpected chapter page dimensions")
            new_data = renumber_page(source_page, local_number, chapter["body_start"] + local_number - 1)
            page = writer.add_page(source_page)
            stream = DecodedStreamObject()
            stream.set_data(new_data)
            page.replace_contents(stream.flate_encode())
        print(f"{edition}: added chapter {chapter['chapter']:02} ({chapter['pages']} pages)", flush=True)
    for page in appendix.pages:
        writer.add_page(page)

    writer.add_outline_item("扉页", 0)
    writer.add_outline_item("版本与来源", 1)
    writer.add_outline_item("目录", 2)
    for _, name, first, last in PARTS:
        parent = writer.add_outline_item(name, chapters[first - 1]["pdf_start"] - 1)
        for chapter in chapters[first - 1:last]:
            writer.add_outline_item(f"第 {chapter['chapter']} 章", chapter["pdf_start"] - 1, parent=parent)
    writer.add_outline_item("底本附记与许可", FRONT_PAGES + body_pages)
    for rect, target in links:
        annotation = writer.add_annotation(2, Link(rect=rect, target_page_index=target, border=[0, 0, 0]))
        # Local explicit destinations require page references. pypdf 6.10's
        # Link helper otherwise leaves the zero-based integer in this array.
        annotation["/Dest"][0] = writer.pages[target].indirect_reference
    writer.set_page_label(0, FRONT_PAGES - 1, style=PageLabelStyle.LOWERCASE_ROMAN, start=1)
    writer.set_page_label(FRONT_PAGES, len(writer.pages) - 1, style=PageLabelStyle.DECIMAL, start=1)
    writer.page_mode = "/UseOutlines"
    writer.page_layout = "/OneColumn"
    writer.root_object[NameObject("/Lang")] = TextStringObject("zh-CN")
    writer.add_metadata({"/Title": f"尤利西斯 · {EDITION_NAMES[edition]}合订本",
                         "/Author": "James Joyce; Inoarby 与 ulysses-zh 项目贡献者",
                         "/Subject": f"十八章逐章复审本；版本 {version}；含编者处理说明",
                         "/Creator": "ulysses-zh / scripts/build_book_pdf.py"})
    path = output_dir / f"ulysses-{edition}.pdf"
    temporary = path.with_suffix(".pdf.tmp")
    try:
        with temporary.open("wb") as output:
            writer.write(output)
        result = PdfReader(temporary, strict=True)
        expected_pages = FRONT_PAGES + body_pages + len(appendix.pages)
        if len(result.pages) != expected_pages or len(result.pages[2]["/Annots"]) != 19:
            raise ValueError("Compiled book failed page/navigation validation")
        for annotation, (_, target) in zip(result.pages[2]["/Annots"], links):
            if annotation.get_object()["/Dest"][0] != result.pages[target].indirect_reference:
                raise ValueError("Contents link does not resolve to the expected page")
        for chapter in chapters:
            input_path = ROOT / chapter["path"]
            if sha256(input_path) != chapter["sha256"]:
                raise ValueError(f"Input changed during assembly: {input_path}")
        # PdfReader may hold the file open on Windows; release it before rename.
        result.close()
        temporary.replace(path)
    finally:
        writer.close()
        for reader in readers:
            reader.close()
    print(f"Created {path}: {expected_pages} pages", flush=True)
    return {"path": path.name, "sha256": sha256(path), "bytes": path.stat().st_size,
            "front_pages": FRONT_PAGES, "body_pages": body_pages,
            "appendix_pages": len(appendix.pages), "total_pages": expected_pages,
            "appendix_pdf_start": FRONT_PAGES + body_pages + 1,
            "chapters": chapters}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--edition", choices=("both", "zh", "parallel"), default="both")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "output/pdf")
    parser.add_argument("--date", type=date.fromisoformat, default=date.today())
    parser.add_argument("--font", type=Path, default=Path(os.environ.get("ULYSSES_SONG_FONT", "C:/Windows/Fonts/simsun.ttc")))
    parser.add_argument("--english-font", type=Path, default=Path(os.environ.get("ULYSSES_ENGLISH_FONT", "C:/Windows/Fonts/georgia.ttf")))
    args = parser.parse_args()
    pdfmetrics.registerFont(TTFont("Song", str(args.font), subfontIndex=0))
    pdfmetrics.registerFont(TTFont("BookEnglish", str(args.english_font)))
    args.output_dir.mkdir(parents=True, exist_ok=True)
    editions = ("zh", "parallel") if args.edition == "both" else (args.edition,)
    manifest = {"schema_version": 1, "version_date": args.date.isoformat(),
                "assembly": "Existing chapter page streams and resources; only centred footer numbers changed",
                "page_indices": "pdf_start and appendix_pdf_start are 1-based; body_start is the printed Arabic folio",
                "back_matter_sha256": sha256(ROOT / "chapters/back-matter.txt"),
                "books": {}}
    for edition in editions:
        manifest["books"][edition] = build(edition, args.output_dir, args.date.isoformat())
    # A single-edition build gets its own manifest, avoiding stale claims about the other book.
    manifest_name = "whole-book-manifest.json" if args.edition == "both" else f"whole-book-{args.edition}-manifest.json"
    (args.output_dir / manifest_name).write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
