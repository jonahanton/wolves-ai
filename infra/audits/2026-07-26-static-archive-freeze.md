# Static archive runtime freeze

Executed at 2026-07-26T18:57:22Z in AWS account `815812379706`, region `eu-west-2`.

## Scope

- Disable the five `wolves-*` EventBridge Scheduler schedules.
- Set the `wolves-backend` ECS service desired count to zero.
- Retain all resources and rollback state.
- Make the frozen posture declarative in Terraform.
- Leave Cloudflare unchanged.

No AWS resource or S3 object was deleted.

## Before

- Enabled schedules: `wolves-daily-run`, `wolves-agent-uk-opening`, `wolves-agent-us-trip`, `wolves-agent-uk-final`.
- Disabled schedule: `wolves-agent-uk-finals`.
- Backend desired/running/pending tasks: `1/1/0`.
- Engine daily and agent running/pending tasks: `0/0`.
- `wolves-agent-uk-final` existed in AWS but was absent from Terraform state.

The `active-runs` workflow run [30215670003](https://github.com/jonahanton/wolves-ai/actions/runs/30215670003) did not provide valid evidence because `BACKEND_URL` was empty and the pipeline masked the curl failure. Direct ECS task-family queries were used instead. The workflow and CLI now fail correctly in this condition.

## Changes

- Imported `default/wolves-agent-uk-final` at `module.scheduler.aws_scheduler_schedule.agent_daily["uk-final"]`.
- Disabled four enabled schedules with `UpdateSchedule`; the fifth was already disabled.
- Cleared expired start and end bounds that AWS refuses to echo during an update after expiry. The retained schedules remain disabled and Terraform records their exact state.
- Set `wolves-backend` desired count to zero with `UpdateService`.
- Applied a Terraform refresh-only plan: `0 added, 0 changed, 0 destroyed`.

## After

- All five schedules report `DISABLED`.
- Backend desired/running/pending tasks: `0/0/0`.
- All cluster running and pending task lists are empty.
- Terraform validation passes.
- The post-freeze plan contains no schedule-state or backend-count drift.

The remaining plan is pre-existing task-definition normalisation: three replacement task definitions and their dependent service and schedule target references. It was not applied.

## Evidence

Private evidence bundle:

`s3://wolves-superforecaster-prod/static-archive/operations/freezes/cb11c865f75beb13708e384ceb9481b52fc8fe77b1b20df5ff7b8a792376b3e4.tar.gz`

SHA-256:

`cb11c865f75beb13708e384ceb9481b52fc8fe77b1b20df5ff7b8a792376b3e4`

Terraform state hashes:

- Before: `3ad54ddfdc7803748b9af446104cf7c13b7577d952c6ac92209bd917867332fe`
- After: `7708b7135fbb5c4752331f5fe139e5771143d19f5e84ccb003330d7bd65062b1`

The bundle contains both state snapshots, the post-freeze plan, Scheduler and ECS post-state, running and pending task inventories, CloudTrail records for five schedule update attempts and one service update, Terraform version information and per-file checksums.
