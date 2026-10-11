# 尤利西斯 · 中文重译与夹注

逐章重译詹姆斯·乔伊斯的 *Ulysses*，制作适合连续阅读的中文本，以及便于细读原文的中英对照本。

以“信、达、雅”为方向；直译更能保留原作的声音时，就保留直译。对双关、典故、文化差异和难以兼顾的语义，采用接近《红楼梦》脂评的简短夹注，尽量让解释贴近阅读发生的地方。

**目前完成第 1、2 章的译稿、夹注及各自的两个 PDF 版本。** 本项目使用 AI 辅助翻译、核典与排版，译稿持续校订，欢迎依据原文提出修正。

## 开始阅读

| 章节 | 进度 | 中文译本 | 中英对照本 | 可编辑文本与校译记录 |
| --- | --- | --- | --- | --- |
| 第 1 章 · 第一部开篇 | 已完成初稿、词语照应及叙述层次校订 | [PDF · 26 页](chapters/01/chapter-01-zh.pdf) | [PDF · 47 页](chapters/01/chapter-01-parallel.pdf) | [译稿](chapters/01/translation.txt) · [校译记录](chapters/01/translation-notes.txt) |
| 第 2 章 | 已完成初稿及跨章照应核对 | [PDF · 16 页](chapters/02/chapter-02-zh.pdf) | [PDF · 29 页](chapters/02/chapter-02-parallel.pdf) | [译稿](chapters/02/translation.txt) · [校译记录](chapters/02/translation-notes.txt) |
| 第 3–18 章 | 原文已分章，待翻译 | — | — | [章节索引](chapters/index.json) |

中文本保留原作中的必要异语及其释义。对照本将中文放在上方、对应原文放在下方；长段按语义拆分，诗歌保留完整诗节，每组中英文同页。

## 翻译与排版

- 保留底本的部、章编号和叙述层次，不把通行的荷马对应名称增作原文章题。
- 尽量保留人物口吻、意识流、重复意象和有意悬空的主语；不把解释补进正文。
- 对承接、回应或回响起作用的重复词句，保持可辨认的共同译语，连同跨章复现一并核对；确有词义变化或双关时保留差异，必要时简注说明。
- 夹注从简，说明难以兼顾的音义、文化背景与必要出处；有解释性质的判断应与事实区分。
- 中文正文为 10.5 磅宋体，夹注为 8 磅淡红色宋体，不显示“注：”及方括号。
- 对照本原文为 9.5 磅浅灰蓝色 Georgia（`#929CA6`），保留斜体与诗行；降低原文的视觉分量，方便连续阅读中文时跳过。

第 1 章包含 67 条夹注，第 2 章包含 40 条。译名、取舍及已核对的参考资料见各章校译记录；跨章沿用的原则见 [AGENTS.md](AGENTS.md)，包括保留歧义、区分人物声音、保留句法节奏、兼顾双关与典故、保留人物错记，以及区分注释中的事实与解释。

## 文件结构

```text
ulysses.txt                       未改动的 Gutenberg 全书底本
chapters/
  front-matter.txt                 来源元数据与目录
  back-matter.txt                  结束标记与 Gutenberg 完整许可
  index.json                      章节路径、原文行号与 SHA-256
  01/
    original.txt                  本章原文
    translation.txt               本章译稿与内部夹注标记
    translation-notes.txt          译名、校译取舍、参考来源与检查记录
    parallel-segments.json        长段对读的对应切分位置
    chapter-01-zh.pdf              中文译本
    chapter-01-parallel.pdf        中英对照本
  02/
    original.txt
    translation.txt
    translation-notes.txt
    parallel-segments.json
    chapter-02-zh.pdf
    chapter-02-parallel.pdf
  03/ … 18/
    original.txt
scripts/
  split_chapters.py                无损分章与底本校验
  build_chapter_pdf.py             生成两个阅读版本
```

