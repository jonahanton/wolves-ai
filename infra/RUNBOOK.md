# Prod runbook

First apply, release, and day-two operations for `infra/envs/prod`. All commands assume `AWS_REGION=eu-west-2` and admin credentials.

## First apply

### 1. Bootstrap the state backend (once per account)

Skip if the `wolves-terraform-state` bucket already exists.

```sh
terraform -chdir=infra/bootstrap init
terraform -chdir=infra/bootstrap apply
```

Bootstrap state stays on local disk by design.

### 2. Import a pre-existing GitHub OIDC provider

An account can hold only one provider for `token.actions.githubusercontent.com`. Check first:

```sh
aws iam list-open-id-connect-providers
```

If one exists, import it before applying:

```sh
terraform -chdir=infra/envs/prod init
terraform -chdir=infra/envs/prod import \
  module.release_oidc.aws_iam_openid_connect_provider.github \
  arn:aws:iam::<ACCOUNT_ID>:oidc-provider/token.actions.githubusercontent.com
```

### 3. Apply

```sh
terraform -chdir=infra/envs/prod init
terraform -chdir=infra/envs/prod apply
```

Defaults are safe for an empty account: both schedules are created DISABLED and `backend_desired_count` is 0, so nothing tries to pull from the still-empty ECR repositories or read versionless secrets.

### 4. Confirm the SNS subscription

The apply subscribes `alert_email` (from `terraform.tfvars`) to the `wolves-alerts` topic. Click the confirmation link in the email before relying on alerts.

### 5. Put secret values

Terraform creates the secret containers only; values never go through terraform or its state.

```sh
aws secretsmanager put-secret-value --secret-id wolves-engine-anthropic-api-key --secret-string '<value>'
aws secretsmanager put-secret-value --secret-id wolves-engine-api-football-key  --secret-string '<value>'
aws secretsmanager put-secret-value --secret-id wolves-engine-odds-api-key      --secret-string '<value>'
aws secretsmanager put-secret-value --secret-id wolves-backend-admin-token      --secret-string '<value>'
```

### 6. Set GitHub secrets and variables

From `terraform -chdir=infra/envs/prod output`:

| GitHub setting | Type | Source |
| --- | --- | --- |
| `AWS_RELEASE_ROLE_ARN` | secret | output `github_release_role_arn` |
| `AWS_OPS_ROLE_ARN` | secret | output `github_ops_role_arn` |
| `ADMIN_TOKEN` | secret | the value put into `wolves-backend-admin-token` |
| `BACKEND_URL` | secret | set in step 8 once the backend has an IP |
| `ECS_SUBNETS` | variable | output `ecs_subnets` |
| `ECS_SECURITY_GROUP` | variable | output `ecs_security_group` |

### 7. First release

Tag and push:

```sh
git tag prod-<version> && git push origin prod-<version>
```

`release.yml` builds and pushes the engine and backend images and registers fresh `wolves-engine-daily` and `wolves-engine-agent` task definition revisions. The backend service roll step is harmless at desired count 0.

### 8. Start the backend and set BACKEND_URL

```sh
terraform -chdir=infra/envs/prod apply -var backend_desired_count=1
```

Read the task's public IP:

```sh
task=$(aws ecs list-tasks --cluster wolves --service-name wolves-backend --query 'taskArns[0]' --output text)
eni=$(aws ecs describe-tasks --cluster wolves --tasks "$task" \
  --query "tasks[0].attachments[0].details[?name=='networkInterfaceId'].value" --output text)
aws ec2 describe-network-interfaces --network-interface-ids "$eni" \
  --query 'NetworkInterfaces[0].Association.PublicIp' --output text
```

Set the GitHub secret `BACKEND_URL` to `http://<ip>:8080`. Known limitation: this IP rots on every backend redeploy until a stable HTTPS endpoint exists (tracked separately); refresh the secret after each roll.

### 9. Smoke checks

1. `admin-control.yml` with action `active-runs` returns an empty list.
2. `run-engine.yml` with mode `daily`; watch `/ecs/wolves-engine` in CloudWatch Logs.
3. Confirm a snapshot lands in `s3://wolves-superforecaster-prod/snapshots/`.
4. Deliberately break a run (for example dispatch with a bad ceiling or stop the task) and confirm the failure alert email arrives.

