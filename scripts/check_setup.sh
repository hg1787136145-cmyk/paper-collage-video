#!/usr/bin/env bash
# paper-collage-video environment self-check.
# Exit 0 = all good; exit 1 = at least one item missing (details on stdout).

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOCAL_ENV="$SCRIPT_DIR/../.env.local"
GLOBAL_ENV="$HOME/.config/paper-collage-video.env"
REQUESTED_PROVIDER="${GBRO_VIDEO_PROVIDER:-}"
if [ -f "$LOCAL_ENV" ]; then
  set -a
  # shellcheck source=/dev/null
  . "$LOCAL_ENV"
  set +a
fi
if [ -f "$GLOBAL_ENV" ]; then
  set -a
  # shellcheck source=/dev/null
  . "$GLOBAL_ENV"
  set +a
fi
if [ -n "$REQUESTED_PROVIDER" ]; then
  GBRO_VIDEO_PROVIDER="$REQUESTED_PROVIDER"
fi

VENV_PY="$HOME/hyperframes-projects/.omni-venv/bin/python"
PROVIDER="${GBRO_VIDEO_PROVIDER:-yijia}"
FAIL=0

ok()   { printf 'PASS  %s\n' "$1"; }
bad()  { printf 'FAIL  %s\n' "$1"; FAIL=1; }
warn() { printf 'WARN  %s\n' "$1"; }

case "$PROVIDER" in
  yijia|gemini) ok "视频 provider: $PROVIDER" ;;
  *) bad "GBRO_VIDEO_PROVIDER 只能是 yijia 或 gemini，当前为：$PROVIDER" ;;
esac

# 1. provider API key
if [ "$PROVIDER" = "yijia" ]; then
  if [ -n "${YIJIA_API_KEY:-}" ]; then
    ok "YIJIA_API_KEY 已设置"
  else
    bad "YIJIA_API_KEY 未设置（一甲/Yijia API 密钥，写入环境变量即可，不要写进 skill 文件）"
  fi

  TOS_AK="${TOS_ACCESS_KEY_ID:-${TOS_ACCESS_KEY:-${VOLCENGINE_ACCESS_KEY_ID:-}}}"
  TOS_SK="${TOS_SECRET_ACCESS_KEY:-${TOS_SECRET_KEY:-${VOLCENGINE_SECRET_ACCESS_KEY:-}}}"
  TOS_REGION_OR_ENDPOINT="${TOS_REGION:-${TOS_ENDPOINT:-}}"

  if [ -n "$TOS_AK" ] && [ -n "$TOS_SK" ] && [ -n "${TOS_BUCKET:-}" ] && [ -n "$TOS_REGION_OR_ENDPOINT" ]; then
    if python3 - <<'PY' >/dev/null 2>&1
import tos
PY
    then
      ok "火山 TOS 素材上传配置已设置"
    else
      bad "已配置 TOS 环境变量，但 Python 包 tos 缺失（安装：python3 -m pip install --user tos）"
    fi
  elif [ -n "${YIJIA_PUBLIC_ASSET_ROOT:-}" ] && [ -n "${YIJIA_PUBLIC_ASSET_BASE_URL:-}" ]; then
    ok "Yijia 公网素材映射已设置"
  else
    warn "Yijia input_reference 需要公网 URL；建议配置火山 TOS 环境变量，或设置 YIJIA_PUBLIC_ASSET_ROOT 和 YIJIA_PUBLIC_ASSET_BASE_URL"
  fi
elif [ "$PROVIDER" = "gemini" ]; then
  if [ -n "${GEMINI_API_KEY:-}" ]; then
    ok "GEMINI_API_KEY 已设置"
  else
    bad "GEMINI_API_KEY 未设置（到 https://aistudio.google.com/apikey 创建后 export 到 shell 配置）"
  fi
fi

# 2. ffmpeg / ffprobe
if command -v ffmpeg >/dev/null 2>&1 && command -v ffprobe >/dev/null 2>&1; then
  ok "ffmpeg / ffprobe 可用"
else
  bad "ffmpeg / ffprobe 缺失（macOS: brew install ffmpeg；Debian/Ubuntu: sudo apt install ffmpeg）"
fi

# 3. Python version
if [ "$PROVIDER" = "yijia" ]; then
  PY_MIN='(3, 9)'
  PY_LABEL='python3 >= 3.9'
elif [ "$PROVIDER" = "gemini" ]; then
  PY_MIN='(3, 10)'
  PY_LABEL='python3 >= 3.10'
else
  PY_MIN=''
  PY_LABEL=''
fi

if [ -n "$PY_MIN" ]; then
  if command -v python3 >/dev/null 2>&1 && python3 -c "import sys; sys.exit(0 if sys.version_info >= $PY_MIN else 1)" 2>/dev/null; then
    ok "$PY_LABEL"
  else
    bad "python3 缺失或版本低于要求：$PY_LABEL"
  fi
fi

# 4. Gemini-only shared venv with google-genai >= 2.10.0
if [ "$PROVIDER" = "yijia" ]; then
  ok "$PROVIDER 链路使用 Python 标准库，无需 google-genai"
elif [ "$PROVIDER" = "gemini" ] && [ -x "$VENV_PY" ] && "$VENV_PY" - <<'PY' 2>/dev/null
import sys
from google import genai
parts = [int(x) for x in genai.__version__.split(".")[:2]]
sys.exit(0 if parts >= [2, 10] else 1)
PY
then
  ok "共享 venv 就绪（google-genai >= 2.10.0）"
elif [ "$PROVIDER" = "gemini" ]; then
  bad "共享 venv 未创建或 google-genai 版本过旧（创建：python3 -m venv ~/hyperframes-projects/.omni-venv && ~/hyperframes-projects/.omni-venv/bin/python -m pip install --upgrade 'google-genai>=2.10.0' 'httpx[socks]'）"
fi

exit $FAIL
