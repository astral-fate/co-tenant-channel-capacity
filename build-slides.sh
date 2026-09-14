#!/usr/bin/env bash
# Render slides.html to slides.pdf, one page per slide.
#
#   ./build-slides.sh
#
# The deck is authored as HTML because it carries live layout -- flex columns, gauges drawn in
# CSS -- that a slide tool would flatten. `.slide` sets `page-break-after: always`, so a browser's
# print path is the renderer: headless Chrome honours the page breaks and the print stylesheet,
# where a generic html-to-pdf converter drops the grid backgrounds and the break rules.
#
# --virtual-time-budget matters: without it Chrome can snapshot before fonts and layout settle,
# which shows up as a deck with the right text at the wrong sizes.
set -u
cd "$(dirname "$0")"

SRC="$(pwd)/slides.html"
# The compiled deck ships beside the manuscripts, so a reader finds it where the other
# documents are rather than loose at the repository root.
mkdir -p docs
OUT="$(pwd)/docs/slides.pdf"

CHROME=""
for c in \
  "/c/Program Files/Google/Chrome/Application/chrome.exe" \
  "/c/Program Files (x86)/Google/Chrome/Application/chrome.exe" \
  "/c/Program Files (x86)/Microsoft/Edge/Application/msedge.exe" \
  "/c/Program Files/Microsoft/Edge/Application/msedge.exe" \
  "$(command -v google-chrome || true)" \
  "$(command -v chromium || true)"
do
  [ -n "$c" ] && [ -x "$c" ] && CHROME="$c" && break
done

if [ -z "$CHROME" ]; then
    echo "no Chrome or Edge found -- open slides.html and print to PDF instead" >&2
    exit 1
fi

# Convert the path to a file:// URL Chrome accepts on Windows.
URL="file:///$(echo "$SRC" | sed 's|^/\([a-z]\)/|\1:/|' | sed 's| |%20|g')"

rm -f "$OUT"
"$CHROME" --headless --disable-gpu --no-pdf-header-footer --no-margins \
          --virtual-time-budget=15000 --print-to-pdf="$OUT" "$URL" >/dev/null 2>&1

if [ ! -f "$OUT" ]; then
    echo "BUILD FAILED -- no PDF produced" >&2
    exit 1
fi

# Count pages from the PDF and slides from the numbering stamp. `<section class="slide"` is the
# wrong marker: five slides carry a variant class and it silently undercounts by five.
#
# The interpreter is native Windows Python, so it cannot open the `/d/...` path this shell uses;
# hand it the drive-letter form, and via the environment rather than by interpolating a path with
# spaces into a -c string.
pages=$(PDF="$(echo "$OUT" | sed 's|^/\([a-z]\)/|\1:/|')" python -c "
import os, re
raw = open(os.environ['PDF'], 'rb').read()
print(len(re.findall(rb'/Type\s*/Page[^s]', raw)))
" 2>/dev/null || echo "?")
slides=$(grep -o 'slide-num\">[0-9]* / [0-9]*' "$SRC" | wc -l)

echo "built docs/slides.pdf -- $pages pages from $slides sections, $(stat -c%s "$OUT") bytes"

# A mismatch means a slide overflowed onto a second page, which is invisible in the HTML and
# obvious in the PDF only if you count. Worth failing on rather than shipping a deck whose
# numbering no longer matches its pages.
if [ "$pages" != "?" ] && [ "$pages" -ne "$slides" ]; then
    echo "WARNING: $pages pages from $slides slides -- a slide is overflowing" >&2
    exit 1
fi
