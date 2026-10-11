"""Split the local Gutenberg source without changing any source bytes."""

import hashlib
import json
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "ulysses.txt"
OUTPUT = ROOT / "chapters"


def main():
    source = SOURCE.read_bytes()
    source.decode("utf-8")  # Validate the encoding before writing anything.
    lines = source.splitlines(keepends=True)
    book_start, = (
        i for i, line in enumerate(lines)
        if line.rstrip(b"\r\n") == b"*** START OF THE PROJECT GUTENBERG EBOOK ULYSSES ***"
    )
    book_end, = (
        i for i, line in enumerate(lines)
        if line.rstrip(b"\r\n") == b"*** END OF THE PROJECT GUTENBERG EBOOK ULYSSES ***"
    )

    # Contents entries are indented; actual chapter headings are not.
    headers = []
    for i in range(book_start + 1, book_end):
        match = re.fullmatch(rb"\[ *([0-9]+) *\]", lines[i].rstrip(b"\r\n"))
        if match:
            headers.append((int(match[1]), i))
    if [number for number, _ in headers] != list(range(1, 19)):
        raise ValueError("Expected exactly 18 chapter headings in order.")

    parts = {1: "I", 4: "II", 16: "III"}
    boundaries = []
    for number, heading in headers:
        start = heading
        if number in parts:
            part_heading = f"— {parts[number]} —".encode("utf-8")
            start = heading - 1
            while start > book_start and not lines[start].strip():
                start -= 1
            if lines[start].rstrip(b"\r\n") != part_heading:
                raise ValueError(f"Missing part heading before chapter {number}.")
        boundaries.append(start)
    boundaries.append(book_end)

    files = {"front-matter.txt": b"".join(lines[:boundaries[0]])}
    chapters = []
    for index, (number, heading) in enumerate(headers):
        start, end = boundaries[index:index + 2]
        part = "I" if number <= 3 else "II" if number <= 15 else "III"
        path = f"{number:02d}/original.txt"
        files[path] = b"".join(lines[start:end])
        chapters.append({
            "number": number,
            "part": part,
            "path": f"chapters/{path}",
            "source_start_line": start + 1,
            "source_end_line": end,
            "source_heading_line": heading + 1,
        })
    files["back-matter.txt"] = b"".join(lines[book_end:])
    if b"".join(files.values()) != source:
        raise ValueError("Split files do not reproduce the complete source.")

    manifest = {
        "source": "ulysses.txt",
        "encoding": "UTF-8",
        "source_sha256": hashlib.sha256(source).hexdigest(),
        "front_matter": "chapters/front-matter.txt",
        "back_matter": "chapters/back-matter.txt",
        "chapters": chapters,
    }
    files["index.json"] = (json.dumps(manifest, indent=2) + "\n").encode("utf-8")

    # Re-running is safe; refuse to replace files edited since the split.
    for path, content in files.items():
        target = OUTPUT / path
        if target.exists() and target.read_bytes() != content:
            raise FileExistsError(f"Refusing to overwrite changed file: {target}")
    for path, content in files.items():
        target = OUTPUT / path
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists():
            target.write_bytes(content)

    reconstructed = b"".join(
        (OUTPUT / path).read_bytes() for path in files if path != "index.json"
    )
    if reconstructed != source or SOURCE.read_bytes() != source:
        raise ValueError("Source preservation verification failed.")
    print(f"Verified {len(chapters)} chapters; all {len(source):,} source bytes preserved.")


if __name__ == "__main__":
    main()
