# Archive infrastructure runbook

AWS retains the private production source archive and Terraform state. The public site is served by Cloudflare Pages.

## Apply

```sh
terraform -chdir=infra/envs/prod init
terraform -chdir=infra/envs/prod plan
terraform -chdir=infra/envs/prod apply
```

Terraform references `wolves-superforecaster-prod` without owning the bucket. It manages only the lifecycle rule that aborts incomplete multipart uploads. Existing objects and object versions have no automatic expiry.

## Recovery

The retired ECS runtime, schedules, roles and secret containers can be reconstructed from repository history. Restore the retirement commit's parent, review current service versions and recreate secret values before applying.
