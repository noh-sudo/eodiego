# 어디GO EC2 백엔드 배포 안내

작성일: 2026-09-18 · 대상: 백엔드 담당자와 프론트 협업자

**현재는 배포 파일과 절차를 준비한 상태입니다. EC2 설치, DuckDNS 주소 등록, RDS 연결, HTTPS 발급 및 실제 사이트 연결은 아직 확인하지 않았습니다.** 서비스 주소는 `eodiego-jeju.duckdns.org`입니다. 기존 `.env`는 변경하지 않습니다.

최종 연결은 `브라우저 → 화면(ui/) Worker → HTTPS/nginx → D(8003) → A/B/C → RDS·외부 API`입니다. 이번 작업 범위는 백엔드 배포와 연결 안내 준비이며, 프론트 환경변수 적용·재배포·화면 검증은 협업자가 담당합니다.

로컬에서는 배포 전용 검사 12개와 Bash 문법 검사가 통과했습니다. 실제 Ubuntu의 systemd/nginx 실행, 운영 DB와 외부 API 연결은 아직 검증하지 않았습니다. 배포 파일은 저장소에 추가됐지만 **커밋·푸시는 아직 하지 않았습니다**.

원격에 올릴 때는 Windows PowerShell에서 아래 순서로 배포 폴더만 확인·반영합니다. `git diff --cached`에 다른 기존 변경이 있다면 해당 변경과 분리합니다.

```powershell
cd C:\Users\shqkr\eodiego
git branch --show-current
git check-ignore PythonServer/.env
git add -- PythonServer/deploy
git diff --cached --stat
git diff --cached
git commit -m "chore: add EC2 backend deployment configuration" -- PythonServer/deploy
git push origin feature/Backend
```

브랜치는 `feature/Backend`, 비밀 파일 제외 확인 결과는 `PythonServer/.env`여야 합니다. 커밋 전에는 새 파일에 실제 키나 비밀번호를 채우지 않았는지 확인합니다.

## 1. AWS와 주소 준비

**기존 RDS가 본인 AWS 계정에 있다는 점은 확인됐습니다.** 실제 RDS 엔드포인트, 서울 리전, VPC ID와 연결 상태는 아직 확인하지 않았습니다. 인스턴스 생성 전에 해당 RDS의 VPC ID를 확인하고 EC2도 그 VPC에 만듭니다. 같은 VPC에서는 RDS 보안 그룹이 EC2 보안 그룹을 허용하도록 연결할 수 있습니다. [AWS 공식 연결 구성](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/USER_VPC.Scenarios.html)

| 항목 | 사용할 설정 |
|---|---|
| 리전 | 서울 `ap-northeast-2` |
| 운영체제 / 아키텍처 | Ubuntu Server 24.04 LTS / x86_64 |
| 인스턴스 / 디스크 | `t3.micro` / gp3 20 GiB |
| 네트워크 | 기존 RDS와 같은 VPC, 인터넷 게이트웨이로 연결되는 퍼블릭 서브넷 |
| 주소 | Elastic IP를 할당하고 EC2에 연결 |
| SSH | 키 페어 사용, TCP 22는 현재 내 공인 IP `/32`만 허용 |
| 웹 | TCP 80·443은 공개, TCP 8000~8003은 인바운드 규칙을 만들지 않음 |
| DB | RDS TCP 3306에 EC2 보안 그룹을 허용 |

인스턴스·스토리지·공인 IPv4 등에는 계정 조건에 따른 비용이 발생할 수 있습니다. 이 구성은 무료 사용을 보장하지 않습니다.

RDS에는 우선 EC2 보안 그룹의 3306 접근을 **추가**합니다. 기존 규칙은 EC2에서 DB 연결이 성공한 후 검토하여 제거하고, 애플리케이션 접근은 EC2 보안 그룹으로 제한합니다. 다른 운영·관리 연결이 있다면 담당자와 조정합니다.

