# 명령어 요약

이 문서는 각 언어용 간단한 명령어 소개입니다. 전체 명령어와 실제 동작은 기본 문서 `docs/COMMANDS.md`와 실제 코드를 우선으로 확인해 주세요.

## 일반 사용자 명령어

- `/status`: Bot의 기본 상태를 확인합니다.
- `/ai`: 로컬 Ollama AI에 질문을 보냅니다.
- `@bot 메시지`: 멘션으로 Bot에게 답변을 요청합니다.
- `/my_warnings`: 자신의 경고 기록을 확인합니다.
- `/my_profile`: 자신의 상호작용 요약 또는 기본 profile을 확인합니다.

## 관리 및 모더레이션

- `/warn`: 사용자에게 경고 기록을 추가합니다.
- `/anger`: 사용자의 현재 분노 값 상태를 확인합니다.
- `/calm`: 사용자의 분노 값을 낮추거나 초기화합니다.
- `/punish`: 관리자의 판단에 따라 처리 작업을 실행합니다.
- `/mod_suggest`: 관리 판단을 돕기 위한 제안을 생성합니다.
- `/remove_warning`: 특정 경고 기록을 제거합니다.

## 규칙 및 안전 문구

- `/banword_add`: 금지어를 추가합니다.
- `/banword_remove`: 금지어를 제거합니다.
- `/banword_list`: 금지어 목록을 확인합니다.
- `/safe_add`: 안전 문구 또는 허용 표현을 추가합니다.
- `/safe_remove`: 안전 문구를 제거합니다.
- `/safe_list`: 안전 문구 목록을 확인합니다.

## 케이스 및 자동 관리

- `/case_ignore`: 지정한 케이스를 무시합니다.
- `/case_resolve`: 케이스를 처리 완료로 표시합니다.
- `/auto_mod`: 자동 모더레이션 기능을 전환하거나 설정합니다.
- `/auto_mod_status`: 자동 모더레이션 상태를 확인합니다.

## 시스템 및 PC 상태

- `/pc_status`: CPU, RAM, 디스크, 네트워크, GPU 상태를 확인합니다.
- `/pc_monitor_start`: 상태 모니터링을 시작합니다.
- `/pc_monitor_stop`: 상태 모니터링을 중지합니다.
- `/pc_action`: 사전 정의된 시스템 작업을 실행합니다.
- `/bot_mode`: normal, eco, emergency 등의 Bot 모드를 전환합니다.
- `/bot_mode_status`: 현재 Bot 모드를 확인합니다.
- `/bot_guard_set`: 온도 보호 또는 안전 모드 관련 설정을 지정합니다.

## 음악 기능

- `/music_add`: 음악 파일 또는 음악 항목을 추가합니다.
- `/music_list`: 음악 라이브러리를 확인합니다.
- `/music_remove`: 음악 항목을 제거합니다.
- `/go_music`: 음성 채널에 참가하고 재생을 시작합니다.
- `/music_queue`: 재생 대기열을 확인합니다.
- `/music_now`: 현재 재생 중인 항목을 확인합니다.
- `/music_pause`: 일시 정지합니다.
- `/music_resume`: 재생을 재개합니다.
- `/music_skip`: 현재 항목을 건너뜁니다.
- `/music_stop`: 재생을 중지하고 대기열을 비웁니다.
- `/music_volume`: 볼륨을 조정합니다.
- `/music_loop`: 반복 재생을 전환합니다.

## 사용 안내

일부 명령어는 관리자 역할, 지정 채널 또는 Discord Bot 권한이 필요합니다. 실제 사용 가능 여부는 `.env` 설정, 서버 권한, Discord Developer Portal 설정에 따라 달라질 수 있습니다.
