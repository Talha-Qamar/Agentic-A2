set -e
pip install -q fastembed==0.* wordllama openai
python - <<'PY'
import os, time, json
from fastembed import TextEmbedding
from fastembed.rerank.cross_encoder import TextCrossEncoder
t=time.time(); m=TextEmbedding("BAAI/bge-small-en-v1.5"); v=list(m.embed(["hello world"]))[0]; print("bge", len(v), time.time()-t)
t=time.time(); r=TextCrossEncoder("Xenova/ms-marco-MiniLM-L-6-v2"); print("rerank", list(r.rerank("celery queue", ["background worker queue","react ui"])), time.time()-t)
from wordllama import WordLlama
wl=WordLlama.load(); print("wordllama", wl.embed(["x"]).shape)
from openai import OpenAI
c=OpenAI(base_url="https://api.groq.com/openai/v1", api_key=os.environ["GROQ_API_KEY"])
t=time.time(); r=c.chat.completions.create(model="openai/gpt-oss-20b", messages=[{"role":"user","content":"Reply with the word OK"}], max_tokens=20, reasoning_effort="low")
print("groq", r.choices[0].message.content, r.usage, time.time()-t)
PY
mkdir -p ci/out/models
tar -C $HOME/.cache -czf /tmp/models.tgz fastembed
python - <<'PY'
import os, glob, shutil
from pathlib import Path
src = Path.home()/".cache"
for p in src.glob("**/wordllama*"): print(p)
PY
WL=$(python -c "import wordllama,os;print(os.path.dirname(wordllama.__file__))")
tar -czf /tmp/wl.tgz -C $HOME/.cache wordllama 2>/dev/null || true
ls -la /tmp/*.tgz
split -b 80m /tmp/models.tgz ci/out/models/fastembed.tgz.part-
[ -s /tmp/wl.tgz ] && cp /tmp/wl.tgz ci/out/models/wordllama.tgz || true
ls -la ci/out/models
