#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "usage: $0 OUTPUT_DIR" >&2
  exit 2
fi

repo_root=$(git rev-parse --show-toplevel)
pilot_dir="$repo_root/benchmarks/human_gold_v0_1/pilot"
output_dir="$1"
mkdir -p "$output_dir"
cd "$repo_root"

python -m tools.human_gold.openalex_candidates \
  --snapshot "$pilot_dir/openalex_snapshot.json" \
  --transform-config "$pilot_dir/candidate_transform.json" \
  --rejections "$pilot_dir/objective_rejections.jsonl" \
  --candidates-output "$output_dir/candidates.jsonl" \
  --eligible-output "$output_dir/eligible_candidates.jsonl"

cmp "$pilot_dir/candidates.jsonl" "$output_dir/candidates.jsonl"
cmp "$pilot_dir/eligible_candidates.jsonl" "$output_dir/eligible_candidates.jsonl"

python -m tools.human_gold.sample_sources \
  --candidates "$output_dir/eligible_candidates.jsonl" \
  --exclusions "$pilot_dir/exclusion_registry.jsonl" \
  --config "$pilot_dir/selection_config.json" \
  --output "$output_dir/selected.jsonl"

cmp "$pilot_dir/selected.jsonl" "$output_dir/selected.jsonl"
echo "pilot selection replay: PASS"
