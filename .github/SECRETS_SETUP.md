# GitHub Secrets 설정 가이드

## CD 배포를 위한 필수 Secrets

GitHub 저장소 → Settings → Secrets and variables → Actions 에서 설정

| Secret 이름 | 설명 | 예시 |
|------------|------|------|
| `DEPLOY_HOST` | 배포 서버 IP 또는 도메인 | `123.456.789.0` |
| `DEPLOY_USER` | SSH 접속 사용자명 | `ubuntu` |
| `DEPLOY_KEY` | SSH 개인 키 (PEM 형식 전체) | `-----BEGIN RSA PRIVATE KEY-----...` |
| `SUPABASE_URL` | Supabase 프로젝트 URL | `https://xxx.supabase.co` |
| `SUPABASE_KEY` | Supabase anon 키 | `eyJ...` |

## SSH 키 생성 방법

```bash
ssh-keygen -t ed25519 -C "github-deploy" -f ~/.ssh/deploy_key
# 공개 키를 서버의 ~/.ssh/authorized_keys 에 추가
cat ~/.ssh/deploy_key.pub >> ~/.ssh/authorized_keys
# 개인 키 내용을 DEPLOY_KEY secret에 설정
cat ~/.ssh/deploy_key
```

## 배포 서버 초기 설정

```bash
# Docker 설치
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER

# 앱 디렉토리 생성
sudo mkdir -p /opt/stock-theme-app
sudo chown $USER:$USER /opt/stock-theme-app
```
