#!/usr/bin/env bash
set -euo pipefail

app_dir=/opt/riesgo-comunal
backup_dir=/var/backups/riesgo-comunal
repo=""
branch=main
domain=""
admin_email=""

usage() {
  echo "usage: GIT_TOKEN=<token> deploy.sh --repo <https or ssh url> --domain <domain> --admin-email <email> [--branch main]" >&2
  exit 2
}

die() {
  echo "ERROR: $*" >&2
  exit 1
}

while [ $# -gt 0 ]; do
  case "$1" in
    --repo) repo="${2:?}"; shift 2 ;;
    --branch) branch="${2:?}"; shift 2 ;;
    --domain) domain="${2:?}"; shift 2 ;;
    --admin-email) admin_email="${2:?}"; shift 2 ;;
    -h|--help) usage ;;
    *) echo "unknown argument: $1" >&2; usage ;;
  esac
done

[ "$(id -u)" -eq 0 ] || die "run as root"
[ -n "$repo" ] && [ -n "$domain" ] && [ -n "$admin_email" ] || usage
. /etc/os-release
[ "${ID:-}" = ubuntu ] || die "this script targets Ubuntu (found ${ID:-unknown})"

log() {
  echo "==> $*"
}

install_packages() {
  export DEBIAN_FRONTEND=noninteractive
  apt-get update
  apt-get install -y ca-certificates curl git openssl ufw cron
}

install_docker() {
  if docker compose version >/dev/null 2>&1; then
    log "Docker and Compose already installed: $(docker --version)"
    return
  fi
  log "Installing Docker Engine and the Compose plugin from download.docker.com"
  install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
  chmod a+r /etc/apt/keyrings/docker.asc
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu ${UBUNTU_CODENAME:-$VERSION_CODENAME} stable" \
    > /etc/apt/sources.list.d/docker.list
  apt-get update
  apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
  systemctl enable --now docker
  docker compose version
}

open_firewall() {
  log "Opening 22, 80 and 443 with ufw"
  ufw allow 22/tcp
  ufw allow 80/tcp
  ufw allow 443/tcp
  ufw --force enable
  ufw status
}

git_auth() {
  case "$repo" in
    https://*)
      [ -n "${GIT_TOKEN:-}" ] || die "GIT_TOKEN is required for an https repo URL (private repo); or use an ssh URL with a deploy key"
      git -c "http.extraHeader=Authorization: Basic $(printf 'x-access-token:%s' "$GIT_TOKEN" | base64 -w0)" "$@"
      ;;
    *)
      git "$@"
      ;;
  esac
}

clone_repo() {
  if [ -d "$app_dir/.git" ]; then
    log "Updating $app_dir to origin/$branch"
    git_auth -C "$app_dir" fetch origin "$branch"
    git -C "$app_dir" checkout "$branch"
    git -C "$app_dir" merge --ff-only "origin/$branch"
    return
  fi
  [ -e "$app_dir" ] && die "$app_dir exists but is not a git checkout"
  log "Cloning $repo ($branch) into $app_dir"
  git_auth clone --branch "$branch" "$repo" "$app_dir"
}

write_env() {
  local env_file="$app_dir/.env"
  if [ -f "$env_file" ]; then
    log "Keeping existing $env_file (secrets are never regenerated; edit it by hand to change values)"
    return
  fi
  log "Writing $env_file"
  local admin_password="${ADMIN_PASSWORD:-}"
  [ -n "$admin_password" ] || admin_password="$(openssl rand -base64 18 | tr -d '/+=')"
  umask 077
  cat > "$env_file" <<EOF
POSTGRES_PASSWORD=$(openssl rand -hex 24)
JWT_SECRET=$(openssl rand -hex 32)

SITE_ADDRESS=$domain
PUBLIC_URL=https://$domain
HTTP_PORT=80
HTTPS_PORT=443

TENANT_CUT=
TENANT_SLUG=
TENANT_NAME=
TENANT_REGION=07
ADMIN_EMAIL=$admin_email
ADMIN_PASSWORD=$admin_password
SEED_DEMO=false

LLM_BASE_URL=
LLM_API_KEY=
LLM_MODEL=
EMBEDDING_BASE_URL=
EMBEDDING_API_KEY=
EMBEDDING_MODEL=

SENAPRED_ALERTS_ENABLED=true

DMC_USER=${DMC_USER:-}
DMC_TOKEN=${DMC_TOKEN:-}
EOF
  chmod 600 "$env_file"
  umask 022
}

