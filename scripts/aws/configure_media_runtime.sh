#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

if [[ "$#" -ne 2 ]]; then
  echo 'Usage: configure_media_runtime.sh MEDIA_BUCKET AWS_REGION' >&2
  exit 2
fi

media_bucket="$1"
aws_region="$2"
runtime_env='/opt/tradeflow/runtime.env'
old_container='tradeflow-web-before-s3-media'

if [[ ! "$media_bucket" =~ ^[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]$ ]]; then
  echo 'Invalid S3 media bucket name.' >&2
  exit 2
fi
if [[ ! "$aws_region" =~ ^[a-z]{2}(-gov)?-[a-z]+-[0-9]+$ ]]; then
  echo 'Invalid AWS region.' >&2
  exit 2
fi
if [[ ! -f "$runtime_env" ]]; then
  echo "Missing $runtime_env; run tradeflow-deploy.sh first." >&2
  exit 1
fi

image_uri="$(docker inspect --format '{{.Config.Image}}' tradeflow-web)"
if [[ -z "$image_uri" ]]; then
  echo 'Could not determine the current TradeFlow image.' >&2
  exit 1
fi

# Preserve media already written to the EC2 volume (including the staging
# upload that exposed this bug). This is additive: it never deletes S3 data.
if [[ -d /opt/tradeflow/media ]]; then
  aws s3 sync /opt/tradeflow/media "s3://${media_bucket}/" \
    --region "$aws_region" \
    --only-show-errors
fi

cp --preserve=mode,ownership "$runtime_env" "${runtime_env}.before-s3-media"
python3 - "$runtime_env" "$media_bucket" "$aws_region" <<'PY'
import os
import sys
from pathlib import Path

path = Path(sys.argv[1])
bucket = sys.argv[2]
region = sys.argv[3]
managed = {
    'AWS_MEDIA_BUCKET_NAME',
    'AWS_MEDIA_REGION_NAME',
    'AWS_MEDIA_URL_EXPIRY',
    'SERVE_LOCAL_MEDIA',
}
lines = [
    line for line in path.read_text(encoding='utf-8').splitlines()
    if line.partition('=')[0].strip() not in managed
]
lines.extend([
    f'AWS_MEDIA_BUCKET_NAME={bucket}',
    f'AWS_MEDIA_REGION_NAME={region}',
    'AWS_MEDIA_URL_EXPIRY=3600',
    'SERVE_LOCAL_MEDIA=false',
])
tmp = path.with_suffix('.env.tmp')
tmp.write_text('\n'.join(lines) + '\n', encoding='utf-8')
os.chmod(tmp, 0o600)
os.replace(tmp, path)
PY

original_renamed=false
rollback() {
  status="$?"
  trap - ERR
  echo 'S3 media validation failed; restoring the previous container.' >&2
  if [[ "$original_renamed" == true ]]; then
    docker rm --force tradeflow-web >/dev/null 2>&1 || true
    if docker inspect "$old_container" >/dev/null 2>&1; then
      if docker rename "$old_container" tradeflow-web; then
        docker start tradeflow-web >/dev/null 2>&1 || true
      fi
    fi
  fi
  if [[ -f "${runtime_env}.before-s3-media" ]]; then
    mv -f "${runtime_env}.before-s3-media" "$runtime_env"
  fi
  exit "$status"
}
trap rollback ERR

docker rm --force "$old_container" >/dev/null 2>&1 || true
docker rename tradeflow-web "$old_container"
original_renamed=true
docker stop "$old_container" >/dev/null

docker run --detach \
  --name tradeflow-web \
  --restart unless-stopped \
  --env-file "$runtime_env" \
  --publish 127.0.0.1:8080:8080 \
  --volume /opt/tradeflow/media:/app/media \
  "$image_uri" >/dev/null

for attempt in {1..30}; do
  if curl --fail --silent --header 'Host: tradeflowcolon.com' \
    http://127.0.0.1:8080/health/live/ >/dev/null; then
    break
  fi
  if [[ "$attempt" -eq 30 ]]; then
    docker logs --tail 100 tradeflow-web
    false
  fi
  sleep 2
done

docker exec tradeflow-web \
  python manage.py check_media_storage --require-remote --write-test

docker rm --force "$old_container" >/dev/null
rm -f "${runtime_env}.before-s3-media"
trap - ERR
echo 'AWS S3 media runtime enabled and verified.'
