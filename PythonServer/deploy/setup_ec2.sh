#!/usr/bin/env bash
# Ubuntu 24.04 설치 스크립트 (설정 전에는 앱을 시작하지 않음)
set -euo pipefail
if [[ ${EUID} -ne 0 ]]; then
  echo 'Run with sudo bash deploy/setup_ec2.sh' >&2
  exit 1
fi
source /etc/os-release
if [[ ${ID} != ubuntu || ${VERSION_ID} != 24.04 ]]; then
  echo 'This installer supports Ubuntu 24.04 only.' >&2
  exit 1
fi
source_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
app_dir=/opt/eodiego/app
venv_dir=/opt/eodiego/venv
if [[ ${source_dir} == /opt/eodiego || ${source_dir} == /opt/eodiego/* ]]; then
  echo 'Run from a separate Git checkout, not /opt/eodiego.' >&2
  exit 1
fi
for service in A_backend B_openapi C_ai_planner D_frontend; do
  [[ -f "${source_dir}/${service}/requirements.txt" ]]
done
# rsync --delete를 심볼릭 링크 없는 고정 설치 경로로 제한
if [[ $(readlink -m "${app_dir}") != /opt/eodiego/app ]]; then
  echo 'Refusing a symlinked installation path.' >&2
  exit 1
fi
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y python3 python3-venv python3-pip nginx certbot python3-certbot-nginx rsync ca-certificates curl
if ! id eodiego >/dev/null 2>&1; then
  useradd --system --user-group --home-dir /opt/eodiego --no-create-home --shell /usr/sbin/nologin eodiego
fi
install -d -o root -g eodiego -m 0750 /opt/eodiego "${app_dir}" /etc/eodiego
if [[ -f /etc/systemd/system/eodiego.target ]]; then
  systemctl stop eodiego.target
fi
rsync -a --delete --chown=root:eodiego --chmod=D750,F640 \
  --exclude='.env*' --exclude='env' --exclude='.venv/' --exclude='venv/' \
  --exclude='.git/' --exclude='.run/' --exclude='__pycache__/' \
  --exclude='*.pyc' --exclude='.pytest_cache/' \
  "${source_dir}/" "${app_dir}/"
python3 -m venv "${venv_dir}"
"${venv_dir}/bin/python" -m pip install \
  -r "${app_dir}/A_backend/requirements.txt" \
  -r "${app_dir}/B_openapi/requirements.txt" \
  -r "${app_dir}/C_ai_planner/requirements.txt" \
  -r "${app_dir}/D_frontend/requirements.txt"
if [[ ! -e /etc/eodiego/eodiego.env ]]; then
  install -o root -g root -m 0600 "${app_dir}/deploy/eodiego.env.example" /etc/eodiego/eodiego.env
fi
chown root:root /etc/eodiego/eodiego.env
chmod 0600 /etc/eodiego/eodiego.env
for unit in "${app_dir}"/deploy/systemd/*; do
  install -o root -g root -m 0644 "${unit}" /etc/systemd/system/
done
systemctl daemon-reload
echo 'Installed. Existing production environment was preserved.'
echo 'Edit /etc/eodiego/eodiego.env; run check_env.py --database via systemd-run.'
echo 'Then: sudo systemctl enable --now eodiego.target'
echo 'Configure nginx and TLS separately, following the deployment guide.'
