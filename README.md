# CODE MORPHER 🔀

A colorful terminal tool for text and code conversion — runs entirely on your Android phone inside Termux.

> ⚠️ **Important:** Encoding is NOT encryption. Anyone with this tool can reverse the output. It is intended for format conversion, obfuscation experiments, and learning — not security.

---

## Features

| # | Feature |
|---|---------|
| 1 | Colorful Rich terminal menu |
| 2 | Paste multi-line text or load any file |
| 3 | Binary encode / decode |
| 4 | Hexadecimal encode / decode |
| 5 | Base64 encode / decode |
| 6 | Unicode-escape encode / decode (`\uXXXX`) |
| 7 | Emoji substitution — fully reversible with versioned map |
| 8 | Custom-symbol profiles — user-defined character substitution |
| 9 | Preview before saving |
| 10 | Auto-suggested filenames with overwrite protection |
| 11 | Batch conversion of entire directories |
| 12 | Output file browser: view, delete |
| 13 | Conversion history (JSON, last 500 entries) |
| 14 | Symbol-profile manager: create, list, delete |
| 15 | Full Unicode support: Bengali, emoji, CJK, special chars |

---

## Installation on Termux

### One-time Termux setup (if not done already)

```bash
pkg update && pkg upgrade -y
pkg install python -y
```

### Install Code Morpher

```bash
# 1. Copy the project folder to your phone, or create it manually:
mkdir -p ~/code_morpher
cd ~/code_morpher

# 2. Install the only external dependency:
pip install rich

# 3. Run the tool:
python main.py
```

If you downloaded a zip:

```bash
cd ~/storage/downloads          # or wherever you saved it
unzip code_morpher.zip
cd code_morpher
pip install rich
python main.py
```

---

## Running the tests

```bash
cd ~/code_morpher
python tests.py
```

All tests should pass with output like:

```
━━ Binary encode / decode ━━
  ✓  binary round-trip [ascii]
  ✓  binary round-trip [multiline]
  ...
============================================================
ALL 80 TESTS PASSED ✓
============================================================
```

---

## Usage Guide

### Main menu

```
┌──────────────────────────────────────────────────────┐
│              CODE MORPHER  v1.0.0                    │
│         text & code conversion                       │
├──────────────────────────────────────────────────────┤
│  1  Encode / Convert text or file                    │
│  2  Decode / Restore encoded content                 │
│  3  Batch conversion                                 │
│  4  Manage output files                              │
│  5  View conversion history                          │
│  6  Manage symbol profiles                           │
│  7  About                                            │
│  q  Quit                                             │
└──────────────────────────────────────────────────────┘
```

### Encoding text

1. Select `1` from the menu.
2. Choose a format (1–6).
3. Choose `paste` and type or paste your text, then type `END` on its own line.
4. Preview the result.
5. Accept the suggested filename or type your own.

### Decoding a file

1. Select `2` from the menu.
2. Choose `file` and enter the path to an encoded file (e.g. `~/code_morpher/outputs/encoded_binary_20240101_120000.txt`).
3. The format is detected automatically from the file header.
4. Preview and save.

### Batch conversion

1. Select `3`.
2. Enter a directory path (e.g. `~/storage/shared/scripts`).
3. Enter a glob pattern (e.g. `*.py`).
4. Choose `encode` or `decode` and the format.
5. All matching files are processed; outputs go into `~/code_morpher/outputs/`.

### Custom symbol profiles

1. Select `6` → `create`.
2. Enter a profile name (e.g. `mycode`).
3. Enter mappings one per line: `char=symbol` (e.g. `a=@`, `e=3`, `o=0`).
4. Type `DONE` when finished.

Now use this profile in the encode/decode menus.

---

## File locations

| Path | Contents |
|------|----------|
| `~/code_morpher/outputs/` | All converted output files |
| `~/code_morpher/history.json` | Conversion history (last 500) |
| `~/code_morpher/symbol_profiles.json` | Your custom symbol profiles |

---

## Format headers

Every encoded file begins with a header so the decoder can identify it:

| Format | Header |
|--------|--------|
| Binary | `##CMORPH-BINARY-v1##` |
| Hex | `##CMORPH-HEX-v1##` |
| Base64 | `##CMORPH-BASE64-v1##` |
| Unicode escape | `##CMORPH-UNICODE-v1##` |
| Emoji | `##CMORPH-EMOJI-v1##` |
| Symbol | `##CMORPH-SYMBOL-v1:profilename##` |

---

## Emoji encoding

The emoji encoder uses a **fixed, versioned** mapping of all 95 printable ASCII characters (space through `~`) to unique emoji. Non-ASCII characters (Bengali, CJK, other emoji, etc.) are encoded as passthrough blocks using their Unicode codepoints, so the round trip is exact.

Example:

```
Input:  Hello!
Output: ##CMORPH-EMOJI-v1##
        😃😋😍😍😒😇
```

---

## Tips for Termux

- Run `termux-setup-storage` once to allow access to your phone's shared storage.
- You can open files from `~/storage/shared/` to convert documents saved anywhere on your phone.
- Add an alias in `~/.bashrc` for quick access:
  ```bash
  alias cm='python ~/code_morpher/main.py'
  ```
  Then just type `cm` to launch.

---

## Dependencies

- **Python 3.8+** (standard Termux python package)
- **rich** (terminal formatting — the only pip package needed)

Everything else (base64, binascii, pathlib, json) is Python standard library.

---

## License

MIT — free to use, modify, and share.
