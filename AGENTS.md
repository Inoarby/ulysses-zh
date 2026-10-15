# Repository Guidelines

## Purpose

We are here to make a better Chinese translation of Ulysses by James Joyce.

## Guide lines

1. We'll translate chapter by chapter.
2. We'll produce a PDF file for each chapter.
3. Try to be "信达雅", but when direct translation works better, use direct translation.
4. Make the translation carry as much meaning and effect as it can. Use inline notes for consequential cultural or linguistic gaps that Chinese cannot readily convey, preserving the original's deliberate difficulty and strangeness.
5. Let inline notes earn the interruption they cause. Take attentiveness and intimacy from 脂评 in 红楼梦, while keeping evaluative commentary rare; follow the inline-note principles below.
6. Use 宋体, use smaller font, different size for the inline comments.
7. Preserve verbal echoes in dialogue, quotations, inner monologue, and recurring images, including across chapters. When repeated words or phrases carry a response or callback, retain a recognizable shared Chinese wording rather than varying synonyms for elegance. Preserve real shifts of meaning and wordplay, with a brief note where needed; review each echo in context before finalizing a chapter.
8. Preserve ambiguity and meaningful omissions. Keep uncertain pronoun references, speakers, thought ownership, and meanings open where the original does; explain possible readings in notes when needed.
9. Distinguish character voices and narrative layers. Preserve the diction, tone, and rhythm of dialogue, narration, inner monologue, quotation, and parody, including their coarseness, solemnity, malice, or suggestiveness.
10. Treat syntax, rhythm, and associative leaps as meaning. Preserve expressive fragments, repetitions, abrupt turns, and unusual word order; assess whether adding subjects, connectives, or causal explanations would alter the movement of thought.
11. Translate wordplay and allusions with both their immediate context and later echoes in view. Carry the principal meanings, voice, and connections into the Chinese where possible, briefly annotate what cannot be retained, and check recurring quotations against earlier renderings.
12. Preserve characters' limited or unreliable understanding. Render their factual mistakes, prejudices, and contradictions faithfully; clarify material errors in notes where useful, distinguishing character opinion, narration, and editorial explanation.
13. Distinguish verified facts, interpretations, and conjectures in notes. Check traceable sources, qualify interpretive claims, and explain only what helps the present passage, limiting spoilers and leaving room for readers to discover connections.

## Inline-note principles

- Write for an attentive Chinese reader without specialist knowledge. Explain what the passage depends on; allow readers to infer what the surrounding text makes clear. Unfamiliarity alone does not require a note.
- Identify each note's specific benefit: removing a consequential obstacle or revealing an otherwise inaccessible effect, such as wordplay, register, an allusion, or a verbal connection. First check whether better translation can do the work. Omit information that makes little difference to the present passage.
- Give the smallest explanation that unlocks the passage, usually one short sentence. For an allusion, identify it and give the relevant detail; include dates, biography, or source history only when they affect this reading. Keep full references and translation justifications in `translation-notes.txt`.
- Supply facts, alternate meanings, and verbal connections that help readers discover meanings themselves. Keep editorial explanation distinct from character voices; preserve uncertainty under guidelines 8 and 13. Avoid prescribing emotions, spelling out every joke, or turning an association into a settled interpretation.
- Attach a note to the smallest complete unit it explains, preferably at a natural pause. Let a joke, image, or revelation land first; protect tightly connected phrases, exchanges, verse, and movements of thought.
- Explain recurring material where it first becomes useful. Repeat briefly when distance or a changed meaning warrants it; preserving an echo does not automatically require announcing it. Review clusters together, since several useful notes can collectively overwhelm a paragraph.
- Revise by subtraction: ask what the reader would materially miss without each note, then delete or shorten weak notes. Read both with and past the notes to check rhythm, placement, and cumulative density; use no fixed note quota or rigid length limit.

## Side-comment principles

- Orient before interpreting: distinguish present action, perception, memory, imagined scenes, and quotation where the text permits. Leave unresolved voices and references open.
- Explain the hardest associative link: identify the word, sound, image, or idea that prompts a jump, rather than paraphrasing every sentence.
- Separate established references from readings and conjectures; mark uncertainty explicitly. Preserve characters' errors and prejudices without endorsing them or treating their thoughts as the author's conclusions.
- Complement inline notes: use the side column for the paragraph's movement and connections, avoiding duplicated definitions and background.
- Comment selectively, only when a note materially improves understanding. Leave clear passages unannotated; omit paraphrase, obvious speaker labels, and guidance already supplied nearby or by an inline note. Give essential guidance first, usually in one or two short Chinese sentences; use no coverage target or fixed quota.
- Recall earlier material when it unlocks the passage, but limit spoilers and avoid resolving later developments in advance.
- Keep interpretations accountable to the text. Do not convert associations into logical arguments; record checked references and fuller justifications in `translation-notes.txt`.
- Align each comment with its passage, distinguish it visually from both languages, and keep it comfortably legible. For long paragraphs, use the existing verified parallel segments but comment only on segments that need help; preserve stanza and dialogue connections. One well-placed orientation may serve a connected sequence.
- Revise by subtraction: identify the specific obstacle each comment removes, shorten it where possible, and read the chapter both with and past the comments.

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
- Optional `side-comments.json` (schema 2) stores selective Chinese guidance keyed by 1-based source paragraph (including headings in the numbering), with checksums for its inputs. Omit unannotated paragraphs; within a split paragraph, keep one array slot per verified segment and use `null` for an unannotated segment. Run `python scripts/build_chapter_pdf.py 03 --edition commented` to create `chapter-03-commented.pdf`: the parallel text at its existing width, plus a right column of 9 pt muted teal SimSun comments. Keep comments, split anchors, and checksums in sync after manuscript changes; the default build still produces the original two editions.

- Optional `layout.json` lists verified 1-based `heading_paragraphs` (in-chapter headings) and `verse_group_break_before` (independent adjacent stanzas). Preserve source asterisk section markers; keep them with the following passage. These controls do not change manuscript paragraph boundaries. `keep_with_next_paragraphs` links explicitly checked questions to their first answers; `zh_keep_together_paragraphs` keeps selected Chinese paragraphs on one page. `accounting_paragraphs` renders selected ledgers with right-aligned amounts; any manual split in a line-preserved passage must end at a complete original and translated line.
- Chapters 15 and 18 explicitly mark limited editorial omissions of graphic sexual content involving minors in both published languages; retain the unchanged source files. `source-overrides.json` (schema 1) records each affected 1-based paragraph's UTF-8 SHA-256 after paragraph parsing, its complete publication `text`, and a `reason`. The text must retain one paragraph and an `[Editorial omission: ...]` marker; Chinese manuscripts use visible `【编者概述：…】` markers. Build and verification use the same publication text, and matching split anchors must refer to that text. Document exact limits in each chapter's notes; do not describe these editions as unabridged.
