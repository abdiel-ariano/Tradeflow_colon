# Supabase Storage — product images

## Problem (fixed)

`django-storages` `S3Boto3Storage` was configured with Supabase's S3-compatible endpoint and
`access_key='service_role'`. Browser URLs looked like:

```
https://<project>.supabase.co/storage/v1/s3/media/...?AWSAccessKeyId=service_role&Signature=...
```

Those signatures are invalid because `service_role` is the Supabase JWT API key, not an AWS
Access Key ID.

## Solution

`core.storage.supabase_media.SupabaseMediaStorage` still uploads via the S3-compatible API
(server-side), but **`url()`** returns native Supabase Storage URLs:

| Mode | URL pattern |
|------|-------------|
| Public bucket (default) | `{SUPABASE_URL}/storage/v1/object/public/{bucket}/{path}` |
| Private bucket | `create_signed_url()` via `supabase-py` (native token, not S3) |

### Environment

```env
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_KEY=eyJ...
SUPABASE_STORAGE_BUCKET=media
SUPABASE_STORAGE_PUBLIC=true
```

Set `SUPABASE_STORAGE_PUBLIC=false` only if the bucket must stay private; signed URLs expire
after `SUPABASE_SIGNED_URL_TTL` seconds (default 3600).

## Bucket policies (Supabase Dashboard)

**Storage → Policies → bucket `media`**

For a **public** product catalog (recommended):

```sql
-- Allow public read on all objects in media bucket
CREATE POLICY "Public read media"
ON storage.objects FOR SELECT
TO public
USING (bucket_id = 'media');
```

Ensure the bucket is marked **Public** in Storage settings, or objects use `public-read` ACL
on upload (already set in `settings.py`).

For **private** buckets, keep RLS restrictive and use `SUPABASE_STORAGE_PUBLIC=false`.

## Placeholder paths in database

Management commands (`generate_placeholders`, `regenerate_product_images`) may set:

```
productos/placeholders/placeholder_{id}_{initials}.png
```

If these paths exist in Postgres but files were never uploaded to Supabase, images 404 until
you either:

1. Run `python manage.py regenerate_product_images --storage remote` (uploads to bucket), or
2. Reset orphan paths: audit with `python manage.py verify_media --audit-placeholders`

The frontend falls back to `/static/images/placeholder-producto.svg` when the URL is empty or
`onerror` fires.

## Verify after deploy

```bash
python manage.py verify_media --audit-placeholders
```

URLs must contain `/storage/v1/object/public/` (public) or `/storage/v1/object/sign/` (signed),
never `/storage/v1/s3/`.
