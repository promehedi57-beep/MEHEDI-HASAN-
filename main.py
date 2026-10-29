#!/usr/bin/env python3
"""
CODE MORPHER — A code and text conversion tool for Termux on Android.
Encoding is NOT encryption. Outputs are recoverable by anyone with this tool.
"""

__version__ = "1.0.0"
__author__ = "Code Morpher"

import base64
import binascii
import json
import os
import shutil
import sys
import unicodedata
from datetime import datetime
from pathlib import Path
from typing import Optional

# ── Rich imports ─────────────────────────────────────────────────────────────
try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich.prompt import Prompt, Confirm
    from rich.syntax import Syntax
    from rich.text import Text
    from rich import box
    from rich.columns import Columns
    from rich.rule import Rule
    from rich.progress import Progress, SpinnerColumn, TextColumn
except ImportError:
    print("ERROR: 'rich' is not installed. Run: pip install rich")
    sys.exit(1)

console = Console()

# ── Paths ─────────────────────────────────────────────────────────────────────
BASE_DIR   = Path.home() / "code_morpher"
OUTPUT_DIR = BASE_DIR / "outputs"
HISTORY_FILE   = BASE_DIR / "history.json"
PROFILES_FILE  = BASE_DIR / "symbol_profiles.json"

for _d in (BASE_DIR, OUTPUT_DIR):
    _d.mkdir(parents=True, exist_ok=True)

# ── Emoji map (versioned) ─────────────────────────────────────────────────────
EMOJI_MAP_VERSION = "1"
# Every printable ASCII (0x20–0x7E) gets a unique emoji.
_EMOJI_CHARS = [
    "😀","😁","😂","🤣","😃","😄","😅","😆","😉","😊","😋","😎","😍","😘","🥰","😗",
    "😙","😚","🙂","🤗","🤩","🤔","🤨","😐","😑","😶","🙄","😏","😣","😥","😮","🤐",
    "😯","😪","😫","🥱","😴","😌","😛","😜","😝","🤤","😒","😓","😔","😕","🙃","🤑",
    "😲","☹️","🙁","😖","😞","😟","😤","😢","😭","😦","😧","😨","😩","🤯","😬","😰",
    "😱","🥵","🥶","😳","🤪","😵","🥴","😠","😡","🤬","😷","🤒","🤕","🤢","🤮","🤧",
    "🥳","🥸","🤠","😈","👿","👹","👺","💀","☠️","👻","👽","👾","🤖","🎃","😺","😸",
]
# Build a deterministic mapping for all 95 printable ASCII characters
_ASCII_PRINTABLE = [chr(i) for i in range(0x20, 0x7F)]   # space..~
assert len(_EMOJI_CHARS) >= len(_ASCII_PRINTABLE), "Emoji pool too small"
EMOJI_ENCODE_MAP: dict[str, str] = {
    ch: _EMOJI_CHARS[i] for i, ch in enumerate(_ASCII_PRINTABLE)
}
EMOJI_DECODE_MAP: dict[str, str] = {v: k for k, v in EMOJI_ENCODE_MAP.items()}
# Sentinel so we can identify emoji-encoded files
EMOJI_HEADER = f"##CMORPH-EMOJI-v{EMOJI_MAP_VERSION}##\n"
# Non-ASCII passthrough marker used inside encoded text
_NON_ASCII_OPEN  = "\u2983"   # ｛
_NON_ASCII_CLOSE = "\u2984"   # ｝
_NEWLINE_TOKEN   = "🔚"        # represents a newline inside an encoded line


# ── History helpers ────────────────────────────────────────────────────────────
def _load_history() -> list:
    if HISTORY_FILE.exists():
        try:
            return json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
        except Exception:
            return []
    return []

def _save_history(records: list) -> None:
    HISTORY_FILE.write_text(json.dumps(records, ensure_ascii=False, indent=2),
                            encoding="utf-8")

def _add_history(op: str, src: str, dst: str, fmt: str) -> None:
    records = _load_history()
    records.append({
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "operation": op,
        "source":    src,
        "output":    dst,
        "format":    fmt,
    })
    records = records[-500:]   # keep last 500 entries
    _save_history(records)


# ── Symbol-profile helpers ─────────────────────────────────────────────────────
def _load_profiles() -> dict:
    if PROFILES_FILE.exists():
        try:
            return json.loads(PROFILES_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}

def _save_profiles(profiles: dict) -> None:
    PROFILES_FILE.write_text(json.dumps(profiles, ensure_ascii=False, indent=2),
                             encoding="utf-8")


# ─────────────────────────────────────────────────────────────────────────────
#   ENCODERS / DECODERS
# ─────────────────────────────────────────────────────────────────────────────

