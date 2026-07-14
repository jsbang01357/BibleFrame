#!/usr/bin/env bash
set -euo pipefail

PROJECT_ID="${PROJECT_ID:-jisong-cloud-492111}"
REGION="${REGION:-asia-northeast1}"
SERVICE="${SERVICE:-bibleframe}"
JOB="${JOB:-bibleframe-audio}"
BUCKET="${AUDIO_BUCKET:-bibleframe-audio-${PROJECT_ID}}"
REPOSITORY="${REPOSITORY:-bibleframe}"
RUNTIME_SA_NAME="${RUNTIME_SA_NAME:-bibleframe-runtime}"
AUDIO_SA_NAME="${AUDIO_SA_NAME:-bibleframe-audio}"
IMAGE_TAG="${IMAGE_TAG:-$(date -u +%Y%m%d-%H%M%S)}"
IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPOSITORY}/web:${IMAGE_TAG}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ACTION="${1:-all}"

runtime_sa="${RUNTIME_SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"
audio_sa="${AUDIO_SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"

ensure_service_account() {
  local name="$1"
  local label="$2"
  if ! gcloud iam service-accounts describe "${name}@${PROJECT_ID}.iam.gserviceaccount.com" --project "$PROJECT_ID" >/dev/null 2>&1; then
    gcloud iam service-accounts create "$name" --project "$PROJECT_ID" --display-name "$label"
  fi
}

infra() {
  ensure_service_account "$RUNTIME_SA_NAME" "BibleFrame Cloud Run"
  ensure_service_account "$AUDIO_SA_NAME" "BibleFrame Audio Job"

  gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member="serviceAccount:${runtime_sa}" --role="roles/aiplatform.user" --quiet >/dev/null
  gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member="serviceAccount:${runtime_sa}" --role="roles/serviceusage.serviceUsageConsumer" --quiet >/dev/null
  gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member="serviceAccount:${audio_sa}" --role="roles/serviceusage.serviceUsageConsumer" --quiet >/dev/null

  if ! gcloud storage buckets describe "gs://${BUCKET}" --project "$PROJECT_ID" >/dev/null 2>&1; then
    gcloud storage buckets create "gs://${BUCKET}" --project "$PROJECT_ID" \
      --location "$REGION" --uniform-bucket-level-access
  fi
  gcloud storage buckets add-iam-policy-binding "gs://${BUCKET}" \
    --member="serviceAccount:${audio_sa}" --role="roles/storage.objectAdmin" --quiet >/dev/null
  gcloud storage buckets add-iam-policy-binding "gs://${BUCKET}" \
    --member="allUsers" --role="roles/storage.objectViewer" --quiet >/dev/null
  gcloud storage buckets update "gs://${BUCKET}" --cors-file="${ROOT}/deploy/audio-cors.json" --quiet >/dev/null

  if ! gcloud artifacts repositories describe "$REPOSITORY" --project "$PROJECT_ID" --location "$REGION" >/dev/null 2>&1; then
    gcloud artifacts repositories create "$REPOSITORY" --project "$PROJECT_ID" \
      --location "$REGION" --repository-format docker --description "BibleFrame containers"
  fi
}

build() {
  gcloud builds submit "$ROOT" --project "$PROJECT_ID" --region "$REGION" --tag "$IMAGE"
}

deploy_service() {
  gcloud run deploy "$SERVICE" --project "$PROJECT_ID" --region "$REGION" \
    --image "$IMAGE" --service-account "$runtime_sa" --allow-unauthenticated \
    --cpu 1 --memory 1Gi --concurrency 40 --timeout 180s \
    --min 0 --max 5 --min-instances 0 --max-instances 5 \
    --set-env-vars="GOOGLE_CLOUD_PROJECT=${PROJECT_ID},AUDIO_BUCKET=${BUCKET},RAG_GENERATION_ENABLED=true,VERTEX_EMBEDDING_LOCATION=us-central1,VERTEX_EMBEDDING_MODEL=text-multilingual-embedding-002,VERTEX_EMBEDDING_DIMENSIONS=256"
}

deploy_job() {
  gcloud run jobs deploy "$JOB" --project "$PROJECT_ID" --region "$REGION" \
    --image "$IMAGE" --service-account "$audio_sa" --tasks 80 --parallelism 64 \
    --task-timeout 7200s --max-retries 2 --command python \
    --args="^:^scripts/synthesize_chapter_audio.py:--bucket:${BUCKET}:--voices:kore,charon:--speaking-rate:0.9" \
    --set-env-vars="GOOGLE_CLOUD_PROJECT=${PROJECT_ID},AUDIO_BUCKET=${BUCKET},TTS_LOCATION=global,TTS_MAX_ATTEMPTS=5,TTS_RETRY_BASE_SECONDS=1"
}

execute_audio() {
  gcloud run jobs execute "$JOB" --project "$PROJECT_ID" --region "$REGION" --wait
}

case "$ACTION" in
  infra) infra ;;
  build) build ;;
  service) deploy_service ;;
  job) deploy_job ;;
  execute-audio) execute_audio ;;
  all) infra; build; deploy_service; deploy_job ;;
  *) echo "사용법: $0 {infra|build|service|job|execute-audio|all}" >&2; exit 2 ;;
esac

printf 'PROJECT=%s\nREGION=%s\nIMAGE=%s\nBUCKET=gs://%s\n' "$PROJECT_ID" "$REGION" "$IMAGE" "$BUCKET"
