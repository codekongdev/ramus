# Ramus 디자인 시스템 v2

온보딩에 한정됐던 v1을 앱 본체와 실제 공개 UI 정의까지 확장한 독립 reference kit입니다. 원 서비스의 공식 소스나 모든 제품 기능의 완전 복제가 아닙니다.

## 먼저 열기

- `Ramus-Design-System.html`: 실제 제공 React 모듈로 구동하는 인터랙티브 카탈로그. 서버 불필요.
- `RAMUS-DESIGN-SYSTEM.md`: 전체 가이드와 구현 차이.
- `COMPONENT-COVERAGE.md`: 원 정의별 실제 관측·source-only·부분 지원·미지원·대응 API.
- `references/index.html`: 원본 스크린샷 **64개** 검색형 모음. ZIP 전체를 풀어 폴더 구조 유지.
- `Onboarding-Reference.html`, `ONBOARDING-FOUNDATIONS-v1.md`: v1의 상세 토큰/온보딩 규칙 보존.

## 들어 있는 컴포넌트

- 아바타: 이미지·이니셜·5개 크기·온라인 상태, UserChip/PrincipalCell.
- 입력: 7종 Button variant/7 sizes, Input/Label/Textarea, mixed Checkbox, 3 sizes Switch, Radio.
- 선택: 검색형 Select, MultiSelect·선택 칩·제거·clear, DropdownMenu·checkbox·radio·submenu, Chip.
- 오버레이: Tooltip, Popover, HoverCard, modal/AlertDialog, ContextMenu, ActionSheet, StatusDialog.
- 탐색: Tabs, SearchCommand, Breadcrumbs, ScrollArea, Separator, ResizablePanels.
- 날짜: Calendar, DateTimeEditor. 시간은 로컬 native input이며 원 일정 엔진 전체 구현 아님.
- 내용: Table 8개 구조용 export, DataGridLite 기본 정렬·필터·선택·empty/loading, Toolbar, ComposerToolbar, MessageCard, FileCard.
- 추가: StructuredCard/OptionRow/Group/Hint/Footer/ActionRow, IconColorPicker, SymbolPicker, Toast/Toaster, FileDropzone, Disclosure.
- 상태: Badge 8 variants, Alert, Skeleton, Spinner, 숫자 InputOTP UI.

원 화면 패턴을 새로 구성한 권장 조합과 정적 정의만 확인한 항목은 카탈로그/coverage에 표시합니다. export 개수에는 상수와 구조용 하위 wrapper가 포함되므로 전체 컴포넌트 종수와 혼동하지 않습니다.

## 소스로 바로 사용

```tsx
import "./ramus.css";
import "./ramus-primitives.css";
import "./ramus-patterns.css";
import "./ramus-advanced.css";
import { RamusProvider, Avatar, MultiSelect } from "./index";
```

제어형 props와 callbacks는 각 `.tsx`의 타입 정의 또는 카탈로그 API 예시를 참고하세요. API는 원본 Ramus의 공식 export가 아니라 독립 재작성입니다.

## 빌드된 ESM 사용

`dist/`에 ESM JS, 타입 선언, 4개 style 모듈과 `ramus-all.css`를 제공합니다. React/ReactDOM은 외부 peer dependency이며 19.3.1에서 검증했습니다.

```tsx
import "./dist/ramus-all.css";
import { RamusProvider, Avatar, MultiSelect } from "./dist/index.js";
```

- 브라우저용 번들러의 CSS 처리가 필요합니다. CSS를 import하는 ESM을 plain Node에서 직접 실행하는 배포가 아닙니다.
- Select 타입은 `SingleSelectOption` / `MultiSelectOption`으로 구분합니다. 원 module의 local 타입은 별도 파일에도 있습니다.
- 소스를 바꾼 뒤 `npm install`, `npm run typecheck`, `npm run build`로 다시 생성할 수 있습니다. 자동 게시하지 않는 private 패키지입니다.

## 검증과 한계

- TypeScript 7.0.2 strict 검사, 실제 React 19.3.1 StrictMode 브라우저 실행. 상세 결과는 `verification.json`.
- 원본과 별개로 로컬 demo의 검색·복수 선택·메뉴·폼·달력·표·모달 등 상호작용을 검사했습니다.
- 일부 source-only variants, 인증, 실제 업로드·저장, OAuth, grid/editor 고급 기능, 모든 브라우저/스크린리더는 검증 대상이 아닙니다.
- OTP는 숫자 입력 UI만 있고 코드 발급/검증은 없습니다. 실제 OTP를 입력하지 마세요.
- SymbolPicker는 caller-supplied 데이터만 사용하며 원 이모지 데이터베이스·로고·아이콘 registry를 대량 복제하지 않습니다.
- Popover는 local placement라 overflow clipping 가능. Portal·완전한 collision engine·long-press·모든 subview를 복제하지 않습니다.
- 원본 보조 글자 일부 대비는 부족할 수 있어 원값과 enhanced opt-in을 분리했습니다. 전체 WCAG 감사가 아닙니다.

## 원본 화면과 개인정보

64개 원본 캡처에는 계정 표시명·메일이 남아 있을 수 있습니다. 개인용 참조 자료이며 외부 공유 전 가림을 권장합니다. 카탈로그 fixture에는 실제 사용자 정보를 사용하지 않았습니다.

스케줄 UI 조사 중 만들어진 미발행 초안 1개는 삭제 완료했습니다. 발행/실행, 설정 저장, 메시지 전송, 초대, 계정 연결, 결제는 하지 않았습니다. 원 채팅 화면과 viewport/sidebar를 복구했습니다.

출처: https://app.hops.ai · 2026-11-09 관측. 폰트/React notices는 `THIRD-PARTY-NOTICES.md` 및 `licenses/` 참고.


## 이름 변경 안내

폴더·파일·React API·CSS scope·카탈로그 브랜드를 Ramus로 변경했습니다. 원본 출처 URL, 라이선스, 원본 스크린샷 및 references/evidence의 관측 기록은 보존했습니다. 원본 제품명을 Ramus라고 주장하는 변경이 아닙니다.