# ── Binary ────────────────────────────────────────────────────────────────────
BINARY_HEADER = "##CMORPH-BINARY-v1##\n"

def encode_binary(text: str) -> str:
    encoded_bytes = text.encode("utf-8")
    bits = " ".join(f"{b:08b}" for b in encoded_bytes)
    return BINARY_HEADER + bits

def decode_binary(text: str) -> str:
    text = text.strip()
    if text.startswith(BINARY_HEADER.strip()):
        text = text[len(BINARY_HEADER.strip()):].strip()
    tokens = text.split()
    try:
        byte_vals = [int(t, 2) for t in tokens if t]
        return bytes(byte_vals).decode("utf-8")
    except (ValueError, UnicodeDecodeError) as exc:
        raise ValueError(f"Binary decode failed: {exc}") from exc


# ── Hexadecimal ───────────────────────────────────────────────────────────────
HEX_HEADER = "##CMORPH-HEX-v1##\n"

def encode_hex(text: str) -> str:
    return HEX_HEADER + text.encode("utf-8").hex()

def decode_hex(text: str) -> str:
    text = text.strip()
    if text.startswith(HEX_HEADER.strip()):
        text = text[len(HEX_HEADER.strip()):].strip()
    try:
        return bytes.fromhex(text).decode("utf-8")
    except (ValueError, UnicodeDecodeError) as exc:
        raise ValueError(f"Hex decode failed: {exc}") from exc


# ── Base64 ────────────────────────────────────────────────────────────────────
B64_HEADER = "##CMORPH-BASE64-v1##\n"

def encode_base64(text: str) -> str:
    return B64_HEADER + base64.b64encode(text.encode("utf-8")).decode("ascii")

def decode_base64(text: str) -> str:
    text = text.strip()
    if text.startswith(B64_HEADER.strip()):
        text = text[len(B64_HEADER.strip()):].strip()
    try:
        return base64.b64decode(text).decode("utf-8")
    except Exception as exc:
        raise ValueError(f"Base64 decode failed: {exc}") from exc


# ── Unicode escapes ───────────────────────────────────────────────────────────
UNICODE_HEADER = "##CMORPH-UNICODE-v1##\n"

def encode_unicode_escape(text: str) -> str:
    # Encode to bytes then escape; we also encode the length so we can
    # restore the exact original (including leading/trailing whitespace).
    escaped = text.encode("unicode_escape").decode("ascii")
    # Store char-count so decoding can verify, but we rely on the escaped
    # representation being exact.  Leading spaces in the escaped form are
    # safe because \x20 is a valid escape.
    return UNICODE_HEADER + escaped

def decode_unicode_escape(text: str) -> str:
    # Strip ONLY the header line, not any whitespace in the payload.
    if text.startswith(UNICODE_HEADER):
        text = text[len(UNICODE_HEADER):]
    elif text.startswith(UNICODE_HEADER.strip()):
        # Header without trailing newline (e.g. after .strip() elsewhere)
        text = text[len(UNICODE_HEADER.strip()):]
        if text.startswith("\n"):
            text = text[1:]
    try:
        # encode("raw_unicode_escape") → bytes that we then decode with
        # "unicode_escape".  This avoids Python 3's strict ASCII check on
        # the intermediate bytes object and correctly handles \uXXXX.
        return text.encode("raw_unicode_escape").decode("unicode_escape")
    except Exception as exc:
        raise ValueError(f"Unicode-escape decode failed: {exc}") from exc


# ── Emoji encoder (reversible) ────────────────────────────────────────────────
# Pre-build sorted decode keys (longest first) for O(n) greedy scan
_EMOJI_DECODE_SORTED = sorted(EMOJI_DECODE_MAP.keys(), key=len, reverse=True)

def encode_emoji(text: str) -> str:
    """
    Encode text to emoji.
    - ASCII printable chars → emoji from EMOJI_ENCODE_MAP.
    - Non-ASCII chars → ｛U+XXXX｝ passthrough blocks.
    - Newlines are encoded as literal \\n sequences so the line structure
      of the encoded output is a single line per *encoded* block, avoiding
      off-by-one issues with trailing newlines.
    """
    out: list[str] = []
    for ch in text:
        if ch == "\n":
            # Represent newline as a passthrough escape so we never split on it
            out.append(f"{_NON_ASCII_OPEN}\\n{_NON_ASCII_CLOSE}")
        elif ch == "\r":
            out.append(f"{_NON_ASCII_OPEN}\\r{_NON_ASCII_CLOSE}")
        else:
            mapped = EMOJI_ENCODE_MAP.get(ch)
            if mapped:
                out.append(mapped)
            else:
                cp = f"U+{ord(ch):04X}"
                out.append(f"{_NON_ASCII_OPEN}{cp}{_NON_ASCII_CLOSE}")
    # The whole encoded payload fits on one line; header on its own line
    return EMOJI_HEADER + "".join(out)

