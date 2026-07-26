# AWS runtime retirement

Completed on 26 July 2026 after the Cloudflare Pages cutover was verified.

## Preserved state

The retirement evidence bundle contains the DynamoDB records, ECR image digests, ECS service metadata, schedules, secret metadata, July costs and pre-retirement Terraform state. It contains no secret values.

- S3 key: `static-archive/operations/retirements/b3485b8520282d9ce2a8b0a4f088b46cdabb65053a03df32ec8f3a5088b38021.tar.gz`
- SHA-256: `b3485b8520282d9ce2a8b0a4f088b46cdabb65053a03df32ec8f3a5088b38021`
- Version ID: `RKZY.2kMI5cDteoKAjcZ0APUcC2RwVhQ`
- Size: 33,433 bytes

The verified archive release remains:

`static-archive/releases/5e751c619a9ce8b18774c3691b0cd025eb9824535c07ef371b3628d61d44a650`

## Changes

Terraform applied a reviewed plan with 53 destroys, one in-place lifecycle update and no creates.

Retired:

- the ECS cluster, backend service and all active task definitions;
- backend and engine ECR repositories and images;
- five disabled EventBridge Scheduler schedules;
- the `wolves-forecaster` DynamoDB table after export;
- backend and engine log groups and security groups;
- runtime IAM roles, policies, GitHub OIDC roles and their otherwise-unused account provider;
- runtime alerts, SNS topic and budget action;
- nine Secrets Manager secrets with a 30-day recovery window.

The production S3 lifecycle now aborts incomplete multipart uploads after seven days and expires nothing. The production archive bucket, development bucket and Terraform state bucket were not deleted or emptied.

The unused Lightsail static IP `jonah-agent-ip` (`3.11.48.247`) was released successfully in operation `c9ea9022-a25d-4a35-95a2-a4756b773805`.

The retired GitHub release and run-control workflows were removed. Their scripts remain under `scripts/archived/`. Their four repository secrets and two repository variables were deleted after the AWS roles and security group ceased to exist.

## Verification

- A post-apply Terraform plan reported no changes.
- Terraform state contains only the production archive bucket data source and lifecycle resource.
- No Wolves ECS cluster, active task definition, ECR repository, schedule, DynamoDB table, log group, IAM role, local IAM policy, OIDC provider or Lightsail static IP remains.
- All nine Secrets Manager deletions requested a 30-day recovery window.
- The retirement evidence object and verified archive release remain readable from the private production bucket.
- `api.wolvesworldcup.com` no longer resolves and the Cloudflare tunnel is deleted.
- The apex redirect, `www` site, five MX records and SPF TXT record remain healthy.

## Cost

The account had accrued approximately USD 80 including tax during July, primarily from Fargate before the freeze. The confirmed USD 3.60 monthly Lightsail charge, approximately USD 3.60 monthly Secrets Manager charge and approximately USD 0.35 monthly ECR charge are retired.

The remaining Wolves AWS run rate is approximately USD 0.10 per month before tax for about 3.62 GB across the production archive, development and Terraform state buckets. Cloudflare Pages and the domain zone are on free plans.
