#!/bin/sh
# Local orchestrator: the 4500-tier GEN ladder, sequential pods, one log.
cd "$(dirname "$0")/.." || exit 1
export CM_GPU="NVIDIA RTX PRO 4500 Blackwell"
echo "GEN-ALL START $(date)"
sh scripts/pod_battery.sh 'cd /workspace/creative-machine && sh scripts/run_gen_pod.sh olmo allenai/OLMo-2-1124-13B 20'
sh scripts/pod_battery.sh 'cd /workspace/creative-machine && sh scripts/run_gen_pod.sh qwen14 Qwen/Qwen3-14B-Base 20'
sh scripts/pod_battery.sh 'cd /workspace/creative-machine && sh scripts/run_gen_pod.sh qwen38 Qwen/Qwen3.8-27B 20'
echo "GEN-ALL DONE $(date)"
