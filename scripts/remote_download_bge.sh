#!/bin/bash
set -euo pipefail
export HF_ENDPOINT=https://hf-mirror.com
export HF_HUB_ENDPOINT=https://hf-mirror.com
python -c "
from sentence_transformers import SentenceTransformer
m = SentenceTransformer('BAAI/bge-large-zh-v1.5')
print('model_ok', m.get_sentence_embedding_dimension())
"
