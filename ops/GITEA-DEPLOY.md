# Deploy via Gitea Actions (host-mode runner on the VPS)

Goal: deploys run on the VPS itself, so the VPS needs no inbound SSH from GitHub.
Same pattern as `~/development/pv-planner` (`pvplanner-app/DEPLOY-gitea.md`).

## Design
- Gitea (`https://code.lab.halbewahrheit21.de`, tailnet only) holds the repo
  `marvin/VibedInsight`. A push to `main` there triggers `.gitea/workflows/deploy.yml`.
- A host-mode `act_runner` (label `vibedinsight`) runs the job as `aiplatform` and calls
  `/srv/vibedinsight/deploy.sh update` (own pre-deploy DB backup included).
- GitHub keeps CI and the Flutter release; only the deploy moves.
- The runner has Docker access = effectively root. Differences to pv-planner:
  it runs as `aiplatform` (not root), is registered for THIS repository only
  (repo-level token), and the workflow never runs on pull requests.
- Local dev: remote `gitea` = `ssh://git@code.lab.halbewahrheit21.de:2222/marvin/VibedInsight.git`.

## Setup (once, on the VPS)
Gitea Actions are already enabled on the instance (pv-planner uses them); enable them
for this repo too (Repo -> Settings -> Actions -> General). The `act_runner` binary may
already exist at `/usr/local/bin/act_runner` (installed for pv-planner); reuse it.

1. Gitea: Repo -> Settings -> Actions -> Runners -> "Create new runner" -> copy the token.
2. Register in its own directory, token via environment (never on the command line):
   ```
   sudo install -d -o aiplatform /srv/act-runner-vibedinsight && cd /srv/act-runner-vibedinsight
   read -rs GITEA_RUNNER_REGISTRATION_TOKEN && export GITEA_RUNNER_REGISTRATION_TOKEN
   export GITEA_INSTANCE_URL=https://code.lab.halbewahrheit21.de
   act_runner register --no-interactive --name vps-vibedinsight --labels vibedinsight:host
   unset GITEA_RUNNER_REGISTRATION_TOKEN
   ```
3. systemd unit `/etc/systemd/system/act_runner-vibedinsight.service`:
   ```
   [Unit]
   Description=Gitea act_runner (VibedInsight)
   After=docker.service network-online.target
   [Service]
   User=aiplatform
   WorkingDirectory=/srv/act-runner-vibedinsight
   ExecStart=/usr/local/bin/act_runner daemon
   Restart=always
   [Install]
   WantedBy=multi-user.target
   ```
   `sudo systemctl daemon-reload && sudo systemctl enable --now act_runner-vibedinsight`
4. Point the deploy checkout at Gitea so the deploy does not depend on GitHub:
   `cd /srv/vibedinsight && git remote set-url origin http(s)/ssh URL of the local Gitea repo`
   (the VPS needs read access; a read-only deploy key is enough).

## Test (stage 1, nothing is deployed)
Gitea UI -> Actions -> "Deploy to VPS" -> Run workflow, action = `check`.
Expect: host/user line, `docker compose ps` of the stack, origin URL.
Then run once with action = `deploy` at a quiet moment and compare `/health`.

## Cutover (stage 2)
1. In `.gitea/workflows/deploy.yml` enable the `push` trigger (with the `paths` filter).
2. `.github/workflows/deploy.yml`: replace the `push` trigger by `workflow_dispatch`
   (manual fallback). The Gitea copy of the repo already contains this change.
3. Afterwards remove the GitHub secrets `VPS_HOST`, `VPS_USER`, `VPS_SSH_KEY` and the
   matching public key from `~/.ssh/authorized_keys` on the VPS.
