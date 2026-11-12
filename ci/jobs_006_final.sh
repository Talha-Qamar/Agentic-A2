# Final job: demo video on the live site first (fresh quota), then every remaining experiment in rounds.
# Runners cache finished rows; a round that hits Groq's daily cap stops cleanly and the next round resumes.
set -x
git fetch origin main && git reset --hard origin/main
git log --oneline -1
pip install -q -r requirements-eval.txt
set +x
[ -f ~/.gigbid_reviewer.env ] && set -a && . ~/.gigbid_reviewer.env && set +a
set -x
OUT=runs/out/006_final; mkdir -p $OUT/results
export EMBED_THREADS=6 GIGBID_PROFILE=open
export GIGBID_FIT_BID=$(python -c "import json;print(json.load(open('evals/results/fit_calibration.json'))['summary']['fit_bid'])")
export GIGBID_FIT_WATCH=$(python -c "import json;print(round(0.6*json.load(open('evals/results/fit_calibration.json'))['summary']['fit_bid'],4))")

# 1. demo video against the live deployment (narration with macOS `say`)
python -m playwright install chromium >/dev/null 2>&1
if [ ! -f $OUT/gigbid_demo.mp4 ]; then
  timeout 3000 python scripts/demo_video.py --url https://gigbid-d3l2.onrender.com --out $OUT/gigbid_demo.mp4 > $OUT/demo.log 2>&1
  tail -5 $OUT/demo.log
fi

# 2. no-LLM analysis
[ -f evals/results/rerank_analysis.json ] || python -m evals.runners.rerank_analysis --limit 40 > $OUT/rerank.log 2>&1
cp evals/results/rerank_analysis.json $OUT/results/ 2>/dev/null

# 3. experiments, fresh caches once
if [ ! -f var/.fresh_006 ]; then rm -rf var/eval_cache var/cmp_gigsim.db* var/inj_gigsim.db*; mkdir -p var; touch var/.fresh_006; fi
[ -f ~/.gigbid_hidden_seed ] || python -c "import secrets;print(secrets.token_hex(8))" > ~/.gigbid_hidden_seed
complete() { python - "$@" <<'PY'
import json,sys,os
ok=all(os.path.exists(f"evals/results/{f}") and json.load(open(f"evals/results/{f}")).get("complete", True) for f in sys.argv[1:])
sys.exit(0 if ok else 1)
PY
}
for round in $(seq 1 60); do
  echo "=== round $round $(date)"
  if ! complete tool_granularity.json; then
    ( python -m evals.runners.tool_granularity --tasks 40 --provider groq --model qwen/qwen3.8-27b > $OUT/tool_study_r$round.log 2>&1 ) &
    TS=$!
  else TS=""; fi
  complete multiagent_comparison.json || python -m evals.runners.multiagent_comparison --limit 2
  complete injection_eval.json || python -m evals.runners.injection_eval --limit 6
  complete rag_e2e_v0.json || GIGBID_RAG_VARIANT=v0_naive python -m evals.runners.multiagent_comparison --limit 2 --systems gigbid_graph --tag v0 --out rag_e2e_v0.json
  if ! complete change_request_before.json change_request_after.json; then
    ( export GIGSIM_POLICY_VERSION=2026-11-02 GIGBID_FIT_BID=0 GIGBID_FIT_WATCH=0
      git show 70c8062:data/policy_pack/rules.yaml > data/policy_pack/rules.yaml
      python -m evals.runners.decision_eval --limit 2 --concurrency 2 --out change_request_before.json
      git checkout -q -- data/policy_pack/rules.yaml
      python -m evals.runners.decision_eval --limit 2 --concurrency 2 --out change_request_after.json )
  fi
  complete hidden_test_results.json || HIDDEN_TEST_SEED=$(cat ~/.gigbid_hidden_seed) python -m evals.runners.hidden_test --per-persona 3
  [ -n "$TS" ] && wait $TS
  python -m evals.runners.human_eval build > $OUT/human_eval_build.log 2>&1 || true
  cp evals/results/*.json evals/results/*.csv $OUT/results/ 2>/dev/null
  cp var/human_eval/* $OUT/results/ 2>/dev/null
  if complete tool_granularity.json multiagent_comparison.json injection_eval.json rag_e2e_v0.json change_request_before.json change_request_after.json hidden_test_results.json; then
    echo ALL_DONE; break
  fi
  echo "quota reached; sleeping 40 min"; sleep 2400
done
