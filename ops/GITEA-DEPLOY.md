# Deploy via Gitea Actions (host-mode runner on the VPS)

Goal: deploys run on the VPS itself, so the VPS needs no inbound SSH from GitHub.

## Design
- Gitea (on the VPS) holds a copy of this repo; a push to `main` there triggers
  `.gitea/workflows/deploy.yml`.
- A host-mode `act_runner` (label `vps`) runs the job as `aiplatform` and calls
  `/srv/vibedinsight/deploy.sh update` (own pre-deploy DB backup included).
- GitHub keeps CI and the Flutter release; only the deploy moves.
- The runner has Docker access = effectively root on the VPS. Register it for
  THIS repository only (repo-level token), never for the whole instance, and
  keep the workflow on `push` to `main` / manual dispatch (no pull_request).

## Setup (once, on the VPS as aiplatform)
1. Gitea: create the repo `VibedInsight`, enable Actions for it
   (Settings -> Advanced -> Actions). Push this repo to it.
2. Gitea: Repo -> Settings -> Actions -> Runners -> "Create new runner" -> copy
   the registration token into a file only you can read, e.g.
   `install -m 600 /dev/null ~/.gitea-runner-token && nano ~/.gitea-runner-token`.
3. Register (token via environment, never on the command line):
   ```
   export GITEA_INSTANCE_URL=<gitea base url>
   export GITEA_RUNNER_REGISTRATION_TOKEN="$(cat ~/.gitea-runner-token)"
   act_runner register --no-interactive --name vps-vibedinsight --labels vps:host
   shred -u ~/.gitea-runner-token
   ```
4. Run it as a service (systemd user or system unit running `act_runner daemon`).
5. Point the deploy checkout at Gitea so the deploy does not depend on GitHub:
   `cd /srv/vibedinsight && git remote set-url origin <local gitea clone url>`.
6. Local dev machine: push to both remotes, e.g.
   `git remote set-url --add --push origin <gitea url>` (and re-add the GitHub URL).

## Test (stage 1, nothing is deployed)
Gitea UI -> Actions -> "Deploy to VPS" -> Run workflow, action = `check`.
Expect: host/user line, `docker compose ps` of the stack, origin URL.
Then run once with action = `deploy` on a quiet moment and compare `/health`.

## Cutover (stage 2)
1. In `.gitea/workflows/deploy.yml` enable the `push` trigger.
2. In `.github/workflows/deploy.yml` replace the `push` trigger by
   `workflow_dispatch` (kept as manual fallback).
3. Afterwards remove the GitHub secrets `VPS_HOST`, `VPS_USER`, `VPS_SSH_KEY`
   and the matching public key from `~/.ssh/authorized_keys` on the VPS.