def decode_emoji(text: str) -> str:
    # Strip exactly the header line (preserving any embedded \\n escapes)
    if text.startswith(EMOJI_HEADER):
        text = text[len(EMOJI_HEADER):]
    elif text.startswith(EMOJI_HEADER.rstrip("\n")):
        text = text[len(EMOJI_HEADER.rstrip("\n")):]
        if text.startswith("\n"):
            text = text[1:]

    out: list[str] = []
    pos = 0
    while pos < len(text):
        # Check for passthrough block: ｛...｝
        if text[pos] == _NON_ASCII_OPEN:
            end = text.find(_NON_ASCII_CLOSE, pos)
            if end == -1:
                raise ValueError("Malformed emoji-encoded text: unclosed passthrough block.")
            inner = text[pos+1:end]
            if inner == "\\n":
                out.append("\n")
            elif inner == "\\r":
                out.append("\r")
            elif inner.startswith("U+"):
                try:
                    cp_val = int(inner[2:], 16)
                    out.append(chr(cp_val))
                except ValueError as exc:
                    raise ValueError(f"Bad codepoint in emoji encoding: {inner}") from exc
            else:
                raise ValueError(f"Unknown passthrough block: {inner!r}")
            pos = end + 1
        else:
            # Greedy match against known emoji (longest first)
            matched = False
            for sym in _EMOJI_DECODE_SORTED:
                if text[pos:pos+len(sym)] == sym:
                    out.append(EMOJI_DECODE_MAP[sym])
                    pos += len(sym)
                    matched = True
                    break
            if not matched:
                # Literal char passthrough (shouldn't happen in well-formed input)
                out.append(text[pos])
                pos += 1
    return "".join(out)


# ── Custom-symbol encoder ─────────────────────────────────────────────────────
SYMBOL_HEADER_TPL = "##CMORPH-SYMBOL-v1:{profile_name}##\n"

def encode_symbol(text: str, profile_name: str, mapping: dict[str, str]) -> str:
    """mapping: {original_char -> symbol}"""
    rev = {v: k for k, v in mapping.items()}
    if len(rev) != len(mapping):
        raise ValueError("Symbol mapping is not 1-to-1 (duplicate symbol values).")
    out: list[str] = []
    for ch in text:
        out.append(mapping.get(ch, ch))
    header = SYMBOL_HEADER_TPL.format(profile_name=profile_name)
    return header + "".join(out)

def decode_symbol(text: str, mapping: dict[str, str]) -> str:
    """mapping: {original_char -> symbol}  — we invert it."""
    reverse: dict[str, str] = {v: k for k, v in mapping.items()}
    # Sort by symbol length descending so longer symbols match first.
    sorted_syms = sorted(reverse.keys(), key=len, reverse=True)
    # Strip header
    if text.startswith("##CMORPH-SYMBOL-v1:"):
        nl = text.find("\n")
        if nl != -1:
            text = text[nl+1:]
    out: list[str] = []
    pos = 0
    while pos < len(text):
        matched = False
        for sym in sorted_syms:
            slen = len(sym)
            if text[pos:pos+slen] == sym:
                out.append(reverse[sym])
                pos += slen
                matched = True
                break
        if not matched:
            # Character has no mapping — pass through unchanged.
            # IMPORTANT: we must NOT try to re-match after appending,
            # so we advance by exactly 1 code point.
            out.append(text[pos])
            pos += 1
    return "".join(out)


# ─────────────────────────────────────────────────────────────────────────────
#   FORMAT DETECTION
# ─────────────────────────────────────────────────────────────────────────────
def detect_format(text: str) -> Optional[str]:
    """Return format tag if the text starts with a known CODE MORPHER header."""
    t = text.strip()
    if t.startswith(BINARY_HEADER.strip()):  return "binary"
    if t.startswith(HEX_HEADER.strip()):     return "hex"
    if t.startswith(B64_HEADER.strip()):     return "base64"
    if t.startswith(UNICODE_HEADER.strip()): return "unicode"
    if t.startswith(EMOJI_HEADER.strip()):   return "emoji"
    if t.startswith("##CMORPH-SYMBOL-v1:"):  return "symbol"
    return None


# ─────────────────────────────────────────────────────────────────────────────
#   FILE HELPERS
# ─────────────────────────────────────────────────────────────────────────────
def safe_write(path: Path, content: str) -> bool:
    """Write to path; ask for confirmation if it exists. Returns True on success."""
    if path.exists():
        if not Confirm.ask(f"[yellow]File exists:[/] {path.name} — overwrite?"):
            return False
    try:
        path.write_text(content, encoding="utf-8")
        return True
    except PermissionError as exc:
        console.print(f"[red]Permission denied:[/] {exc}")
        return False

