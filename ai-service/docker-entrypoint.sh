#!/bin/sh
# Container entrypoint: seed the Chroma ONNX embedding cache from a locally
# mounted model directory, then start the service.
#
# Chroma (>=1.x) only considers the model "present" when ALL of the files below
# exist inside <cache>/all-MiniLM-L6-v2/onnx/. Seeding only model.onnx is not
# enough — Chroma would silently fall back to downloading a 79 MB archive, and
# the background ingest task plus the uvicorn worker would race on the same
# file, leaving a corrupt truncated archive behind.
set -e

MODEL_SRC="/models/minilm"
CACHE_ROOT="/root/.cache/chroma/onnx_models"
MODEL_CACHE_DIR="${CACHE_ROOT}/all-MiniLM-L6-v2/onnx"

REQUIRED_FILES="config.json model.onnx special_tokens_map.json tokenizer_config.json tokenizer.json vocab.txt"

model_complete() {
  for f in $REQUIRED_FILES; do
    [ -f "${MODEL_CACHE_DIR}/${f}" ] || return 1
  done
  return 0
}

if model_complete; then
  echo "[entrypoint] ONNX model cache already complete, skipping seed"
else
  echo "[entrypoint] seeding ONNX model cache from ${MODEL_SRC}"
  mkdir -p "$MODEL_CACHE_DIR"

  if [ ! -f "${MODEL_SRC}/onnx/model.onnx" ]; then
    echo "[entrypoint] WARNING: ${MODEL_SRC}/onnx/model.onnx not found." >&2
    echo "[entrypoint] Mount the model directory at /models/minilm or Chroma will download it at runtime (slow)." >&2
  else
    cp "${MODEL_SRC}/onnx/model.onnx" "${MODEL_CACHE_DIR}/model.onnx"
    for f in config.json special_tokens_map.json tokenizer_config.json tokenizer.json vocab.txt; do
      if [ -f "${MODEL_SRC}/${f}" ]; then
        cp "${MODEL_SRC}/${f}" "${MODEL_CACHE_DIR}/${f}"
      elif [ -f "${MODEL_SRC}/onnx/${f}" ]; then
        cp "${MODEL_SRC}/onnx/${f}" "${MODEL_CACHE_DIR}/${f}"
      else
        echo "[entrypoint] WARNING: ${f} missing in ${MODEL_SRC}" >&2
      fi
    done
  fi

  if model_complete; then
    # Drop any partial archive left behind by an interrupted download.
    rm -f "${CACHE_ROOT}/all-MiniLM-L6-v2/onnx.tar.gz"
    echo "[entrypoint] model cache ready"
  else
    echo "[entrypoint] WARNING: model cache incomplete, Chroma will try to download it" >&2
  fi
fi

exec "$@"
