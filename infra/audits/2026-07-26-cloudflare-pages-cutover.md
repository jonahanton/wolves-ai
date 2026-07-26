# Cloudflare Pages cutover

Completed on 26 July 2026 for `wolvesworldcup.com`.

## Production deployment

- Project: `wolves-world-cup`
- Production branch: `main`
- Source commit: `dfef588dc5d7b14c9103ddc18163cbf879f3dc76`
- Deployment: `5441b1bf-94a5-4d7a-946b-0746efb53a0d`
- Archive release: `5e751c619a9ce8b18774c3691b0cd025eb9824535c07ef371b3628d61d44a650`

Cloudflare reused all 1,951 files from the verified preview upload. The Pages production URL and the public `www` domain returned the same archive manifest SHA-256:

`6fad1c21af804d8734abe7e6f62a3231b39f5d788897f853f98bea9b827224b4`

## Routing

The two DNS-only Vercel CNAMEs were replaced in place. Mail and TXT records were not changed.

- `wolvesworldcup.com`: proxied CNAME to `wolves-world-cup.pages.dev`
- `www.wolvesworldcup.com`: proxied CNAME to `wolves-world-cup.pages.dev`

The zone-level redirect ruleset `33f2007e8270450b9ae7e6bb13489e17` preserves the canonical host. Rule `9016fac5acd241ad838906579743e26c` redirects the apex to `www` with status `308`, preserving the path and query string.

The `www` Pages custom domain is active. The apex Pages association remains pending because the edge redirect handles apex requests before Pages validation. DNS verification is active and public apex routing is healthy.

## Verification

- All 189 public `www` routes returned `200`.
- Three representative apex routes returned `308` with exact path and query preservation.
- The public manifest matched the verified build byte for byte.
- Private provenance, source exports, retired API routes and unknown routes returned `404`.
- Security and cache headers matched the verified preview.
- TLS was valid for the apex and `www.wolvesworldcup.com`.
- Five MX records and the SPF record were retained.

The first proxied `www` request returned `522` while Pages completed CNAME verification. Verification became active and the site returned `200` within one minute.

## Rollback

Restore both web CNAME records to:

`291b7b3f19208db1.vercel-dns-016.com`

Set them to DNS-only and disable the apex redirect rule. The retained Vercel deployment then resumes the previous apex-to-`www` behaviour.
