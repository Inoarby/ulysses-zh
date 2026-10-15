"""Verify generated PDF text, embedded fonts, page bounds and bilingual alignment.

Usage: python scripts/verify_chapter_pdf.py 01 [--edition zh|parallel|commented|all]
Requires pdfplumber and pypdf. This does not replace semantic or rendered-page review.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re

import pdfplumber
from pypdf import PdfReader

from build_chapter_pdf import SYMBOL_CHARACTERS, aligned_units, load_heading_paragraphs, load_paragraph_layout, load_side_comments, note_text, paragraphs, publication_sources

ROOT = Path(__file__).resolve().parent.parent
HEADING = re.compile(r"— [IVX]+ —|\[ *\d+ *\]|\*(?:\s+\*){2}")


def compact(text):
    return re.sub(r"\s+", "", text)


def verify(chapter, edition):
    directory = ROOT / 'chapters' / f'{chapter:02d}'
    source = publication_sources(directory, paragraphs((directory / 'original.txt').read_text(encoding='utf-8')))
    target = paragraphs((directory / 'translation.txt').read_text(encoding='utf-8'))
    assert len(source) == len(target), 'Paragraph count mismatch'
    units = aligned_units(directory, source, target)
    units = [u for u in units if not u['heading']]
    comments = load_side_comments(directory, aligned_units(directory, source, target)) if edition == 'commented' else {}
    path = directory / f'chapter-{chapter:02d}-{edition}.pdf'
    streams = {'zh': [], 'en': [], 'side': [], 'note': []}
    separator_pages = []
    with pdfplumber.open(path) as pdf:
        pages = len(pdf.pages)
        for page_number, page in enumerate(pdf.pages, 1):
            for char in page.chars:
                if not char['text'].strip():
                    continue
                assert 0 <= char['x0'] <= char['x1'] <= page.width + .5, (page_number, 'horizontal overflow', char)
                assert 0 <= char['top'] <= char['bottom'] <= page.height + .5, (page_number, 'vertical overflow', char)
                char = dict(char, page=page_number)
                font, size = char['fontname'], char['size']
                symbol = char['text'] in SYMBOL_CHARACTERS
                if 'Georgia' in font or (symbol and abs(size - 9.5) < .01):
                    assert abs(size - 9.5) < .01, ('English size', size)
                    assert close_color(char['non_stroking_color'], '#929CA6'), ('English color', char)
                    streams['en'].append(char)
                elif 'SimSun' in font or symbol:
                    if abs(size - 12) < .01 and char['text'] == '*':
                        separator_pages.append(page_number)
                    if abs(size - 10.5) < .01:
                        streams['zh'].append(char)
                    elif abs(size - 8) < .01 and close_color(char['non_stroking_color'], '#A66F73'):
                        streams['zh'].append(char)
                        streams['note'].append(char)
                    elif abs(size - 9) < .01 and close_color(char['non_stroking_color'], '#466D68'):
                        streams['side'].append(char)

    expected_zh = compact(''.join(note_text(t) for s, t in zip(source, target) if not HEADING.fullmatch(s)))
    expected_en = compact(''.join(u['source'] for u in units).replace('_', '')) if edition != 'zh' else ''
    expected_note = compact(''.join(m[3:-1] for t in target for m in re.findall(r'【注：[^】]*】', t)))
    expected_side = compact(''.join(comment_for(u, comments) for u in units))
    for key, expected in [('zh', expected_zh), ('en', expected_en), ('note', expected_note), ('side', expected_side)]:
        actual = ''.join(c['text'] for c in streams[key])
        if actual != expected:
            first = next((i for i, (a, b) in enumerate(zip(actual, expected)) if a != b), min(len(actual), len(expected)))
            raise AssertionError((path.name, key, 'text mismatch', first, actual[max(0, first-30):first+60], expected[max(0, first-30):first+60]))

    # Chapter-specific newspaper headings belong with the first text below them.
    heading_paragraphs = load_heading_paragraphs(directory, source)
    keep_with_next = load_paragraph_layout(directory, source, 'keep_with_next_paragraphs')
    zh_keep_together = load_paragraph_layout(directory, source, 'zh_keep_together_paragraphs')
    offset = 0
    separator_offset = 0
    for number, (s, t) in enumerate(zip(source, target), 1):
        if HEADING.fullmatch(s):
            if s.startswith('*'):
                marker_pages = separator_pages[separator_offset:separator_offset+3]
                assert len(marker_pages) == 3, ('missing section separator', number)
                assert set(marker_pages) == {streams['zh'][offset]['page']}, ('stranded section separator', number)
                separator_offset += 3
            continue
        count = len(compact(note_text(t)))
        if number in heading_paragraphs or number in keep_with_next:
            assert number < len(source), ('heading has no following passage', number)
            assert streams['zh'][offset + count - 1]['page'] == streams['zh'][offset + count]['page'], ('stranded heading', number)
        if edition == 'zh' and number in zh_keep_together:
            assert streams['zh'][offset]['page'] == streams['zh'][offset + count - 1]['page'], ('paragraph crosses pages', number)
        offset += count
    assert separator_offset == len(separator_pages), 'Unexpected section separators'

    pairs = 0
    if edition != 'zh':
        offsets = {'zh': 0, 'en': 0, 'side': 0}
        for u in units:
            texts = {'zh': compact(note_text(u['target'])), 'en': compact(u['source'].replace('_', '')), 'side': compact(comment_for(u, comments))}
            spans = {}
            for key, value in texts.items():
                start = offsets[key]
                spans[key] = streams[key][start:start+len(value)]
                offsets[key] += len(value)
            page_set = {c['page'] for key in ('zh', 'en', 'side') for c in spans[key]}
            assert len(page_set) == 1, ('reading unit crosses pages', u['paragraph_numbers'], u['segment_index'], page_set)
            if spans['side']:
                assert abs(spans['side'][0]['top'] - spans['zh'][0]['top']) < 3, ('comment alignment', u['paragraph_numbers'])
                assert min(c['x0'] for c in spans['side']) > max(c['x1'] for key in ('zh', 'en') for c in spans[key]), ('column overlap', u['paragraph_numbers'])
            pairs += 1

    font_names = set()
    for page in PdfReader(path).pages:
        for ref in page['/Resources']['/Font'].values():
            font = ref.get_object()
            # ReportLab includes unused standard fonts in the resource table.
            if str(font.get('/BaseFont', '')) == '/Helvetica':
                continue
            descriptor = font.get('/FontDescriptor')
            assert descriptor, ('font descriptor missing', font)
            descriptor = descriptor.get_object()
            assert any(key in descriptor for key in ('/FontFile', '/FontFile2', '/FontFile3')), ('font not embedded', font)
            font_names.add(str(font['/BaseFont']))
    return {'file': str(path), 'pages': pages, 'reading_pairs': pairs, 'side_comments': sum(bool(x) for a in comments.values() for x in a), 'text_and_alignment': 'pass', 'embedded_fonts': sorted(font_names)}


def close_color(value, hexa):
    expected = tuple(int(hexa[i:i+2], 16) / 255 for i in (1, 3, 5))
    return isinstance(value, (tuple, list)) and len(value) == 3 and all(abs(a-b) < .001 for a, b in zip(value, expected))


def comment_for(unit, comments):
    return ''.join(comments[str(n)][unit['segment_index']] or '' for n in unit['paragraph_numbers'] if str(n) in comments)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('chapter', type=int, choices=range(1, 19))
    parser.add_argument('--edition', choices=('zh', 'parallel', 'commented', 'all'), default='all')
    args = parser.parse_args()
    editions = [e for e in ('zh', 'parallel', 'commented') if (ROOT / 'chapters' / f'{args.chapter:02d}' / f'chapter-{args.chapter:02d}-{e}.pdf').exists()] if args.edition == 'all' else [args.edition]
    assert editions, 'No PDFs to verify'
    print(json.dumps([verify(args.chapter, e) for e in editions], ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
