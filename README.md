# Newsletter mail-merge CLI

Renders a newsletter template once per recipient and writes each result to a local text file. See [SPEC.md](SPEC.md).

Requires Python 3.8+ and nothing outside the standard library.

```
./send.py --recipient-list examples/recipients.csv \
          --payload-template examples/newsletter.txt \
          --output-dir out
```

- **Recipient CSV**: no header row, exactly two columns: full name and email address. Blank lines are skipped. Quote names that contain commas.
- **Template**: plain text. `{FULL_NAME}` (or `{ FULL_NAME }`) is replaced with the recipient's name. Any other `{NAME}` placeholder is an error. Other braces are left as they are.
- **Output**: one file per recipient, `<email>.txt` (lowercased; characters outside `A-Za-z0-9@._+-` become `_`). The directory is created if it doesn't exist, and existing files are overwritten.

Input is fully validated before anything is written: wrong column counts, empty names, malformed or duplicate emails, and unsupported template variables all cause exit code 1 with an error message.

## Tests

```
python3 -m unittest discover -s tests
```
