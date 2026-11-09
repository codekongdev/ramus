# @ramus/design-system

Ramus 디자인 시스템 키트(React 19 컴포넌트와 CSS)를 저장소에 그대로 들여온 워크스페이스 패키지다. 빌드 없이 `src/`를 Vite가 직접 읽는다.

## 구성

- `src/` : 컴포넌트(`RamusComponents`, `RamusPrimitives`, `RamusPatterns`, `RamusAdvanced`), 스타일(`ramus*.css`), 개발용 카탈로그(`RamusCatalog.tsx`, `catalog.css`).
- `src/styles.css` : 네 개의 `ramus*.css`를 순서대로 불러온다. 앱 진입점에서 한 번만 import한다.
- 내보내기: `.`(컴포넌트), `./styles.css`, `./catalog`(개발용 카탈로그, 운영 번들에 넣지 않는다).

## 외부에서 들여온 소스(vendored)

이 폴더의 소스는 사용자가 제공한 `Ramus-Design-System-v2` 키트에서 복사했다. 원본 공식 소스가 아닌 독립 재구성 키트다.

- 원본 문서는 이 폴더 루트에 그대로 있다: `KIT-README.md`(원본 README), `RAMUS-DESIGN-SYSTEM.md`, `COMPONENT-COVERAGE.md`, `ONBOARDING-FOUNDATIONS-v1.md`, `ramus.tokens.json`, `THIRD-PARTY-NOTICES.md`, `licenses/`.
- 영어 UI 문구와 기본 prop 값을 한국어로 바꾼 부분이 있다. 바뀐 곳은 모두 `CHANGES.md`에 적는다. 키트를 다시 들여올 때는 이 기록을 보고 같은 수정을 다시 적용한다.
- 원본의 `references/`(원 서비스 스크린샷 64개)는 개인정보가 남아 있을 수 있어 의도적으로 가져오지 않았다. `dist/`, 검증·인벤토리 JSON, 단독 HTML, 빌드 스크립트도 가져오지 않았다.

## 사용 규칙

기능 코드는 이 패키지를 직접 import하지 않는다. 항상 `apps/web/src/ui`(어댑터 계층)를 통해서만 가져온다. 키트 컴포넌트의 이름 변경, 한국어 기본값, 앞으로의 교체는 어댑터에서 처리한다.
