#!/bin/sh
# Build arXiv submission tarballs (tex + bbl + figures), then test-compile each package standalone.
#   sh scripts/make_arxiv.sh [OUT_DIR] [paper dirs...]     (default: OUT_DIR = repo root; papers = paper2 paper3)
# Output: $OUT/paperN_arxiv.tar.gz
set -e
HERE="$(cd "$(dirname "$0")/.." && pwd)"
OUT=${1:-"$HERE"}; [ $# -gt 0 ] && shift
PAPERS="${*:-paper2 paper3}"
for p in $PAPERS; do
  cd "$HERE/$p"
  tectonic --keep-intermediates main.tex > /dev/null 2>&1
  [ -f main.bbl ] || { echo "sem main.bbl em $p"; exit 1; }
  T="$(mktemp -d)"; mkdir "$T/pkg"
  cp main.tex main.bbl "$T/pkg/"; cp -r figures "$T/pkg/figures" 2>/dev/null || true
  (cd "$T/pkg" && tectonic main.tex > /dev/null 2>&1) || { echo "pacote de $p NAO compila isolado"; exit 1; }
  rm -f "$T/pkg/main.pdf" "$T/pkg/main.aux" "$T/pkg/main.log" "$T/pkg/main.out"   # arXiv wants sources only
  tar -czf "$OUT/${p}_arxiv.tar.gz" -C "$T/pkg" .
  echo "$p: pacote ok ($(du -h "$OUT/${p}_arxiv.tar.gz" | cut -f1)) — compila isolado"
  rm -rf "$T"
done
