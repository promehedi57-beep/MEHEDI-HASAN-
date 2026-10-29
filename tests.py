#!/usr/bin/env python3
"""
Automated tests for Code Morpher — round-trip encoding/decoding and file operations.
Run with:  python tests.py
"""

import json
import os
import sys
import tempfile
import traceback
from pathlib import Path

# ── Colour helpers (no external deps needed for tests) ─────────────────────
GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
RESET  = "\033[0m"

def ok(msg: str):  print(f"  {GREEN}✓{RESET}  {msg}")
def fail(msg: str): print(f"  {RED}✗  {msg}{RESET}")
def section(msg: str): print(f"\n{YELLOW}━━ {msg} ━━{RESET}")

# ── Import the module under test ──────────────────────────────────────────
# Patch BASE_DIR so tests don't touch the real user directory
import importlib, types

# We need to set a temp dir before importing main so pathlib globals work
_tmp_base = Path(tempfile.mkdtemp(prefix="cmorph_test_"))

import sys
sys.modules.pop("main", None)

# Monkey-patch: import main but override directory constants
import importlib.util
spec = importlib.util.spec_from_file_location(
    "main",
    Path(__file__).parent / "main.py",
)
main = importlib.util.module_from_spec(spec)  # type: ignore

# Before executing, override the paths
main.BASE_DIR   = _tmp_base
main.OUTPUT_DIR = _tmp_base / "outputs"
main.HISTORY_FILE  = _tmp_base / "history.json"
main.PROFILES_FILE = _tmp_base / "profiles.json"
(_tmp_base / "outputs").mkdir(parents=True, exist_ok=True)

spec.loader.exec_module(main)   # type: ignore

# ─────────────────────────────────────────────────────────────────────────────
PASS = 0
FAIL = 0

def assert_eq(label: str, actual, expected):
    global PASS, FAIL
    if actual == expected:
        ok(label)
        PASS += 1
    else:
        fail(f"{label}\n    expected: {expected!r}\n    got:      {actual!r}")
        FAIL += 1

def assert_no_raise(label: str, fn, *args, **kwargs):
    global PASS, FAIL
    try:
        result = fn(*args, **kwargs)
        ok(label)
        PASS += 1
        return result
    except Exception as exc:
        fail(f"{label} raised {type(exc).__name__}: {exc}")
        FAIL += 1
        return None

def assert_raises(label: str, exc_type, fn, *args, **kwargs):
    global PASS, FAIL
    try:
        fn(*args, **kwargs)
        fail(f"{label} — expected {exc_type.__name__} but none raised")
        FAIL += 1
    except exc_type:
        ok(label)
        PASS += 1
    except Exception as exc:
        fail(f"{label} — expected {exc_type.__name__} got {type(exc).__name__}: {exc}")
        FAIL += 1


# ─────────────────────────────────────────────────────────────────────────────
#  Test data
# ─────────────────────────────────────────────────────────────────────────────
SAMPLES = {
    "ascii":    "Hello, World! 123",
    "multiline": "Line one\nLine two\nLine three",
    "bengali":  "আমার সোনার বাংলা, আমি তোমায় ভালোবাসি",
    "emoji_text": "Coffee ☕ is great 🎉",
    "mixed":    "print('Hello') # সংখ্যা 42 🔥\n    x = [1, 2, 3]",
    "indented": "def foo():\n    if True:\n        return 42\n",
    "whitespace": "  leading\tand\ttabs  \n  more spaces  ",
    "special":  "!@#$%^&*()_+-=[]{}|;':\",./<>?",
    "empty":    "",
}


# ─────────────────────────────────────────────────────────────────────────────
section("Binary encode / decode")
# ─────────────────────────────────────────────────────────────────────────────
for name, text in SAMPLES.items():
    encoded = main.encode_binary(text)
    decoded = main.decode_binary(encoded)
    assert_eq(f"binary round-trip [{name}]", decoded, text)

assert_raises("binary decode bad input raises ValueError",
              ValueError, main.decode_binary, "not binary at all")


# ─────────────────────────────────────────────────────────────────────────────
section("Hexadecimal encode / decode")
# ─────────────────────────────────────────────────────────────────────────────
for name, text in SAMPLES.items():
    encoded = main.encode_hex(text)
    decoded = main.decode_hex(encoded)
    assert_eq(f"hex round-trip [{name}]", decoded, text)

assert_raises("hex decode garbage raises ValueError",
              ValueError, main.decode_hex, "xyz_not_hex")