def suggest_filename(stem: str, suffix: str, directory: Path) -> Path:
    """Return a non-colliding filename (appends _2, _3, … if needed)."""
    candidate = directory / f"{stem}{suffix}"
    if not candidate.exists():
        return candidate
    n = 2
    while True:
        candidate = directory / f"{stem}_{n}{suffix}"
        if not candidate.exists():
            return candidate
        n += 1

def read_file_safe(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except PermissionError as exc:
        raise PermissionError(f"Cannot read {path}: {exc}") from exc
    except UnicodeDecodeError:
        raise ValueError(f"File {path.name} is not valid UTF-8 text.")


# ─────────────────────────────────────────────────────────────────────────────
#   INPUT HELPERS
# ─────────────────────────────────────────────────────────────────────────────
def get_multiline_input(prompt_text: str = "Paste text (end with a line containing only `END`):") -> str:
    console.print(f"\n[bold cyan]{prompt_text}[/]")
    console.print("[dim]Type END on its own line when done.[/dim]\n")
    lines: list[str] = []
    while True:
        try:
            line = input()
        except EOFError:
            break
        if line == "END":
            break
        lines.append(line)
    return "\n".join(lines)

def get_text_or_file() -> tuple[str, str]:
    """Return (text_content, source_label).  Asks user for paste vs file."""
    choice = Prompt.ask(
        "Input source",
        choices=["paste", "file"],
        default="paste",
    )
    if choice == "paste":
        text = get_multiline_input()
        if not text:
            raise ValueError("No text was entered.")
        return text, "<pasted>"
    else:
        file_path_str = Prompt.ask("Enter file path")
        p = Path(file_path_str).expanduser()
        if not p.exists():
            raise FileNotFoundError(f"File not found: {p}")
        return read_file_safe(p), str(p)


# ─────────────────────────────────────────────────────────────────────────────
#   PREVIEW & SAVE
# ─────────────────────────────────────────────────────────────────────────────
def preview_output(output: str, title: str = "Preview") -> None:
    preview = output[:2000]
    truncated = len(output) > 2000
    syntax = Syntax(preview, "text", theme="monokai", word_wrap=True)
    console.print(Panel(syntax, title=f"[bold magenta]{title}[/]", border_style="magenta"))
    if truncated:
        console.print(f"[dim]… (truncated; full output is {len(output):,} chars)[/dim]")

def save_output(output: str, suggested_stem: str, ext: str = ".txt",
                source_label: str = "", fmt: str = "") -> Optional[Path]:
    suggested = suggest_filename(suggested_stem, ext, OUTPUT_DIR)
    console.print(f"\n[dim]Suggested filename:[/] [bold]{suggested.name}[/]")
    name = Prompt.ask("Save as (press Enter to accept)", default=suggested.name)
    dest = OUTPUT_DIR / name
    if safe_write(dest, output):
        console.print(f"[green]✓ Saved:[/] {dest}")
        _add_history("encode", source_label, str(dest), fmt)
        return dest
    return None


# ─────────────────────────────────────────────────────────────────────────────
#   ENCODE WORKFLOW
# ─────────────────────────────────────────────────────────────────────────────
def workflow_encode() -> None:
    console.print(Rule("[bold cyan]ENCODE / CONVERT[/]"))
    # Format selection
    table = Table(box=box.SIMPLE, show_header=False)
    formats = [
        ("1", "Binary",          "0s and 1s"),
        ("2", "Hexadecimal",     "base-16 hex digits"),
        ("3", "Base64",          "ASCII-safe base-64"),
        ("4", "Unicode escapes", r"\uXXXX / \UXXXXXXXX sequences"),
        ("5", "Emoji",           "printable ASCII → emoji (reversible)"),
        ("6", "Custom symbol",   "user-defined character substitution"),
    ]
    for num, name, desc in formats:
        table.add_row(f"[bold cyan]{num}[/]", f"[bold]{name}[/]", f"[dim]{desc}[/]")
    console.print(table)
    console.print("[dim]Note: encoding is NOT encryption — anyone with this tool can reverse it.[/dim]\n")
    fmt_choice = Prompt.ask("Choose format", choices=[str(i) for i in range(1, 7)])

    # Load symbol profile if needed
    profile_name, mapping = "", {}
    if fmt_choice == "6":
        profiles = _load_profiles()
        if not profiles:
            console.print("[yellow]No profiles saved. Let's create one now.[/]")
            profile_name, mapping = _create_symbol_profile()
        else:
            profile_names = list(profiles.keys())
            for i, n in enumerate(profile_names, 1):
                console.print(f"  [cyan]{i}[/] {n}")
            console.print(f"  [cyan]{len(profile_names)+1}[/] Create new profile")
            sel = Prompt.ask("Choose profile", choices=[str(i) for i in range(1, len(profile_names)+2)])
            idx = int(sel) - 1
            if idx < len(profile_names):
                profile_name = profile_names[idx]
                mapping = profiles[profile_name]
            else:
                profile_name, mapping = _create_symbol_profile()

    # Get input
    try:
        text, source_label = get_text_or_file()
    except (FileNotFoundError, ValueError, PermissionError) as exc:
        console.print(f"[red]Error:[/] {exc}")
        return

    # Encode
    fmt_map = {"1": "binary", "2": "hex", "3": "base64",
               "4": "unicode", "5": "emoji", "6": "symbol"}
    fmt = fmt_map[fmt_choice]
    try:
        with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"),
                      transient=True, console=console) as prog:
            prog.add_task("Converting…", total=None)
            if fmt == "binary":    output = encode_binary(text)
            elif fmt == "hex":     output = encode_hex(text)
            elif fmt == "base64":  output = encode_base64(text)
            elif fmt == "unicode": output = encode_unicode_escape(text)
            elif fmt == "emoji":   output = encode_emoji(text)
            else:                  output = encode_symbol(text, profile_name, mapping)
    except Exception as exc:
        console.print(f"[red]Encoding error:[/] {exc}")
        return

    preview_output(output, title=f"Encoded ({fmt.upper()})")
    if Confirm.ask("Save this output?", default=True):
        stem = f"encoded_{fmt}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        save_output(output, stem, ".txt", source_label, fmt)


