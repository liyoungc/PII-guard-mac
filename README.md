# PII Guard for Mac

**English** ｜ [繁體中文](README.zh-TW.md)

A menu bar app that removes personal names from documents, fully offline, on Apple Silicon.
It was built for hospital patient-safety incident reports written in Traditional Chinese:
`陳禮揚` becomes `陳○○`, and nothing else in the file changes.

- **Runs entirely on your Mac.** Open models are served by [Rapid-MLX](https://github.com/raullenchai/Rapid-MLX); document content never leaves the machine.
- **The model finds, the program replaces.** The model only lists names that appear verbatim in the text. It cannot rewrite your document.
- **Text-only edits.** `.docx` / `.xlsx` / `.pptx` files are edited by rewriting text nodes in place, so fonts, borders, images, formulas and layout are preserved.
- **Human review before writing.** Untick false alarms, add anything that was missed, or accept everything in one click.
- **Verified after writing.** The output file is reopened and searched for every confirmed original string.
- **The original is never modified.** Output goes to a new file next to it (`name_去識別.xlsx`).

> ⚠️ No model catches every name, and small models miss more. Treat this as an assistant and review the list for anything important.

## Requirements

- Apple Silicon Mac (M1 or later), macOS 14+, 8 GB RAM or more
- Xcode Command Line Tools (`xcode-select --install`)
- [uv](https://docs.astral.sh/uv/) (`brew install uv`)

## Install (from source)

```bash
git clone https://github.com/liyoungc/PII-guard-mac.git
cd PII-guard-mac
scripts/install.sh
open "$HOME/Applications/PII Guard.app"
```

The script installs the Python engine and Rapid-MLX into an isolated environment
(`~/Library/Application Support/PII-guard-mac/venv`; any existing Rapid-MLX install is left alone),
then builds the app with Swift and copies it to `~/Applications`. It is safe to re-run.

### Instructions for AI agents

Run these in order. Each step has a checkable result.

```bash
# 1. Preconditions (stop and report if any fails; do not work around them)
[ "$(uname -m)" = "arm64" ] && sw_vers -productVersion     # must be arm64 and 14 or later
command -v swift && command -v uv                          # both required; missing uv: brew install uv

# 2. Install
git clone https://github.com/liyoungc/PII-guard-mac.git && cd PII-guard-mac
scripts/install.sh                                         # ends with "==> Done."

# 3. Verify the engine (prints JSON containing "formats")
PG="$HOME/Library/Application Support/PII-guard-mac/venv/bin/piiguard"
"$PG" info

# 4. See the recommended model for this Mac and load it (first run downloads several GB)
"$PG" models                                               # read "recommended"
"$PG" server start --wait                                  # expect "state": "ready"

# 5. End-to-end self-test with synthetic data
printf '通報人：王小明，由護理師林美玲協助。\n' > /tmp/piiguard-demo.txt
"$PG" run /tmp/piiguard-demo.txt                           # expect "verified": true; output contains 王○○ and 林○○

# 6. Launch the menu bar app
open "$HOME/Applications/PII Guard.app"
```

Do not paste the user's real documents into a conversation or upload them anywhere; keeping them local is the point of this tool.

## Usage

1. Click the eye icon in the menu bar → **選擇檔案去識別化…** (Choose files).
2. The model loads automatically the first time (it has to download). After that, use **載入模型 / 卸載模型** (Load / Unload) in the menu; unloading returns all memory to the system.
3. In the review list, untick what should stay, add what was missed, or press **全部接受並寫出** (Accept all and write).
4. The output file appears next to the original.

The app's interface is in Traditional Chinese.

### Settings

| Tab | Contents |
|---|---|
| 模型 (Model) | Measured numbers and the pick for each RAM tier; select, load, unload |
| 遮蔽 (Masking) | Mode, mask character, categories, custom patterns, review on/off, mapping table on/off |
| 白名單 (Lists) | Words never to mask (a built-in medical list, editable) and words always to mask |

### Masking modes

| Mode | 陳禮揚 | 陳明 | 歐陽大華 |
|---|---|---|---|
| Keep surname (default) | 陳○○ | 陳○ | 歐陽○○ |
| Keep surname + number | different people with the same surname become 陳○○(1), 陳○○(2) | | |
| Full mask | ○○○ | ○○ | ○○○○ |
| Code | 人員A | 人員B | 人員C |

The mask character defaults to full-width `○` and is configurable. Besides names you can enable
Taiwan national ID / resident certificate numbers, phone numbers, email addresses, medical record
numbers, or your own regular expressions.

### Mapping table

By default only the de-identified (unlinked) file is written. If you enable the mapping table in
Settings, a second file `name_去識別_對照表.csv` (original → replacement) is written. It contains the
original names; store it separately from the de-identified file.

### Command line

```bash
PG="$HOME/Library/Application Support/PII-guard-mac/venv/bin/piiguard"
"$PG" scan  report.docx > found.json      # detect only; found.json is editable
"$PG" apply report.docx --decisions found.json
"$PG" run   report.docx --mode full --mapping   # accept everything and write
"$PG" server stop                          # unload the model
```

## Which model

These are measurements on a synthetic corpus of incident reports, not impressions. **Recall** (the share
of names that were found) matters most: a missed name is a privacy incident, a false alarm is one tick
to remove in the review list.

<!-- BENCH -->
| Min RAM | Model | Recall | Precision | Speed (chars/s) | Memory | Download | Pick for |
|---|---|---|---|---|---|---|---|
| 8 GB | `mlx-community/Qwen3.5-2B-MLX-4bit` | 79.6% | 92.9% | 197 | 3.2 GB | 1.8 GB |  |
| 8 GB | `mlx-community/gemma-4-e2b-it-4bit` | 100.0% | 98.0% | 224 | 4.92 GB | 3.6 GB | ✅ 8、16 GB |
| 16 GB | `mlx-community/Qwen3.5-4B-MLX-4bit` | 98.0% | 98.0% | 46 | 7.78 GB | 3.1 GB |  |
| 16 GB | `mlx-community/gemma-4-e4b-it-4bit` | 98.0% | 100.0% | 117 | 6.54 GB | 5.2 GB |  |
| 24 GB | `mlx-community/Qwen3.5-9B-6bit` | 98.0% | 98.0% | 33 | 13.0 GB | 8.2 GB |  |
| 24 GB | `mlx-community/gemma-4-12B-it-4bit` | 100.0% | 100.0% | 38 | 8.94 GB | 6.8 GB | ✅ 24、32 GB |
| 32 GB | `rapid-mlx/Qwen3.8-27B-4bit-MTP-MLX` | — | — | — | — | 16.3 GB |  |
| 32 GB | `mlx-community/gemma-4-26b-a4b-it-4bit` | — | — | — | — | 15.4 GB |  |

Measured on: Apple M4 Pro, 24 GB, rapid-mlx 1.0.3, 2026-11-15. Corpus: `bench/corpus.jsonl` (20 synthetic documents, 49 names).
<!-- /BENCH -->

How the picks were made: recall first, then whether the memory footprint leaves room for the system, then speed.

- The corpus has only 49 names, so a difference of one or two names is not significant. The detection prompt was also adjusted after failures on this same corpus, so the numbers are optimistic.
- The 8 GB pick (about 4.9 GB) was not verified on a real 8 GB machine; close other large apps when using it. If memory is too tight, use `Qwen3.5-2B` (about 3.2 GB, but it misses more).
- The two large 32 GB-tier models are not measured yet; the 24 GB pick stands in.
- On this task a bigger model is not automatically more accurate.

The numbers are raw model output, before the whitelist and human review. To re-measure:
`.venv/bin/python bench/run_bench.py <model id>`.

## Supported formats

| Format | Notes |
|---|---|
| `.docx` `.xlsx` `.pptx` (also `.docm` `.xlsm` `.pptm`) | Body text, tables, headers and footers, comments, speaker notes, tracked changes; author and similar file properties are cleared |
| `.txt` `.md` `.csv` `.tsv` `.json` `.xml` `.html` `.yaml` `.log` | UTF-8, UTF-16, Big5 |
| `.doc` `.xls` `.ppt` | **Not supported.** Use "Save As" in Office or LibreOffice to convert to the modern format first |
| `.pdf` | **Not supported**: text in a PDF cannot be replaced in place |

## Known limitations

- The model can miss names, especially two-character names, names with spaces inside, and with smaller models.
- A surname with a title only (`陳醫師`, "Dr. Chen") is not masked.
- A name split across two paragraphs or two cells is not recognised.
- Sheet names, text inside charts, and text inside images are not processed.
- The whitelist matches exact strings only.

## Surname rules

`engine/src/piiguard/surname.py` decides which characters survive in the keep-surname modes: known
compound surnames (歐陽, 司馬, 范姜, 張簡 …) keep two characters, everything else keeps one; a married
double surname (陳林美玉) currently keeps only the first. The function is a few lines long and meant to be edited.

## Uninstall

Move `~/Applications/PII Guard.app` and `~/Library/Application Support/PII-guard-mac` to the Trash.
Model files live in `~/.cache/huggingface/hub/` (folders starting with `models--`).

## Credits and license

The core principle (the model reports exact substrings; the program replaces and verifies) follows
[danyuchn/pii-guard](https://github.com/danyuchn/pii-guard) (MIT). Inference is by
[Rapid-MLX](https://github.com/raullenchai/Rapid-MLX) (Apache-2.0). See each model's page for its license.

Released under the MIT License. Tests and benchmarks use synthetic data only; this repository contains no real documents.