# ─────────────────────────────────────────────────────────────────────────────
section("Base64 encode / decode")
# ─────────────────────────────────────────────────────────────────────────────
for name, text in SAMPLES.items():
    encoded = main.encode_base64(text)
    decoded = main.decode_base64(encoded)
    assert_eq(f"base64 round-trip [{name}]", decoded, text)

assert_raises("base64 decode bad padding raises ValueError",
              ValueError, main.decode_base64, "!!notbase64!!")


# ─────────────────────────────────────────────────────────────────────────────
section("Unicode-escape encode / decode")
# ─────────────────────────────────────────────────────────────────────────────
for name, text in SAMPLES.items():
    encoded = main.encode_unicode_escape(text)
    decoded = main.decode_unicode_escape(encoded)
    assert_eq(f"unicode-escape round-trip [{name}]", decoded, text)


# ─────────────────────────────────────────────────────────────────────────────
section("Emoji encode / decode")
# ─────────────────────────────────────────────────────────────────────────────
for name, text in SAMPLES.items():
    encoded = main.encode_emoji(text)
    decoded = main.decode_emoji(encoded)
    assert_eq(f"emoji round-trip [{name}]", decoded, text)

# Verify the header is present
enc = main.encode_emoji("test")
assert_eq("emoji header present", enc.startswith(main.EMOJI_HEADER), True)

# Verify it uses the correct map version
assert_eq("emoji version in header", f"v{main.EMOJI_MAP_VERSION}", "v1")

# Verify emoji map is bijective (no duplicate keys or values)
keys = list(main.EMOJI_ENCODE_MAP.keys())
vals = list(main.EMOJI_ENCODE_MAP.values())
assert_eq("emoji map: no duplicate originals", len(keys), len(set(keys)))
assert_eq("emoji map: no duplicate symbols",   len(vals), len(set(vals)))

# Verify that encode and decode maps are consistent inverses
for ch, emoji in main.EMOJI_ENCODE_MAP.items():
    if main.EMOJI_DECODE_MAP.get(emoji) != ch:
        fail(f"emoji map inconsistency for '{ch}'")
        FAIL += 1
        break
else:
    ok("emoji encode/decode maps are exact inverses")
    PASS += 1


# ─────────────────────────────────────────────────────────────────────────────
section("Symbol encode / decode")
# ─────────────────────────────────────────────────────────────────────────────
# Use a mapping whose symbols don't appear in any test sample as original chars
SIMPLE_MAPPING = {"a": "α", "e": "ε", "o": "θ", "i": "ι", "s": "σ"}
PROFILE_NAME = "test_profile"

for name, text in SAMPLES.items():
    encoded = main.encode_symbol(text, PROFILE_NAME, SIMPLE_MAPPING)
    decoded = main.decode_symbol(encoded, SIMPLE_MAPPING)
    assert_eq(f"symbol round-trip [{name}]", decoded, text)

# Duplicate symbol should raise
bad_mapping = {"a": "@", "b": "@"}
assert_raises("symbol encode with duplicate symbols raises ValueError",
              ValueError, main.encode_symbol, "hello", "bad", bad_mapping)


# ─────────────────────────────────────────────────────────────────────────────
section("Format detection")
# ─────────────────────────────────────────────────────────────────────────────
detect_cases = [
    ("binary",  main.encode_binary("test")),
    ("hex",     main.encode_hex("test")),
    ("base64",  main.encode_base64("test")),
    ("unicode", main.encode_unicode_escape("test")),
    ("emoji",   main.encode_emoji("test")),
    ("symbol",  main.encode_symbol("test", "p", {"t": "T"})),
]
for expected_fmt, encoded in detect_cases:
    detected = main.detect_format(encoded)
    assert_eq(f"detect_format [{expected_fmt}]", detected, expected_fmt)

assert_eq("detect_format [unknown]", main.detect_format("plain text"), None)


# ─────────────────────────────────────────────────────────────────────────────
section("File operations")
# ─────────────────────────────────────────────────────────────────────────────
tmp_out = _tmp_base / "outputs" / "test_output.txt"
content = "Test content 123\nLine 2\n"

# Write and read back
tmp_out.write_text(content, encoding="utf-8")
read_back = assert_no_raise("read_file_safe works", main.read_file_safe, tmp_out)
assert_eq("read_file_safe content matches", read_back, content)

# suggest_filename: first slot is free
stem_path = main.suggest_filename("new_file", ".txt", _tmp_base / "outputs")
assert_eq("suggest_filename on empty slot has no suffix",
          "_2" not in stem_path.name, True)