# ─────────────────────────────────────────────────────────────────────────────
#   DECODE WORKFLOW
# ─────────────────────────────────────────────────────────────────────────────
def workflow_decode() -> None:
    console.print(Rule("[bold green]DECODE / RESTORE[/]"))
    try:
        text, source_label = get_text_or_file()
    except (FileNotFoundError, ValueError, PermissionError) as exc:
        console.print(f"[red]Error:[/] {exc}")
        return

    fmt = detect_format(text)
    if fmt:
        console.print(f"[green]Detected format:[/] [bold]{fmt}[/]")
    else:
        console.print("[yellow]Format not auto-detected. Choose manually:[/]")
        choices = ["binary", "hex", "base64", "unicode", "emoji", "symbol"]
        for i, c in enumerate(choices, 1):
            console.print(f"  [cyan]{i}[/] {c}")
        sel = Prompt.ask("Format", choices=[str(i) for i in range(1, 7)])
        fmt = choices[int(sel)-1]

    # For symbol, we need the profile
    mapping = {}
    if fmt == "symbol":
        profiles = _load_profiles()
        # Try to extract profile name from header
        detected_profile = None
        for line in text.splitlines()[:1]:
            if line.startswith("##CMORPH-SYMBOL-v1:"):
                detected_profile = line.split(":")[1].rstrip("#").strip()
        if detected_profile and detected_profile in profiles:
            console.print(f"[green]Using profile:[/] {detected_profile}")
            mapping = profiles[detected_profile]
        else:
            profile_names = list(profiles.keys())
            if not profile_names:
                console.print("[red]No symbol profiles found. Cannot decode.[/]")
                return
            for i, n in enumerate(profile_names, 1):
                console.print(f"  [cyan]{i}[/] {n}")
            sel = Prompt.ask("Choose profile for decoding", choices=[str(i) for i in range(1, len(profile_names)+1)])
            mapping = profiles[profile_names[int(sel)-1]]

    try:
        with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"),
                      transient=True, console=console) as prog:
            prog.add_task("Decoding…", total=None)
            if fmt == "binary":    output = decode_binary(text)
            elif fmt == "hex":     output = decode_hex(text)
            elif fmt == "base64":  output = decode_base64(text)
            elif fmt == "unicode": output = decode_unicode_escape(text)
            elif fmt == "emoji":   output = decode_emoji(text)
            else:                  output = decode_symbol(text, mapping)
    except Exception as exc:
        console.print(f"[red]Decode error:[/] {exc}")
        return

    preview_output(output, title="Decoded Output")
    if Confirm.ask("Save decoded output?", default=True):
        stem = f"decoded_{fmt}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        save_output(output, stem, ".txt", source_label, f"decode:{fmt}")


