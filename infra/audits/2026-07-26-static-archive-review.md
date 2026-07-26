# Static archive integrity review

Completed on 26 July 2026 against `wolves-superforecaster-prod`.

## Finding

The first release treated older S3 object versions as current when a delete marker was latest. It therefore included two retired forecasts:

- `agent-20260626-141147`
- `agent-20260714-063120`

No source data was lost. Both runs remain privately recoverable through S3 version history, but neither belongs in the public archive.

## Correction

- Read only current S3 versions and exclude keys whose latest version is a delete marker.
- Preserve the DynamoDB run-index export privately with content-addressed provenance.
- Verify canonical cutoffs, complete ordered forecast history and every release file digest.
- Exclude private provenance and source exports from the static web output.

The corrected archive contains 38 days and 33 current agent forecasts. The 26 and 27 June views select `agent-20260625-115913`.

Corrected append-only release:

`s3://wolves-superforecaster-prod/static-archive/releases/5e751c619a9ce8b18774c3691b0cd025eb9824535c07ef371b3628d61d44a650`

The release contains 74 objects. Its identifier covers every file path and digest, and the publisher uploaded the manifest after the payloads. No S3 object was deleted or overwritten.

The superseded release remains intact for audit:

`s3://wolves-superforecaster-prod/static-archive/releases/f25fad16db1339aa961373deb87a7582cd21af9a65d1b1787c1ab870b4a8304e`