# suggest_filename: collision → _2
(_tmp_base / "outputs" / "col.txt").write_text("x")
result = main.suggest_filename("col", ".txt", _tmp_base / "outputs")
assert_eq("suggest_filename adds _2 on collision", result.name, "col_2.txt")

# Double collision → _3
(_tmp_base / "outputs" / "col_2.txt").write_text("x")
result2 = main.suggest_filename("col", ".txt", _tmp_base / "outputs")
assert_eq("suggest_filename adds _3 on double collision", result2.name, "col_3.txt")


# ─────────────────────────────────────────────────────────────────────────────
section("History")
# ─────────────────────────────────────────────────────────────────────────────
# Start clean
main.HISTORY_FILE.write_text("[]", encoding="utf-8")
main._add_history("encode", "src.txt", "out.txt", "binary")
records = main._load_history()
assert_eq("history has 1 entry", len(records), 1)
assert_eq("history op field", records[0]["operation"], "encode")
assert_eq("history fmt field", records[0]["format"], "binary")

# Overflow: capped at 500
main._save_history([])
for _ in range(505):
    main._add_history("test", "a", "b", "hex")
records = main._load_history()
assert_eq("history capped at 500", len(records), 500)


# ─────────────────────────────────────────────────────────────────────────────
section("Symbol profiles")
# ─────────────────────────────────────────────────────────────────────────────
main._save_profiles({})
main._save_profiles({"myprofile": {"a": "@", "b": "#"}})
loaded = main._load_profiles()
assert_eq("profiles saved and loaded", "myprofile" in loaded, True)
assert_eq("profiles content correct", loaded["myprofile"]["a"], "@")


# ─────────────────────────────────────────────────────────────────────────────
section("Large input handling")
# ─────────────────────────────────────────────────────────────────────────────
large = "A" * 100_000 + "বাংলা" * 5_000 + "\n" * 1_000
for fmt_name, enc_fn, dec_fn in [
    ("binary",  main.encode_binary,          main.decode_binary),
    ("hex",     main.encode_hex,             main.decode_hex),
    ("base64",  main.encode_base64,          main.decode_base64),
    ("emoji",   main.encode_emoji,           main.decode_emoji),
]:
    enc = assert_no_raise(f"large input encode [{fmt_name}]", enc_fn, large)
    if enc is not None:
        dec = assert_no_raise(f"large input decode [{fmt_name}]", dec_fn, enc)
        if dec is not None:
            assert_eq(f"large input round-trip [{fmt_name}]", dec == large, True)


# ─────────────────────────────────────────────────────────────────────────────
section("Edge cases")
# ─────────────────────────────────────────────────────────────────────────────
# Tabs and non-breaking spaces preserved
tricky = "col1\tcol2\tcol3\n\u00a0non-breaking\u00a0space"
for fmt_name, enc_fn, dec_fn in [
    ("binary",  main.encode_binary,  main.decode_binary),
    ("base64",  main.encode_base64,  main.decode_base64),
    ("unicode", main.encode_unicode_escape, main.decode_unicode_escape),
    ("emoji",   main.encode_emoji,   main.decode_emoji),
]:
    enc = enc_fn(tricky)
    dec = dec_fn(enc)
    assert_eq(f"tabs & nbsp preserved [{fmt_name}]", dec, tricky)

# Windows line endings preserved in binary/base64/hex (raw bytes)
crlf = "line1\r\nline2\r\n"
for fmt_name, enc_fn, dec_fn in [
    ("binary", main.encode_binary, main.decode_binary),
    ("hex",    main.encode_hex,    main.decode_hex),
    ("base64", main.encode_base64, main.decode_base64),
]:
    enc = enc_fn(crlf)
    dec = dec_fn(enc)
    assert_eq(f"CRLF preserved [{fmt_name}]", dec, crlf)


# ─────────────────────────────────────────────────────────────────────────────
# Cleanup temp dir
import shutil
shutil.rmtree(_tmp_base, ignore_errors=True)

# ─────────────────────────────────────────────────────────────────────────────
print(f"\n{'='*60}")
total = PASS + FAIL
pct   = int(100 * PASS / total) if total else 0
if FAIL == 0:
    print(f"{GREEN}ALL {PASS} TESTS PASSED ✓{RESET}")
else:
    print(f"{GREEN}{PASS} passed{RESET}, {RED}{FAIL} failed{RESET}  ({pct}% pass rate)")
print(f"{'='*60}\n")

sys.exit(0 if FAIL == 0 else 1)