### 10. Enable the schedules

Set `schedule_state` to `ENABLED` for the daily run. For an agent run, add future bounds and set `state = "ENABLED"` on only the required `agent_schedule_windows` entry. Then apply Terraform.

The live loop and odds archive run inside the backend process and need no schedule; they start with the service.

## Run schedules and policy

EventBridge schedules launch engine tasks and Terraform owns their state:

| Schedule | Task | Configuration |
| --- | --- | --- |
| `wolves-daily-run` | deterministic daily run | `schedule_cron` |
| `wolves-agent-<window>` | agent run (ceiling derived from the calendar policy) | One retained `agent_schedule_windows` entry, disabled unless explicitly bounded and enabled |

The live loop and the odds archive are not scheduled tasks: they run as asyncio loops inside the backend service (`wolves_backend/jobs.py`), polling on the engine's cadence settings and capturing at the archive's UTC hours (`ARCHIVE_HOURS_UTC`). A failing pass publishes to `wolves-alerts` directly, rate-limited to one alert per job per hour. Because of those loops the backend must stay a single writer: `desired_count` above 1 is refused by the module. 0 still parks the service, which also parks live polling and archiving.

The live state flags `schedule_drift` (and the live pass logs a warning) whenever the provider's kickoff times diverge from `data/format/schedule.json`; correct the schedule files when it fires.

The `run_policy` variable in `infra/envs/prod/variables.tf` is the spend-policy configuration surface: agent ceilings and live polling cadence, rendered into every engine task's environment. To see the calendar the engine derives from it, run from a directory with `.env`:

```sh
uv run --project engine python -m wolves.run_policy
```

The agent schedules ship disabled. Enable only one bounded window through Terraform as described in step 10.

## Kill-switch reset

At 100 percent of the monthly budget, the budget action attaches `wolves-deny-run-task` to three roles, which stops all new engine tasks. To reset after investigating:

```sh
for role in wolves-scheduler wolves-backend-task wolves-github-ops; do
  aws iam detach-role-policy --role-name "$role" \
    --policy-arn arn:aws:iam::<ACCOUNT_ID>:policy/wolves-deny-run-task
done
```

Then `admin-control.yml` action `stop-all` to clear anything still running, and re-enable the schedules as in step 10.

## Operational notes

- Manually stopping an engine task triggers the failure alert email. Expected: the EventBridge rule matches any non-zero exit or failed start and cannot distinguish operator stops.
- Secrets Manager blocks recreating a deleted secret name during the recovery window. On teardown, delete with `--force-delete-without-recovery` if the stack will be re-applied soon.
- `run-engine.yml` refuses to dispatch while any `wolves-engine-daily` task is RUNNING or PENDING; pass `force=true` to override deliberately.
- The backend serves engine sims in-process. After a deploy it boots from `models/fitted/latest.json` (falling back to a fresh fit from the dataset); engine routes return 503 until that completes, while `/healthz` and the artifact routes serve immediately.

## Consolidation rollout (one-off)

The backend-engine consolidation lands in two terraform points on the same branch; the deletions must not be applied until the consolidated backend has burned in.

1. Apply at the additive commit ("Size the backend for the engine: ..."): `git checkout <that commit> && terraform -chdir=infra/envs/prod apply && git checkout main`. This grows the backend task (1 vCPU/2GB), grants it the live-data secrets, S3 writes and `sns:Publish`, and leaves every old schedule and task definition in place.
2. Release the consolidated images (tag `prod-<version>`), confirm the backend boots and `/live` updates.
3. Disable the `wolves-live-window` schedule (`update-schedule --state DISABLED`) so the ECS live task and the in-process loop do not double-poll. The odds archive schedule may stay enabled during burn-in: duplicate captures land on second-granularity keys and are harmless.
4. Watch a full match day: live state cadence, a post-FT publish, archive captures at 08/14/18/22 UTC, and the daily run (still on ECS, untouched).
5. Apply HEAD to delete the `live_window` and `odds_archive` schedules, the `wolves-engine-live` and `wolves-engine-archive` task definitions, and to narrow the ECS failure alert to the daily and agent families.

Rollback before step 5 is a redeploy of the previous backend image plus re-enabling a schedule. After step 5, re-creating the deleted resources means re-applying the additive commit.
