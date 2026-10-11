# Repository Guidelines

## Purpose

We are here to make a better Chinese translation of Ulysses by James Joyce.

## Guide lines

1. We'll translate chapter by chapter.
2. We'll produce a PDF file for each chapter.
3. Try to be "信达雅", but when direct translation works better, use direct translation.
4. If a translation is hard to translate the original meaning or indication, add a inline commen to explain.
5. Be aware of the cultural difference, add precise and concise inline comments/explainations to help the reader understand, like 脂评 in 红楼梦
6. Use 宋体, use smaller font, different size for the inline comments.

## Conventions

This section is for communicating the translation conventions over different sessions, add them if you think they help the following work. But keep this clean and concise, avoid bloating it.

- Keep `ulysses.txt` as the unchanged Project Gutenberg source.
- The 18 chapters use zero-padded folders `chapters/01/` through `chapters/18/`. Each folder contains `original.txt`; work from that file when translating its chapter, and keep the chapter's translation and PDF in the same folder.
- Preserve the source's chapter numbering and part divisions: Part I contains chapters 1–3, Part II chapters 4–15, and Part III chapters 16–18. A part heading stays with its opening chapter.
- `chapters/front-matter.txt` contains the source metadata and contents; `chapters/back-matter.txt` contains the Gutenberg end marker and license. `chapters/index.json` records chapter paths, source line ranges, and the source checksum.
- Run `python scripts/split_chapters.py` to reproduce the split. It preserves the original bytes and refuses to overwrite changed chapter files.
- Use UTF-8 `translation.txt` with the same blank-line paragraph boundaries as `original.txt`; mark inline notes internally as `【注：…】` and indent verse lines with four spaces. PDFs omit the note label and brackets. Keep translation decisions and checked references in `translation-notes.txt`; chapter 01 establishes the initial names and recurring terms.
- Run `python scripts/build_chapter_pdf.py 01` (substitute the chapter number) to create both `chapter-01-zh.pdf` and `chapter-01-parallel.pdf` in the chapter folder; `--edition zh|parallel` selects one. Chinese text uses embedded SimSun at 10.5 pt, with 8 pt muted rose (`#A66F73`) inline notes. The parallel edition places 9.5 pt light gray-blue (`#929CA6`) Georgia source text below each Chinese passage, preserving italics and stanzas while making the English easy to skip during Chinese reading. Optional `parallel-segments.json` records verified matching splits for long paragraphs. Font paths can be set with the script's font options or `ULYSSES_*_FONT` environment variables.
- Publish chapter PDFs with their editable manuscripts and update the README reading links and progress. New translation, notes, and documentation use CC BY-SA 4.0; scripts use MIT. Preserve the source and third-party notices in `NOTICE.md`; keep temporary renders, credentials, caches, and standalone font files out of Git.
