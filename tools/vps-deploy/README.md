# vps-deploy

`deploy.sh` installs the platform on a fresh Ubuntu 24.04 KVM VPS, run as root. It is safe to run again: it skips what is already done and never regenerates secrets.

What it does, in order:

1. Installs `ca-certificates curl git openssl ufw cron`, then Docker Engine and the Compose plugin from Docker's apt repository (`download.docker.com`), unless `docker compose` already works.
2. Allows 22/tcp, 80/tcp and 443/tcp in ufw and enables it. If SSH listens on a port other than 22, add it with `ufw allow <port>/tcp` before running the script, or you lock yourself out.
3. Clones the repository into `/opt/riesgo-comunal` (or fast-forwards it to `origin/<branch>` if it is already there).
4. Writes `/opt/riesgo-comunal/.env` (mode 600) only if it does not exist: random `POSTGRES_PASSWORD` and `JWT_SECRET` from `openssl rand`, `TENANT_REGION=07` (the 30 Maule comunas), empty `TENANT_CUT` and `TENANT_SLUG`, `SITE_ADDRESS=<domain>`, `PUBLIC_URL=https://<domain>`, `ADMIN_EMAIL` from the argument and `ADMIN_PASSWORD` from the environment or generated. `DMC_USER` and `DMC_TOKEN` are copied from the environment if set.
5. Runs `docker compose up -d --build` and waits for `bootstrap` to exit 0 (up to 30 minutes).
6. Creates the Lota tenant (`create-tenant --cut 08106 --slug lota`) if it does not exist.
7. Waits for the `api` container to report healthy.
8. Installs `/usr/local/sbin/riesgo-comunal-backup` and `/etc/cron.d/riesgo-comunal-backup`: every day at 03:30 server time it writes `pg_dump` and the uploads volume to `/var/backups/riesgo-comunal` (the commands in `docs/deployment.md`) and deletes files older than 14 days. Copy that folder off the server as well.
9. Calls `https://<domain>/api/health` and warns (does not fail) if it does not answer 200 yet, which is normal while DNS has not reached the VPS.

## Usage

The repository is private, so the VPS needs read access. Two options.

**Token over HTTPS.** Create a GitHub fine-grained personal access token with read-only `Contents` access to this repository only. Pass it in the environment, not as an argument, so it does not appear in the process list; the script sends it as a header and does not store it in `.git/config`, so pass it again on every rerun:

```bash
scp tools/vps-deploy/deploy.sh root@<vps-ip>:/root/
ssh root@<vps-ip>
read -rs GIT_TOKEN && export GIT_TOKEN
bash /root/deploy.sh --repo https://github.com/<owner>/riesgo-comunal.git --domain <domain> --admin-email <email> --branch main
```

**SSH deploy key.** On the VPS, as root:

```bash
ssh-keygen -t ed25519 -N "" -f /root/.ssh/id_ed25519
ssh-keyscan github.com >> /root/.ssh/known_hosts
cat /root/.ssh/id_ed25519.pub
```

Add the printed key in GitHub under the repository's Settings, Deploy keys (read-only), then run the script with `--repo git@github.com:<owner>/riesgo-comunal.git`. Later `git pull` works without a token.

To choose the admin password instead of generating one, export `ADMIN_PASSWORD` before running. The super admin can switch between all 31 comunas; the password stays in `/opt/riesgo-comunal/.env`.

## Updates

Run the script again with the same arguments, or by hand:

```bash
cd /opt/riesgo-comunal && git pull && docker compose up -d --build
```

## Verification status

`bash -n deploy.sh` passes. The script has not been run on a real VPS yet.
