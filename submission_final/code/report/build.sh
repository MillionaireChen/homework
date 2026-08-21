#!/usr/bin/env bash
# Build the report from source.
#
# Needs TeX Live with IEEEtran, pgfplots and xeCJK, plus a CJK font
# (Noto Sans CJK JP) because the report quotes Japanese examples inline.
# On Debian/Ubuntu:
#   apt-get install texlive-latex-recommended texlive-pictures \
#                   texlive-publishers texlive-lang-cjk texlive-lang-chinese \
#                   texlive-xetex fonts-noto-cjk
#
# All diagrams are TikZ and all charts are pgfplots; there are no image files
# to regenerate.

set -euo pipefail
cd "$(dirname "$0")"

xelatex -interaction=nonstopmode -halt-on-error report.tex
xelatex -interaction=nonstopmode -halt-on-error report.tex   # resolve refs
rm -f report.aux report.log report.out
cp report.pdf ../../report.pdf

echo "built: $(pwd)/report.pdf  ->  also copied to the submission root"
