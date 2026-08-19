#!/bin/sh
# Build the arXiv source bundle for the main paper: sources, figures, bib and the .bbl
# (arXiv compiles with pdflatex; the preamble is pdflatex-compatible).
cd "$(dirname "$0")/../paper" || exit 1
tectonic --keep-intermediates main.tex > /dev/null 2>&1 || tectonic -X compile --keep-intermediates main.tex
rm -rf arxiv && mkdir -p arxiv/sections arxiv/figures
cp main.tex main.bbl references.bib arxiv/ 2>/dev/null
cp sections/*.tex arxiv/sections/
for f in $(grep -oh "includegraphics\[[^]]*\]{[^}]*}" sections/*.tex | sed 's/.*{\(.*\)}/\1/' | sort -u); do cp "figures/$f" arxiv/figures/ 2>/dev/null; done
tar czf arxiv_bundle.tar.gz -C arxiv .
ls -la arxiv_bundle.tar.gz; echo "figures: $(ls arxiv/figures | wc -l)"; grep -c "todo{" arxiv/sections/*.tex | grep -v ":0" || true