第一部为第 1–3 章，第二部为第 4–15 章，第三部为第 16–18 章。部标题随各部的首章保存。

## 本地重建

直接阅读 PDF 无须安装依赖。重建需要 Python 3.10 或更新版本，以及具有相应使用和嵌入许可的字体。

```sh
python -m pip install -r requirements.txt
python scripts/split_chapters.py
python scripts/build_chapter_pdf.py 01
python scripts/build_chapter_pdf.py 02
```

分章脚本核对完整底本的字节与校验和；已有分章文件被改动时会拒绝覆盖。排版脚本读取该章原文及译稿，输出 PDF，不改动输入文本。目前可排版的章节为 `01`、`02`。

默认同时生成两版，也可单独生成：

```sh
python scripts/build_chapter_pdf.py 01 --edition zh
python scripts/build_chapter_pdf.py 01 --edition parallel
```

Windows 默认使用 `C:/Windows/Fonts/simsun.ttc`、`georgia.ttf` 和 `georgiai.ttf`。其他路径可通过参数指定：

```sh
python scripts/build_chapter_pdf.py 01 --font "/path/to/simsun.ttc" --english-font "/path/to/georgia.ttf" --english-italic-font "/path/to/georgiai.ttf"
```

也可设置 `ULYSSES_SONG_FONT`、`ULYSSES_ENGLISH_FONT` 和 `ULYSSES_ENGLISH_ITALIC_FONT`。仓库不分发独立字体文件；替换字体会影响换行和页数。生成后应检查文字完整性，并渲染逐页校样。

## 参与校订

欢迎通过 Issue 或 Pull Request 提出改译、补充可靠出处，或报告排版问题。请给出章节、原句、当前译文，以及建议和理由；核典尽量链接到原作、学术机构或可复核的文献。

修改译稿时保留与 `original.txt` 一致的空行分段，诗行缩进四个空格。`【注：……】` 仅是译稿的内部标记，PDF 会将其转为小号淡红夹注。若改动涉及对照本的长段切分，请同步更新 `parallel-segments.json`，重建两版并核对页面。提交到相应目录的新增内容沿用该目录的许可证。

## 来源与许可

原著作者为 **James Joyce**。英文底本来自 [Project Gutenberg eBook #4300](https://www.gutenberg.org/ebooks/4300)，电子文本制作署名 **Col Choat**；本仓库所用版本的更新时间为 2025-11-27。Gutenberg 将该底本标为在美国属于公有领域，其他地区的适用情况应依当地法律判断。

| 内容 | 许可范围 |
| --- | --- |
| 本项目新增的中文译文、夹注、文档，以及 PDF 中相应的新增内容 | [CC BY-SA 4.0](LICENSE)：署名、注明修改，并以相同许可分享改编成果；允许商业使用 |
| `scripts/` 中的代码 | [MIT](scripts/LICENSE) |
| 乔伊斯原文、Gutenberg 元数据及许可文本、第三方引文和嵌入字体 | 保留各自的权利状态，不纳入本项目新增内容的许可；详见 [NOTICE.md](NOTICE.md) |

新增内容的署名可写作“[Inoarby 与 ulysses-zh 项目贡献者](https://github.com/Inoarby/ulysses-zh)”，并标明所用版本及修改情况。以上授权限于贡献者依法能够授予的权利，不为公有领域内容设立新的限制。

### Gutenberg 再分发说明

> This eBook is for the use of anyone anywhere in the United States and most other parts of the world at no cost and with almost no restrictions whatsoever. You may copy it, give it away or re-use it under the terms of the Project Gutenberg™ License included with this eBook or online at [www.gutenberg.org](https://www.gutenberg.org/license). If you are not located in the United States, you will have to check the laws of the country where you are located before using this eBook.

原始全文及其完整许可保留在 [ulysses.txt](ulysses.txt)；分章后的完整许可见 [chapters/back-matter.txt](chapters/back-matter.txt)。本项目与 Project Gutenberg 无隶属或背书关系。