# ─────────────────────────────────────────────────────────────────────────────
#   BATCH CONVERSION
# ─────────────────────────────────────────────────────────────────────────────
def workflow_batch() -> None:
    console.print(Rule("[bold yellow]BATCH CONVERSION[/]"))
    dir_str = Prompt.ask("Directory containing files to convert")
    src_dir = Path(dir_str).expanduser()
    if not src_dir.is_dir():
        console.print(f"[red]Not a directory:[/] {src_dir}")
        return
    pattern = Prompt.ask("File pattern (e.g. *.txt, *.py)", default="*.txt")
    files = sorted(src_dir.glob(pattern))
    if not files:
        console.print("[yellow]No matching files found.[/]")
        return
    console.print(f"\n[cyan]{len(files)}[/] file(s) found:")
    for f in files:
        console.print(f"  • {f.name}")

    op = Prompt.ask("Operation", choices=["encode", "decode"], default="encode")
    fmt = ""
    if op == "encode":
        choices = ["binary", "hex", "base64", "unicode", "emoji", "symbol"]
        for i, c in enumerate(choices, 1):
            console.print(f"  [cyan]{i}[/] {c}")
        sel = Prompt.ask("Format", choices=[str(i) for i in range(1, 7)])
        fmt = choices[int(sel)-1]

    profile_name, mapping = "", {}
    if fmt == "symbol":
        profiles = _load_profiles()
        if not profiles:
            console.print("[yellow]No profiles. Create one first.[/]")
            profile_name, mapping = _create_symbol_profile()
        else:
            pnames = list(profiles.keys())
            for i, n in enumerate(pnames, 1):
                console.print(f"  [cyan]{i}[/] {n}")
            sel = Prompt.ask("Profile", choices=[str(i) for i in range(1, len(pnames)+1)])
            profile_name = pnames[int(sel)-1]
            mapping = profiles[profile_name]

    success, fail = 0, 0
    for fp in files:
        try:
            text = read_file_safe(fp)
            if op == "encode":
                if fmt == "binary":    out = encode_binary(text)
                elif fmt == "hex":     out = encode_hex(text)
                elif fmt == "base64":  out = encode_base64(text)
                elif fmt == "unicode": out = encode_unicode_escape(text)
                elif fmt == "emoji":   out = encode_emoji(text)
                else:                  out = encode_symbol(text, profile_name, mapping)
                stem = f"{fp.stem}_encoded_{fmt}"
            else:
                detected = detect_format(text)
                if detected is None:
                    console.print(f"[yellow]Skipping {fp.name}: unknown format[/]")
                    fail += 1
                    continue
                fmt_used = detected
                if fmt_used == "binary":    out = decode_binary(text)
                elif fmt_used == "hex":     out = decode_hex(text)
                elif fmt_used == "base64":  out = decode_base64(text)
                elif fmt_used == "unicode": out = decode_unicode_escape(text)
                elif fmt_used == "emoji":   out = decode_emoji(text)
                else:
                    console.print(f"[yellow]Skipping {fp.name}: symbol profile unknown[/]")
                    fail += 1
                    continue
                stem = f"{fp.stem}_decoded"
            dest = suggest_filename(stem, fp.suffix or ".txt", OUTPUT_DIR)
            dest.write_text(out, encoding="utf-8")
            _add_history(op, str(fp), str(dest), fmt)
            console.print(f"[green]✓[/] {fp.name} → {dest.name}")
            success += 1
        except Exception as exc:
            console.print(f"[red]✗[/] {fp.name}: {exc}")
            fail += 1
    console.print(f"\n[bold]Done.[/] {success} succeeded, {fail} failed.")


# ─────────────────────────────────────────────────────────────────────────────
#   OUTPUT FILE MANAGEMENT
# ─────────────────────────────────────────────────────────────────────────────
def workflow_manage_files() -> None:
    console.print(Rule("[bold blue]MANAGE OUTPUT FILES[/]"))
    files = sorted(OUTPUT_DIR.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True)
    files = [f for f in files if f.is_file()]
    if not files:
        console.print("[dim]No output files yet.[/dim]")
        return

    table = Table(box=box.SIMPLE, show_lines=False)
    table.add_column("#", style="cyan", width=4)
    table.add_column("Filename", style="bold")
    table.add_column("Size", justify="right", style="dim")
    table.add_column("Modified", style="dim")
    for i, f in enumerate(files, 1):
        stat = f.stat()
        size = f"{stat.st_size:,} B"
        mtime = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M")
        table.add_row(str(i), f.name, size, mtime)
    console.print(table)

    action = Prompt.ask("Action", choices=["view", "delete", "back"], default="back")
    if action == "back":
        return
    sel = Prompt.ask(f"File number (1-{len(files)})")
    try:
        idx = int(sel) - 1
        chosen = files[idx]
    except (ValueError, IndexError):
        console.print("[red]Invalid selection.[/]")
        return

    if action == "view":
        try:
            content = read_file_safe(chosen)
            preview_output(content, title=chosen.name)
        except Exception as exc:
            console.print(f"[red]Error reading file:[/] {exc}")
    elif action == "delete":
        if Confirm.ask(f"[red]Delete {chosen.name}?[/]", default=False):
            chosen.unlink()
            console.print(f"[green]Deleted:[/] {chosen.name}")


