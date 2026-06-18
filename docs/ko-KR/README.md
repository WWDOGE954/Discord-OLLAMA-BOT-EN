# Discord OLLAMA Bot ko-KR

이 문서는 프로젝트의 한국어 보조 문서입니다.

이 프로젝트는 고등학교 시기에 제작한 Discord Bot을 정리하여 공개한 학습용 프로젝트입니다. Discord 서버 관리, 로컬 Ollama AI, 모더레이션 케이스 보고, 사용자 상호작용 요약, PC 상태 모니터링, 온도 보호, 개인 음악 라이브러리 기능을 포함합니다.

> **번역 안내**  
> 이 프로젝트는 실제 소스 코드와 영어 GitHub 주요 문서를 최종 기준으로 합니다. 한국어 문서는 AI 번역 또는 정리 도움을 포함할 수 있으며, 내용이 다를 경우 소스 코드를 우선으로 확인해 주세요.

## AI Provider and Privacy Notice

This project was originally designed to use local Ollama as the main AI provider.

When privacy is important, using a local AI model is recommended because prompts, moderation context, user interaction summaries, memory-related data, and logs can remain on the deployer's own machine.

If the deployer modifies this project to use a cloud AI API, prompts, user-related context, moderation records, or conversation data may be sent to a third-party provider.

If you choose to use a cloud AI API, you are responsible for reviewing the provider's privacy policy, data retention policy, terms of service, and any legal or compliance requirements.

For privacy-sensitive servers, school environments, or communities involving minors, local AI deployment is strongly recommended.


## 문서 바로가기

- [명령어 요약](./COMMANDS.md)
- [AI 및 관리 기능 설명](./AI_AND_MODERATION_NOTES.md)
- [docs 전체 안내로 돌아가기](../README.md)

## 프로젝트 목적

이 저장소는 주로 다음 목적을 위해 공개되었습니다.

- 학습 기록
- 포트폴리오
- 교육 및 수업 참고 자료
- Discord Bot과 로컬 AI 통합 예시

특별한 이유가 없다면 이 프로젝트는 앞으로 큰 업데이트를 받지 않을 가능성이 높습니다.

## 안전 안내

`.env`, Discord Bot Token, Webhook URL, API Key, 비밀번호, `data/`, `logs/`, AI 대화 기록, 사용자 정보, 모더레이션 케이스, 음악 파일을 공개하지 마세요.

token, API key, webhook, 비밀번호가 공개되었다면 즉시 폐기하거나 새로 생성하세요.

## 라이선스 안내

학습, 수업, 개인 연습, 교육 참고, 학술 참고 용도는 환영합니다. 상업적 사용, 무단 재배포, 개인 데이터 오용, 데이터 판매, 허가되지 않은 음악 또는 저작권 콘텐츠 사용은 금지됩니다.