start_stack() {
  cd "$app_dir"
  log "Building and starting the stack (the first build takes several minutes)"
  docker compose up -d --build || {
    docker compose logs bootstrap 2>&1 | grep -viE 'password|contrase|clave' | tail -40
    die "docker compose up failed"
  }
  log "Waiting for bootstrap to finish"
  local state=""
  for _ in $(seq 1 360); do
    state="$(docker compose ps -a bootstrap --format '{{.State}} {{.ExitCode}}')"
    case "$state" in exited*) break ;; esac
    sleep 5
  done
  docker compose logs bootstrap 2>&1 | grep -viE 'password|contrase|clave' | tail -20
  [ "$state" = "exited 0" ] || die "bootstrap did not exit 0 (state: ${state:-unknown}); see docker compose logs bootstrap"
}

create_lota() {
  cd "$app_dir"
  if [ "$(docker compose exec -T db psql -U riesgo -d riesgo -tAc "select 1 from municipality where cut_code = '08106'")" = "1" ]; then
    log "Lota (08106) already exists"
    return
  fi
  log "Creating tenant Lota (08106)"
  docker compose run --rm bootstrap python -m app.cli create-tenant --cut 08106 --slug lota
}

wait_api() {
  cd "$app_dir"
  local health=""
  for _ in $(seq 1 60); do
    health="$(docker compose ps api --format '{{.Health}}')"
    [ "$health" = healthy ] && break
    sleep 5
  done
  [ "$health" = healthy ] || die "api is not healthy (state: ${health:-unknown}); see docker compose logs api"
  log "api healthy"
}

install_backup() {
  log "Installing daily backup to $backup_dir"
  install -d -m 700 "$backup_dir"
  cat > /usr/local/sbin/riesgo-comunal-backup <<EOF
#!/usr/bin/env bash
set -euo pipefail
cd $app_dir
docker compose exec -T db pg_dump -U riesgo -Fc riesgo > $backup_dir/backup-\$(date +%F).dump
docker run --rm -v riesgo-comunal_uploads:/data -v $backup_dir:/out alpine tar czf /out/uploads-\$(date +%F).tgz -C /data .
find $backup_dir -type f -mtime +14 -delete
EOF
  chmod 750 /usr/local/sbin/riesgo-comunal-backup
  echo "30 3 * * * root /usr/local/sbin/riesgo-comunal-backup >> /var/log/riesgo-comunal-backup.log 2>&1" > /etc/cron.d/riesgo-comunal-backup
  chmod 644 /etc/cron.d/riesgo-comunal-backup
}

check_https() {
  local code
  code="$(curl -s -o /dev/null -w '%{http_code}' --max-time 20 "https://$domain/api/health" || true)"
  if [ "$code" = 200 ]; then
    log "https://$domain/api/health answers 200"
  else
    echo "WARNING: https://$domain/api/health answered '${code}'. If DNS does not point here yet, Caddy retries the certificate once it does (dig +short $domain)." >&2
  fi
}

install_packages
install_docker
open_firewall
clone_repo
write_env
start_stack
create_lota
wait_api
install_backup
check_https

log "Done. Super admin: $admin_email (password in $app_dir/.env, ADMIN_PASSWORD)."
log "Public pages: https://$domain/c/<slug>, for example https://$domain/c/lota and https://$domain/c/talca"