DuckDNS에 로그인하여 사용 가능한 이름을 직접 등록하고 IPv4를 Elastic IP로 지정합니다. EIP를 유지하면 주기적인 IP 변경 작업은 필요하지 않습니다. DuckDNS 계정 토큰은 프론트와 공유하지 않습니다. 주소 갱신 API를 사용한다면 HTTPS를 사용합니다. [DuckDNS 공식 규격](https://www.duckdns.org/spec.jsp)

Windows PowerShell에서 실제 주소가 EIP로 조회되는지 확인한 뒤 SSH로 접속합니다. 키 경로와 EIP는 본인 값으로 바꿉니다.

```powershell
Resolve-DnsName eodiego-jeju.duckdns.org -Type A
ssh -i "C:\실제경로\키파일.pem" ubuntu@ELASTIC_IP
```

이하 명령은 SSH로 접속한 **EC2의 Ubuntu 터미널**에서 실행합니다.

## 2. 설치와 환경변수 확인

배포 파일이 포함된 `feature/Backend` 코드를 EC2의 `~/eodiego`에 준비합니다. 원격 저장소에 배포 파일을 올리지 않았다면 새로 내려받기만 해서는 포함되지 않습니다. 반영된 커밋을 사용하거나 준비한 `PythonServer/deploy` 폴더를 SSH/SFTP로 전달해야 합니다. `.env`를 코드와 함께 업로드하거나 커밋하지 않습니다.

```bash
git clone --branch main --single-branch https://github.com/noh-sudo/eodiego.git ~/eodiego
cd ~/eodiego/PythonServer
test -f deploy/setup_ec2.sh
sudo bash deploy/setup_ec2.sh
```

이미 `~/eodiego` 저장소가 있으면 clone은 생략하고, 로컬 변경을 확인한 뒤 해당 브랜치에서 `git pull --ff-only`로 업데이트합니다. 저장소가 비공개이면 읽기 전용 Git 인증을 사용하며, 토큰을 저장소 URL에 넣지 않습니다.

설치 스크립트는 Python 환경, nginx, Ubuntu의 `certbot`·`python3-certbot-nginx` 패키지, 네 서비스와 실행 그룹을 설치합니다. **애플리케이션 서비스 시작과 부팅 시 자동 시작은 하지 않습니다.**

| 경로 | 내용 |
|---|---|
| `/opt/eodiego/app` | `PythonServer` 코드 복사본. 기존 `.env` 제외 |
| `/opt/eodiego/venv` | Python 실행 환경 |
| `/etc/eodiego/eodiego.env` | 운영 설정·비밀 값. root 소유, 권한 `0600` |

운영 파일은 숫자 기본값이 채워진 `deploy/eodiego.env.example`을 기준으로 작성합니다. 처음에는 `USE_LLM=false`를 유지합니다. 사용자가 보관한 기존 `.env`에서 필요한 실제 비밀 값만 안전한 편집 세션으로 옮깁니다.

```bash
sudoedit /etc/eodiego/eodiego.env
sudo chown root:root /etc/eodiego/eodiego.env
sudo chmod 600 /etc/eodiego/eodiego.env
```

확인할 값은 다음과 같습니다.

- `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`: 기존 RDS와 앱 계정 값. `DB_HOST`에는 RDS 엔드포인트를 사용합니다. TLS를 쓰면 `DB_SSL_CA`는 `/etc/eodiego/global-bundle.pem`처럼 앱 계정이 읽을 수 있는 실제 인증서 파일 경로로 지정합니다. 서비스에서 접근이 차단되는 사용자 홈 폴더에 인증서를 두지 않습니다.
- `KTO_SERVICE_KEY`: 운영 검사는 `USE_MOCK=false`와 실제 키를 요구하므로 보관한 관광공사 키를 입력합니다. 초기 연결 점검은 관광공사 API를 호출하지 않습니다.
- `BFF_GATEWAY_TOKEN`: 충분히 긴 무작위 비밀 값으로 지정하고, 추후 동일한 값을 프론트 Worker에 설정합니다. 암호 관리 도구에서 생성한 64자리 무작위 16진 문자열을 사용할 수 있습니다.
- `COOKIE_SECURE=true`, `COOKIE_SAMESITE=lax`, 쿠키 이름은 `session_id`로 유지합니다. `ALLOWED_ORIGINS`는 `https://eodiego-jeju.duckdns.org`처럼 정확한 화면 출처를 적습니다.
- A/B/C 내부 주소는 `127.0.0.1`과 8000/8001/8002를 사용합니다. 숫자 항목을 빈칸으로 두지 않고 배포 템플릿 값을 유지합니다.

`.env`를 `source`·`eval`로 실행하거나, 비밀번호를 명령 인수에 넣지 않습니다. 비밀 값은 채팅, Git, 터미널 명령 기록에 남기지 않습니다. systemd가 root 전용 파일을 읽어 서비스에 전달하므로 앱 계정이 설정 파일을 직접 읽을 권한은 필요하지 않습니다.

이어서 **환경변수 형식과 DB 읽기 연결만 검사**합니다. 이 검사는 테이블을 만들거나 데이터를 변경하지 않습니다.

```bash
sudo systemd-run --wait --pipe --collect \
  -p User=eodiego -p Group=eodiego \
  -p WorkingDirectory=/opt/eodiego/app \
  -p EnvironmentFile=/etc/eodiego/eodiego.env \
  -p Environment=PYTHONPATH=/opt/eodiego/app \
  /opt/eodiego/venv/bin/python \
  /opt/eodiego/app/deploy/check_env.py --database
```

실패하면 다음 단계로 넘어가지 않고 누락 설정, RDS 보안 그룹, VPC, DB 계정·스키마를 확인합니다. 테이블이 없다면 RDS 관리자가 `PythonServer/db/schema.sql`을 적용해야 합니다. 앱 계정의 운영 권한은 `SELECT, INSERT`입니다. 운영 DB에서 일반 `pytest`를 실행하지 않습니다.

## 3. 서비스 시작과 HTTPS 확인

사전 검사가 통과하면 네 서비스를 실행하고 부팅 시 자동 시작을 등록합니다.

```bash
sudo systemctl enable --now eodiego.target
sudo systemctl status 'eodiego-*' --no-pager
```

실행 그룹이 활성 상태여도 각 서비스와 기능을 별도로 확인해야 합니다. 아래 점검은 토큰 없음·잘못된 토큰의 403 거부, 올바른 토큰의 `/ui/regions` JSON 성공을 확인합니다. 관광공사·LLM API 호출이나 계정 생성은 하지 않습니다.

시작 명령 직후에는 앱이 아직 준비 중일 수 있습니다. 연결 거부가 나오면 네 서비스의 상태·로그를 확인하고 기동이 끝난 뒤 다시 검사합니다. `PASS`가 나오기 전에는 다음 단계로 넘어가지 않습니다.

```bash
sudo systemd-run --wait --pipe --collect \
  -p User=eodiego -p Group=eodiego \
  -p WorkingDirectory=/opt/eodiego/app \
  -p EnvironmentFile=/etc/eodiego/eodiego.env \
  -p Environment=PYTHONPATH=/opt/eodiego/app \
  /opt/eodiego/venv/bin/python \
  /opt/eodiego/app/deploy/smoke_test.py
```

다음으로 **실제 등록한 주소**를 지정하여 nginx 설정을 설치합니다. `__DDNS_HOST__`를 운영 설정을 쓰는 과정에서 교체하며, 저장소의 원본 파일은 수정하지 않습니다. 이 단계는 첫 HTTPS 설정 때 한 번 수행합니다.

```bash
DDNS_HOST='eodiego-jeju.duckdns.org'
cd ~/eodiego/PythonServer
sed "s/__DDNS_HOST__/${DDNS_HOST}/g" deploy/nginx/eodiego.conf \
  | sudo tee /etc/nginx/sites-available/eodiego > /dev/null
sudo ln -sfn /etc/nginx/sites-available/eodiego /etc/nginx/sites-enabled/eodiego
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl reload nginx
sudo certbot --nginx --redirect -d "$DDNS_HOST"
sudo certbot renew --dry-run
```

`nginx -t`가 실패하면 reload와 Certbot을 실행하지 말고 오류를 먼저 고칩니다. 위 default 링크 제거는 이 앱 전용 새 EC2를 전제로 합니다. 인증서 발급 전에는 도메인이 EIP를 가리키고 외부에서 80번 포트로 접근할 수 있어야 합니다. Certbot은 nginx의 HTTPS 설정과 갱신 기능을 제공합니다. [Certbot 공식 nginx 안내](https://certbot.eff.org/instructions?os=pip&ws=nginx)

HTTPS 주소로 같은 검사를 다시 수행합니다.

```bash
sudo systemd-run --wait --pipe --collect \
  -p User=eodiego -p Group=eodiego \
  -p WorkingDirectory=/opt/eodiego/app \
  -p EnvironmentFile=/etc/eodiego/eodiego.env \
  -p Environment=PYTHONPATH=/opt/eodiego/app \
  /opt/eodiego/venv/bin/python \
  /opt/eodiego/app/deploy/smoke_test.py \
  --base-url https://eodiego-jeju.duckdns.org
```

백엔드 전달 조건은 **DB 검사 성공 + 네 서비스 정상 + 로컬·HTTPS 점검 성공 + 인증서 갱신 모의 검사 성공**입니다. `/ui/regions` 성공만으로 로그인·일정 저장·실제 관광·LLM 기능까지 검증됐다고 판단하지 않습니다. 루트 주소나 `/docs`에서 404가 나오는 것은 `/ui/`만 공개하는 설정에서 정상입니다.

EC2에서 DB 접속이 성공한 뒤 RDS의 기존 외부 3306 허용 규칙을 정리하고 퍼블릭 액세스를 끕니다. 적용 후 EC2에서 DB 사전 검사와 로컬 점검을 다시 수행합니다. 기존 외부 관리 접속이 필요한 경우 먼저 별도의 관리 경로를 마련합니다.

## 4. 협업자 전달과 이후 운영

아래 문구는 앞의 전달 조건을 실제로 만족한 뒤 주소를 채워 전달합니다. 토큰 값은 이 메시지에 넣지 말고 안전한 별도 경로로 전달합니다.

```text
어디GO 백엔드 연결 정보를 전달합니다.

BFF_BASE_URL=https://eodiego-jeju.duckdns.org
BFF_GATEWAY_TOKEN=별도로 안전하게 전달한 동일한 값

BFF_BASE_URL은 HTTPS 출처만 넣고 /ui를 붙이지 않습니다.
main 브랜치의 ui/ 폴더(/ui/ Worker 프록시 포함)를 배포해 주세요.

화면 Worker의 서버 환경변수에 위 값을 설정한 뒤
재배포해야 반영됩니다. BFF_GATEWAY_TOKEN은 브라우저 공개 변수로 만들지
말고 Worker 서버 비밀 값으로 설정해 주세요. 사이트의 기존 공개 대상과
접근 설정은 유지해 주세요.

재배포 후 회원가입 → 로그인 → 새로고침 시 로그인 유지 → 일정 생성 →
저장·조회·삭제 → 로그아웃을 확인해 주세요.
```

협업자에게 필요한 비밀은 `BFF_GATEWAY_TOKEN`뿐입니다. 백엔드 `.env` 전체, 관광공사·LLM API 키, DB 비밀번호, SSH 키, DuckDNS 계정 토큰을 전달하지 않습니다. 기본 연결을 확인한 다음 실제 관광공사·LLM 사용을 별도로 검증합니다. `USE_LLM=true`로 바꿀 때는 키·모델·한도를 확인하고, 아래 재시작 절차를 적용합니다.

코드를 갱신할 때는 배포 파일이 포함된 버전을 `~/eodiego`에 먼저 준비하고 설치를 다시 실행합니다.

```bash
cd ~/eodiego/PythonServer
sudo bash deploy/setup_ec2.sh
```

재설치는 실행 그룹을 중지하고 코드를 반영하며 운영 환경변수 파일을 보존합니다. **서비스 중단 시간이 발생합니다.** 2절의 사전 검사를 다시 실행한 후 `sudo systemctl enable --now eodiego.target`, 3절의 로컬·HTTPS 점검 순서로 마무리합니다. 기존 HTTPS가 설정되어 있으면 nginx 원본 템플릿으로 운영 설정을 덮어쓰지 않습니다.

환경변수만 바꾼 경우에도 사전 검사 후 `sudo systemctl restart eodiego.target`을 실행하고 로컬·HTTPS 점검을 반복합니다. 서비스 상태와 최근 로그는 아래에서 확인할 수 있습니다. 로그를 외부에 공유할 때는 비밀 값이나 사용자 정보가 없는지 확인합니다.

```bash
sudo systemctl status 'eodiego-*' --no-pager
sudo journalctl -u 'eodiego-*' -n 100 --no-pager
sudo systemctl list-timers --all | grep certbot
```

설치나 점검이 실패하면 정상이라고 전달하지 않습니다. 이 안내서는 절차이며, 실제 배포 완료 여부는 위 검사의 실행 결과로 확인해야 합니다.
