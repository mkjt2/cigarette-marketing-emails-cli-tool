#!/usr/bin/env python3
"""Render a newsletter template mail-merge style, one text file per recipient.

Usage:
    ./send.py --recipient-list <csv_file> --payload-template <text_file> --output-dir <output_subdir>

The recipient CSV has no header row and exactly two columns: full name, email address.
The template supports a single `{FULL_NAME}` variable. Any other `{NAME}` placeholder
is rejected so that half-rendered emails never get written.
"""

import argparse
import csv
import re
import sys
from pathlib import Path

SUPPORTED_VARIABLES = {"FULL_NAME"}
PLACEHOLDER_RE = re.compile(r"\{\s*([A-Za-z_][A-Za-z0-9_]*)\s*\}")
# Deliberately loose: one "@", no whitespace, a dot in the domain.
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
# Characters allowed verbatim in output file names; everything else becomes "_".
UNSAFE_FILENAME_CHARS_RE = re.compile(r"[^A-Za-z0-9@._+-]")


class InputError(Exception):
    """Raised for invalid operator-supplied input."""


def load_recipients(csv_path):
    """Return a list of (full_name, email) tuples from a headerless two-column CSV."""
    recipients = []
    seen_emails = set()
    with open(csv_path, newline="", encoding="utf-8-sig") as f:
        for line_no, row in enumerate(csv.reader(f), start=1):
            if not row or all(not cell.strip() for cell in row):
                continue
            if len(row) != 2:
                raise InputError(
                    f"{csv_path}:{line_no}: expected 2 columns (full name, email), got {len(row)}"
                )
            full_name, email = (cell.strip() for cell in row)
            if not full_name:
                raise InputError(f"{csv_path}:{line_no}: full name is empty")
            if not EMAIL_RE.match(email):
                raise InputError(f"{csv_path}:{line_no}: invalid email address {email!r}")
            key = email.lower()
            if key in seen_emails:
                raise InputError(f"{csv_path}:{line_no}: duplicate email address {email!r}")
            seen_emails.add(key)
            recipients.append((full_name, email))
    if not recipients:
        raise InputError(f"{csv_path}: no recipients found")
    return recipients


def validate_template(template):
    """Raise InputError if the template uses any unsupported `{VARIABLE}`."""
    unknown = sorted(
        {m.group(1) for m in PLACEHOLDER_RE.finditer(template)} - SUPPORTED_VARIABLES
    )
    if unknown:
        names = ", ".join(f"{{{name}}}" for name in unknown)
        raise InputError(
            f"unsupported template variable(s): {names}; only {{FULL_NAME}} is supported"
        )


def render(template, full_name):
    # Substitute via regex rather than str.format so literal braces elsewhere survive.
    values = {"FULL_NAME": full_name}
    return PLACEHOLDER_RE.sub(lambda m: values.get(m.group(1), m.group(0)), template)


def output_filename(email):
    safe = UNSAFE_FILENAME_CHARS_RE.sub("_", email.lower())
    # Guard against names like "." or ".." that would escape or alias the output dir.
    if set(safe) <= {"."}:
        raise InputError(f"cannot derive a safe file name from {email!r}")
    return f"{safe}.txt"


def run(recipient_list, payload_template, output_dir):
    recipients = load_recipients(recipient_list)
    template = Path(payload_template).read_text(encoding="utf-8")
    validate_template(template)

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    written = []
    for full_name, email in recipients:
        path = out / output_filename(email)
        path.write_text(render(template, full_name), encoding="utf-8")
        written.append(path)
    return written


def parse_args(argv):
    parser = argparse.ArgumentParser(
        description="Render a newsletter template for each recipient into a local folder."
    )
    parser.add_argument(
        "--recipient-list",
        required=True,
        metavar="CSV_FILE",
        help="headerless CSV with two columns: full name, email address",
    )
    parser.add_argument(
        "--payload-template",
        required=True,
        metavar="TEXT_FILE",
        help="text email template; supports the {FULL_NAME} variable",
    )
    parser.add_argument(
        "--output-dir",
        required=True,
        metavar="OUTPUT_SUBDIR",
        help="directory for rendered emails (created if missing)",
    )
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    try:
        written = run(args.recipient_list, args.payload_template, args.output_dir)
    except (InputError, OSError, UnicodeDecodeError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    for path in written:
        print(path)
    print(f"Rendered {len(written)} email(s) to {args.output_dir}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
