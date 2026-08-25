#!/bin/sh
# Painel de status do laboratório — leitura apenas. Rode de qualquer checkout:
#   sh scripts/status.sh
# Os dados vivem no worktree da sessão; se runs/ local não os tiver, usamos o worktree.
R="$(cd "$(dirname "$0")/.." && pwd)/runs"
WT="/Users/robertoonofilho/wrk/repo/creative-machine/.claude/worktrees/plano-continuacao-08e0cf/runs"
[ -f "$R/frontier/F_23_chain.log" ] || R="$WT"
echo "=== creative-machine status — $(date '+%d/%m %H:%M') ==="
echo "--- processos de modelo ativos:"
ps aux | grep -E "[f]rontier_search|[c]onsolidate.py gen|[m]lx_lm lora|[d]po_lora" | awk '{printf "  pid %s  %s%%cpu  %s\n", $2, $3, $NF}' | head -4
[ -z "$(ps aux | grep -E '[f]rontier_search|[c]onsolidate.py gen|[m]lx_lm lora')" ] && echo "  (nenhum — esteira ociosa)"
echo "--- cadeia atual (última linha de cada log de cadeia):"
for f in "$R"/frontier/F_23_chain.log "$R"/frontier/F_ext2_chain.log "$R"/frontier/record_chain.log; do
  [ -f "$f" ] && printf "  %-18s %s\n" "$(basename "$f" .log):" "$(tail -1 "$f")"
done
if [ -d "$R/frontier/F" ]; then
  done23=$(grep -l "DONE best" "$R"/frontier/F/*_B[CD]*.log "$R"/frontier/F/*_CD*.log 2>/dev/null | wc -l | tr -d ' ')
  echo "--- 2^3: $done23 de 54 corridas concluídas"
fi
echo "--- últimos 3 'new best' (qualquer corrida):"
ls -t "$R"/frontier/F/*.log "$R"/frontier/record/*.log 2>/dev/null | head -3 | while read f; do
  nb=$(grep "new best" "$f" | tail -1); [ -n "$nb" ] && printf "  %-24s %s\n" "$(basename "$f" .log):" "$nb"
done
echo "--- térmico: $(pmset -g therm | head -1 | sed 's/Note: //')"
echo "--- análise agregada mais recente: docs/APPENDIX_F.md (recalculada a cada corrida)"
