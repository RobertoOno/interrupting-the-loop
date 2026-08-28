#!/bin/sh
# Build arXiv submission tarballs for papers 2 and 3 (tex + bbl + figures),
# then test-compile each package standalone. Output: $OUT/paperN_arxiv.tar.gz
set -e
HERE="$(cd "$(dirname "$0")/.." && pwd)"
OUT=${1:-"$HERE"}
for p in paper2 paper3; do
  cd "$HERE/$p"
  tectonic --keep-intermediates main.tex > /dev/null 2>&1
  [ -f main.bbl ] || { echo "sem main.bbl em $p"; exit 1; }
  T="$(mktemp -d)"; mkdir "$T/pkg"
  cp main.tex main.bbl "$T/pkg/"; cp -r figures "$T/pkg/figures" 2>/dev/null || true
  (cd "$T/pkg" && tectonic main.tex > /dev/null 2>&1) || { echo "pacote de $p NAO compila isolado"; exit 1; }
  tar -czf "$OUT/${p}_arxiv.tar.gz" -C "$T/pkg" .
  echo "$p: pacote ok ($(du -h "$OUT/${p}_arxiv.tar.gz" | cut -f1)) — compila isolado"
  rm -rf "$T"
done
