#!/bin/bash
# 원격 디버깅용 크롬 실행 스크립트
#
# 평소 쓰는 크롬 프로필 그대로 디버깅 포트를 열어, 이미 로그인된 세션에 붙는다.
#
# 사용법:  bash chrome-debug.sh
# 종료하려면 그냥 그 크롬 창을 닫으면 된다. (포트도 같이 내려간다)
#
# ── 여기까지 오게 된 경위 (같은 삽질 반복 방지용) ──────────────────
#
# 1차 시도: 프로필을 복사해 전용 디버그 프로필을 만듦 → 실패.
#   쿠키 파일(2,381개)은 멀쩡히 복사되는데 구글이 세션을 거부한다.
#   구글이 세션 쿠키를 기기·프로필에 묶어두기 때문에(DBSC), 디렉토리를
#   옮기면 바인딩이 깨져 서버가 강제 로그아웃시킨다.
#   → "복사했는데 왜 로그아웃이지"로 헷갈리기 딱 좋은 자리다.
#
# 2차 시도: 그 복사 프로필에서 손으로 로그인 → 실패.
#   "로그인할 수 없음 / 브라우저 또는 앱이 안전하지 않을 수 있습니다".
#   포트를 떼고 띄워도 막혔다.
#
# 결론: 구글이 막는 건 '로그인 행위'지 '이미 로그인된 세션'이 아니다.
#   그러니 로그인을 새로 하려 들지 말고, 이미 로그인돼 있는 원본 프로필을
#   그대로 쓴다. 로그인 단계 자체가 사라진다.
#
# ⚠️ 주의:
#   - 평소 크롬을 완전히 종료해야 한다 (같은 프로필 동시 사용 불가)
#   - 포트가 열려 있는 동안 실제 로그인 세션이 로컬 CDP에 노출된다.
#     작업이 끝나면 창을 닫아 포트를 내릴 것.
#   - Chrome 136+ 는 기본 프로필 디렉토리에 대한 --remote-debugging-port 를
#     거부할 수 있다. 그 경우 아래 안내가 뜬다.
# ─────────────────────────────────────────────────────────────

set -euo pipefail

PROFILE="$HOME/Library/Application Support/Google/Chrome"
PORT=9222
CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

# 포트가 이미 물려 있으면 그대로 쓴다
if curl -s -m 2 "http://127.0.0.1:$PORT/json/version" >/dev/null 2>&1; then
  echo "✅ 이미 $PORT 포트에 디버깅 크롬이 떠 있습니다. 그대로 사용합니다."
  exit 0
fi

# 실행 중인 크롬이 있으면 사용자가 직접 끄게 한다.
# (강제로 kill 하면 열어둔 탭과 작성 중이던 내용이 날아간다)
RUNNING=$(ps -eo pid,command \
  | grep "Google Chrome.app/Contents/MacOS/Google Chrome" \
  | grep -v grep | grep -v Helper \
  | awk '{print $1}' || true)

if [ -n "$RUNNING" ]; then
  echo "❌ 크롬이 실행 중입니다 (PID $(echo $RUNNING | tr '\n' ' '))"
  echo
  echo "   같은 프로필을 두 크롬이 동시에 열 수 없습니다."
  echo "   크롬을 ⌘Q 로 완전히 종료한 뒤 다시 실행해주세요."
  echo "   (탭이 날아가지 않도록 여기서 강제 종료하지 않습니다)"
  exit 1
fi

echo "🚀 크롬 실행 (평소 프로필 + 디버깅 포트 $PORT)"
"$CHROME" \
  --remote-debugging-port=$PORT \
  --user-data-dir="$PROFILE" \
  --no-default-browser-check \
  >/dev/null 2>&1 &

# 뜨는 데 시간이 걸리므로 최대 10초까지 기다린다
for _ in $(seq 10); do
  if curl -s -m 1 "http://127.0.0.1:$PORT/json/version" >/dev/null 2>&1; then
    echo "✅ 디버깅 포트 연결 확인됨 — 로그인 상태 그대로 붙습니다."
    exit 0
  fi
  sleep 1
done

echo "⚠️  포트가 열리지 않았습니다."
echo
echo "   크롬 창은 떴는데 포트만 없다면, Chrome 136+ 의 보안 정책에 걸린 것입니다."
echo "   (기본 프로필 디렉토리에는 원격 디버깅을 허용하지 않음)"
echo "   이 경우 브라우저 자동화 대신 Google Sheets API 로 우회해야 합니다."