# ─────────────────────────────────────────────────────────────────────────────
#   HISTORY
# ─────────────────────────────────────────────────────────────────────────────
def workflow_history() -> None:
    console.print(Rule("[bold magenta]CONVERSION HISTORY[/]"))
    records = _load_history()
    if not records:
        console.print("[dim]No history yet.[/dim]")
        return
    # Show last 20 most recent first
    recent = records[-20:][::-1]
    table = Table(box=box.SIMPLE)
    table.add_column("Time", style="dim", width=19)
    table.add_column("Op", style="cyan", width=7)
    table.add_column("Format", style="bold", width=10)
    table.add_column("Source / Output", overflow="fold")
    for r in recent:
        op = r.get("operation", "")
        table.add_row(
            r.get("timestamp", ""),
            op,
            r.get("format", ""),
            f"{r.get('source','')}  →  {r.get('output','')}",
        )
    console.print(table)
    if Confirm.ask("Clear all history?", default=False):
        _save_history([])
        console.print("[green]History cleared.[/]")


# ─────────────────────────────────────────────────────────────────────────────
#   SYMBOL PROFILE MANAGEMENT
# ─────────────────────────────────────────────────────────────────────────────
def _create_symbol_profile() -> tuple[str, dict]:
    """Interactive wizard to create a symbol mapping profile. Returns (name, mapping)."""
    console.print("\n[bold]Create a symbol mapping profile[/]")
    console.print("[dim]You'll define a set of character → symbol substitutions.[/dim]")
    profile_name = Prompt.ask("Profile name (e.g. 'mycode')")
    console.print(
        "Enter mappings one per line as: [bold]char=symbol[/bold]\n"
        "Examples:  a=@   e=3   o=0   s=$   (char is a single character)\n"
        "Type [bold]DONE[/bold] when finished.\n"
    )
    mapping: dict[str, str] = {}
    seen_symbols: set[str] = set()
    while True:
        raw = input("  Mapping (char=symbol): ").strip()
        if raw.upper() == "DONE":
            break
        if "=" not in raw:
            console.print("[yellow]  Format must be char=symbol[/]")
            continue
        orig, sym = raw.split("=", 1)
        if not orig:
            console.print("[yellow]  Original character cannot be empty.[/]")
            continue
        if len(orig) != 1:
            console.print(f"[yellow]  '{orig}' must be exactly one character.[/]")
            continue
        if not sym:
            console.print("[yellow]  Symbol cannot be empty.[/]")
            continue
        if sym in seen_symbols:
            console.print(f"[yellow]  Symbol '{sym}' is already used. Symbols must be unique.[/]")
            continue
        mapping[orig] = sym
        seen_symbols.add(sym)
        console.print(f"  [green]Added:[/] '{orig}' → '{sym}'")
    if not mapping:
        raise ValueError("No mappings defined.")
    profiles = _load_profiles()
    profiles[profile_name] = mapping
    _save_profiles(profiles)
    console.print(f"[green]Profile '{profile_name}' saved with {len(mapping)} mappings.[/]")
    return profile_name, mapping

def workflow_profiles() -> None:
    console.print(Rule("[bold yellow]SYMBOL PROFILES[/]"))
    profiles = _load_profiles()
    action = Prompt.ask("Action", choices=["list", "create", "delete", "back"], default="list")
    if action == "back":
        return
    if action == "list":
        if not profiles:
            console.print("[dim]No profiles saved.[/dim]")
            return
        for name, mp in profiles.items():
            console.print(f"\n[bold cyan]{name}[/] ({len(mp)} mappings)")
            for orig, sym in list(mp.items())[:10]:
                console.print(f"  '{orig}' → '{sym}'")
            if len(mp) > 10:
                console.print(f"  [dim]… and {len(mp)-10} more[/]")
    elif action == "create":
        try:
            _create_symbol_profile()
        except ValueError as exc:
            console.print(f"[red]{exc}[/]")
    elif action == "delete":
        if not profiles:
            console.print("[dim]No profiles to delete.[/dim]")
            return
        names = list(profiles.keys())
        for i, n in enumerate(names, 1):
            console.print(f"  [cyan]{i}[/] {n}")
        sel = Prompt.ask("Profile to delete", choices=[str(i) for i in range(1, len(names)+1)])
        name = names[int(sel)-1]
        if Confirm.ask(f"[red]Delete profile '{name}'?[/]", default=False):
            del profiles[name]
            _save_profiles(profiles)
            console.print(f"[green]Deleted profile '{name}'.[/]")


