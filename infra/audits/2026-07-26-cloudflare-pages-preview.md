# Cloudflare Pages preview

Deployed on 26 July 2026 without changing public DNS.

## Deployment

- Account: `00977673ef6db2c0c8128748192d00d2`
- Project: `wolves-world-cup`
- Environment: preview
- Branch: `cloudflare-preview`
- Source commit: `dfef588dc5d7b14c9103ddc18163cbf879f3dc76`
- Deployment: `7c22e87f-e787-4c98-a715-59c5d93b4af0`
- Preview: `https://cloudflare-preview.wolves-world-cup.pages.dev`
- Immutable archive release: `5e751c619a9ce8b18774c3691b0cd025eb9824535c07ef371b3628d61d44a650`

The release contained 74 verified objects, 38 archive days and 33 current agent forecasts. The static build generated 194 routes and uploaded 1,951 public files. Private provenance and source exports were excluded.

## Verification

- All 189 public page routes returned `200`.
- The deployed manifest matched the verified build byte for byte.
- Representative day and run payloads matched their manifest SHA-256 digests.
- Hashed assets and payloads returned immutable one-year cache headers.
- The manifest returned a five-minute revalidation policy.
- Security headers matched `web/public/_headers`.
- Unknown routes, retired API routes, provenance and private sources returned `404`.

## Cutover and rollback

No Pages custom domain is attached. The current public site remains on Vercel:

- `wolvesworldcup.com`: `A 216.150.1.129`, `A 216.150.16.129`
- `www.wolvesworldcup.com`: `CNAME 291b7b3f19208db1.vercel-dns-016.com`

Before cutover, deploy the verified build to the Pages production branch and confirm it matches this preview. Attach the apex and `www` domains only with explicit operator approval. Preserve the DNS values above for immediate rollback and retain the Vercel deployment until the observation period ends.
