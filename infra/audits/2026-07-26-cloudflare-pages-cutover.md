# Cloudflare Pages cutover

Completed on 26 July 2026 for `wolvesworldcup.com`.

## Production deployment

- Project: `wolves-world-cup`
- Source commit: `dfef588dc5d7b14c9103ddc18163cbf879f3dc76`
- Deployment: `5441b1bf-94a5-4d7a-946b-0746efb53a0d`
- Archive release: `5e751c619a9ce8b18774c3691b0cd025eb9824535c07ef371b3628d61d44a650`
- Manifest SHA-256: `6fad1c21af804d8734abe7e6f62a3231b39f5d788897f853f98bea9b827224b4`

## Routing

- `wolvesworldcup.com`: proxied CNAME to `wolves-world-cup.pages.dev`
- `www.wolvesworldcup.com`: proxied CNAME to `wolves-world-cup.pages.dev`

The apex redirects to `www` with status `308`, preserving the path and query string. Mail and TXT records were unchanged.

## Verification

- All 189 public `www` routes returned `200`.
- The public manifest matched the verified build byte for byte.
- Private provenance, source exports, retired API routes and unknown routes returned `404`.
- TLS, five MX records and the SPF record were retained.

## Rollback

Set both web CNAME records to DNS-only `291b7b3f19208db1.vercel-dns-016.com` and disable the apex redirect rule.