# ─────────────────────────────────────────────────────────────────────────────
#   ABOUT
# ─────────────────────────────────────────────────────────────────────────────
def show_about() -> None:
    console.print(Panel(
        Text.assemble(
            ("CODE MORPHER ", "bold magenta"),
            (f"v{__version__}\n\n", "dim"),
            ("A code and text conversion tool for Termux on Android.\n\n", ""),
            ("⚠  IMPORTANT: Encoding is NOT encryption.\n", "bold yellow"),
            ("   Outputs can be reversed by anyone with this tool.\n\n", "dim"),
            ("Supported formats:\n", "bold"),
            ("  • Binary (0/1 bits)\n", ""),
            ("  • Hexadecimal (base-16)\n", ""),
            ("  • Base64 (ASCII-safe)\n", ""),
            ("  • Unicode escapes (\\uXXXX)\n", ""),
            ("  • Emoji substitution (reversible, versioned)\n", ""),
            ("  • Custom symbol profiles (user-defined)\n\n", ""),
            ("Files are saved to: ", "dim"),
            (str(OUTPUT_DIR) + "\n", "bold"),
            ("History: ", "dim"),
            (str(HISTORY_FILE), "bold"),
        ),
        title="[bold]About Code Morpher[/]",
        border_style="magenta",
    ))
    input("\nPress Enter to return to menu…")


# ─────────────────────────────────────────────────────────────────────────────
#   MAIN MENU
# ─────────────────────────────────────────────────────────────────────────────
BANNER = r"""
  ██████╗ ██████╗ ██████╗ ███████╗    ███╗   ███╗ ██████╗ ██████╗ ██████╗ ██╗  ██╗███████╗██████╗
 ██╔════╝██╔═══██╗██╔══██╗██╔════╝    ████╗ ████║██╔═══██╗██╔══██╗██╔══██╗██║  ██║██╔════╝██╔══██╗
 ██║     ██║   ██║██║  ██║█████╗      ██╔████╔██║██║   ██║██████╔╝██████╔╝███████║█████╗  ██████╔╝
 ██║     ██║   ██║██║  ██║██╔══╝      ██║╚██╔╝██║██║   ██║██╔══██╗██╔═══╝ ██╔══██║██╔══╝  ██╔══██╗
 ╚██████╗╚██████╔╝██████╔╝███████╗    ██║ ╚═╝ ██║╚██████╔╝██║  ██║██║     ██║  ██║███████╗██║  ██║
  ╚═════╝ ╚═════╝ ╚═════╝ ╚══════╝    ╚═╝     ╚═╝ ╚═════╝ ╚═╝  ╚═╝╚═╝     ╚═╝  ╚═╝╚══════╝╚═╝  ╚═╝
"""

MENU_ITEMS = [
    ("1", "Encode / Convert text or file",    "cyan",    workflow_encode),
    ("2", "Decode / Restore encoded content", "green",   workflow_decode),
    ("3", "Batch conversion",                 "yellow",  workflow_batch),
    ("4", "Manage output files",              "blue",    workflow_manage_files),
    ("5", "View conversion history",          "magenta", workflow_history),
    ("6", "Manage symbol profiles",           "yellow",  workflow_profiles),
    ("7", "About",                            "dim",     show_about),
    ("q", "Quit",                             "red",     None),
]

def main_menu() -> None:
    while True:
        console.clear()
        # Compact banner on narrow screens
        w = shutil.get_terminal_size((80, 24)).columns
        if w >= 100:
            console.print(BANNER, style="bold magenta")
        else:
            console.print(Panel(
                "[bold magenta]CODE MORPHER[/]",
                subtitle=f"[dim]v{__version__} — text & code conversion[/dim]",
                border_style="magenta",
            ))

        console.print(f"[dim]Output dir:[/] {OUTPUT_DIR}\n")
        table = Table(box=box.ROUNDED, show_header=False, border_style="blue")
        table.add_column("Key", style="bold", width=4)
        table.add_column("Description")
        for key, desc, color, _ in MENU_ITEMS:
            table.add_row(f"[{color}]{key}[/]", f"[{color}]{desc}[/]")
        console.print(table)

        choice = Prompt.ask("\n[bold]Select[/]", default="q").strip().lower()
        for key, _, _, fn in MENU_ITEMS:
            if choice == key:
                if fn is None:
                    console.print("\n[bold red]Goodbye![/]")
                    sys.exit(0)
                try:
                    fn()
                except KeyboardInterrupt:
                    console.print("\n[yellow]Cancelled.[/]")
                except Exception as exc:
                    console.print(f"\n[red]Unexpected error:[/] {exc}")
                if fn is not show_about:
                    input("\nPress Enter to return to menu…")
                break
        else:
            console.print("[red]Invalid choice.[/]")


# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    try:
        main_menu()
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted. Goodbye![/]")
        sys.exit(0)
