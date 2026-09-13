#!/usr/bin/env bash
# Build <stem>.pdf from the rendered <stem>.tex. Default stem: main.
#
#   ./build.sh              # the full manuscript
#   ./build.sh main-8pp     # the 8-page submission build
#
# Run `python paper/render.py` first: main.tex is generated from main.tex.tmpl and every number in
# it is substituted from ../data. Editing main.tex directly will be overwritten. The 8-page build
# renders through the same script:
#
#   python paper/render.py --tmpl=main-8pp.tex.tmpl --out=main-8pp.tex
#
# Four passes, because bibtex needs an .aux and hyperref needs a settled .out. The last pass is
# the one whose exit status matters -- an earlier pass can write a PDF and a later one still
# fail, which is how a deterministic font error first looked intermittent here.
set -u

cd "$(dirname "$0")"

stem="${1:-main}"

# Logs are per-stem: a shared build3.log meant the 8-page build's page count and undefined-
# reference check could read the full manuscript's log and pass on the wrong evidence.
log() { if [ "$stem" = "main" ]; then echo "build$1.log"; else echo "$stem-build$1.log"; fi; }

if [ ! -f "$stem.tex" ]; then
    echo "$stem.tex missing -- run: python paper/render.py" >&2
    exit 1
fi

rm -f "$stem.pdf"

pdflatex -interaction=nonstopmode "$stem.tex" > "$(log 1)" 2>&1
bibtex "$stem"                                > "$(log _bib)" 2>&1
pdflatex -interaction=nonstopmode "$stem.tex" > "$(log 2)" 2>&1
pdflatex -interaction=nonstopmode "$stem.tex" > "$(log 3)" 2>&1

if [ ! -f "$stem.pdf" ]; then
    echo "BUILD FAILED -- no PDF produced. Errors:" >&2
    grep -E "^(!|! LaTeX Error|! pdfTeX error)" "$(log 3)" | head -20 >&2
    exit 1
fi

# Unresolved references render as "??" in the PDF and are easy to miss on a visual skim.
undef=$(grep -c -E "LaTeX Warning: (Citation|Reference) .* undefined" "$(log 3)" || true)
pages=$(grep -oE "Output written on .*\(([0-9]+) pages" "$(log 3)" | grep -oE "[0-9]+ pages" | grep -oE "[0-9]+")

echo "built $stem.pdf -- ${pages:-?} pages, $(stat -c%s "$stem.pdf") bytes"
if [ "$undef" -gt 0 ]; then
    echo "WARNING: $undef undefined citation/reference(s):"
    grep -E "LaTeX Warning: (Citation|Reference) .* undefined" "$(log 3)" | sort -u | head
    exit 1
fi
echo "all citations and references resolved"

# The sprint scores the first 8 pages; references and appendices fall outside that.
# The body's last page is marked by \label{probe:endbody}, so the limit is checked
# here rather than by eyeballing the PDF -- a trim anywhere in the body can push the
# Conclusion over without any other warning appearing.
BODY_PAGE_LIMIT=8
endbody=$(grep -oE "probe:endbody\}\{\{[^}]*\}\{[0-9]+\}" "$stem.aux" 2>/dev/null \
          | grep -oE "\{[0-9]+\}$" | tr -d '{}')
if [ -n "$endbody" ]; then
    if [ "$endbody" -gt "$BODY_PAGE_LIMIT" ]; then
        echo "BODY OVER LIMIT: ends on page $endbody, limit is $BODY_PAGE_LIMIT" >&2
        exit 1
    fi
    echo "body ends on page $endbody of $BODY_PAGE_LIMIT; references and appendices follow"
fi
