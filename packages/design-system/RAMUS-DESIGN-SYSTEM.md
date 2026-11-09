# Ramus 디자인 시스템 v2

온보딩에 한정됐던 v1을 앱 본체, 설정, 검색, 문서 목록, 자동화, 플레이북과 공개 UI 모듈 정의까지 확장했습니다. **원 서비스의 공식 라이브러리나 전체 제품 소스의 완전한 복제는 아닙니다.** 확인할 수 있는 시각·상태·컴포넌트 정의를 회수하고 독립 React 구현으로 재구성한 키트입니다.

관측일: 2026-11-09, Asia/Seoul.

## 1. 무엇이 달라졌나

- 원본 레퍼런스 **64개**: 기존 온보딩 16 + 앱 본체 추가 48.
- 실제 UI: 아바타, 프로필, 사용자 메뉴, 검색형 Select, 다중 선택, Switch, Radio 메뉴, 표, 툴바, 멘션, 아이콘·이모지 picker, 달력, 날짜·시간, Tooltip, 상태 편집, 파괴적 확인, 알림, 모바일 내비게이션.
- 공개 JS 22개에서 최초 30개 그룹의 실제 렌더·props·class 정의 확인. 추가 4개 명시 URL을 조사해 EntityMenu·StructuredCard 계열 및 누락 조합을 보완했습니다.
- 고유 기초/역할 CSS 변수 293개. 그룹별 선언 407개이며 테마 중복을 포함합니다.
- 기존 9개 값 export + Primitive 19개 + Pattern 29개. Pattern에는 `COMPOSER_FORMATS` 상수와 표의 구조용 서브 export가 포함돼 있으므로 “컴포넌트 57종”이라고 합산하지 않습니다.
- 추가 Advanced 모듈은 아래 별도 장을 참고하세요.

## 2. 결과물과 시작점

|파일|역할|
|---|---|
|`Ramus-Design-System.html`|실제 제공 React 컴포넌트로 구동하는 단일 파일 카탈로그|
|`RamusCatalog.tsx`, `catalog.css`|카탈로그의 편집 가능한 소스|
|`RamusComponents.tsx`, `ramus.css`|v1 기본 폼·온보딩·모달과 전체 토큰|
|`RamusPrimitives.tsx`, `ramus-primitives.css`|아바타·입력·선택·메뉴·오버레이 등 기본 UI|
|`RamusPatterns.tsx`, `ramus-patterns.css`|다중 선택·달력·표·명령 검색·편집기 등|
|`RamusAdvanced.tsx`, `ramus-advanced.css`|추가 공유 UI와 회수한 조합|
|`COMPONENT-COVERAGE.md`, `components.inventory.json`|그룹별 원 출처·관측·대응 API·부분 구현·미지원 상태|
|`references/index.html`|원본 64개 캡처의 검색형 모음|
|`references/screenshots/`|조사 중 저장한 원본 이미지|
|`references/evidence/`|원 정의·CSS 근거·실측·AX·정리 결과|
|`ramus.tokens.json`|선언·조건·fallback·테마 원값|
|`ONBOARDING-FOUNDATIONS-v1.md`|색상·타이포·곡률·간격·그림자·모션의 상세 원값|
|`Onboarding-Reference.html`|기존 온보딩 중심 카탈로그 보존본|
|`verification.json`|이번 최종 타입·브라우저·파일 검증 결과|
|`licenses/`|내장 폰트와 React 런타임의 라이선스|

카탈로그는 서버 없이 실행됩니다. 원본 이미지 모음은 상대 경로를 사용하므로 ZIP 전체를 풀고 폴더 구조를 유지해야 합니다.

## 3. 근거 수준을 나눠 읽기

|구분|무엇을 확인했나|무엇을 뜻하지 않나|
|---|---|---|
|UI + 정적 정의|실제 화면의 상태와 공개 모듈 렌더/스타일|모든 옵션·브라우저·상태를 전부 테스트했다는 뜻 아님|
|정적 정의만|실제 props/렌더/class 또는 CSS selector|현재 계정 화면에서 노출됐다는 뜻 아님|
|권장 조합|원 화면 패턴을 재사용 가능한 컴포넌트로 새 구성|원 서비스의 공식 API나 정확한 구현이라는 뜻 아님|
|검증 완료|이 키트의 타입 및 명시한 로컬 동작 확인|원 서비스의 backend, 보안, 결제, 인증 검증 아님|

같은 패밀리에서도 일부 상태만 실제 UI에서 확인했습니다. 예를 들어 Badge의 모든 variant, Checkbox, Skeleton, OTP, HoverCard 등은 원 정의와 화면 관측 범위를 별도로 읽어야 합니다. Source-only를 UI 확인으로 승격하지 않았습니다.

## 4. 실제 화면 조사 지도

- 채팅: primary rail, sidebar, breadcrumb, message, answer card, composer, formatting, link, mention, emoji, conversation actions.
- 사용자: 28px 메뉴 아바타와 8px presence, 80px 프로필 이미지, 상세 카드, 편집 폼, textarea, 시간대 검색 Select, status dialog.
- 전역 검색: 명령형 검색, 그룹·옵션, 사람 필터, Type 복수 선택, 선택 칩·제거·전체 해제, 정렬.
- 설정: 테마 Select, 3가지 Switch 정의, 실제 on/off, 설정 행, 사용자 표, 그룹 표, Radio 메뉴, 사용량 요약, 기간 Select, 네이티브 날짜 범위.
- 문서·표: 브라우저, type tabs, empty view, 실제 AG Grid 목록.
- 자동화: empty, 생성 선택 UI, 임시 미발행 draft, instructions toolbar, resizable side panel, trigger Select, date/time, month picker, time options, destructive AlertDialog.
- 앱·플레이북: 목록 빈 상태, 카드, 아이콘 묶음, 상세 설정 폼, 예시 iframe.
- 모바일: sidebar 열린 상태와 닫힌 본문, conversation dropdown.

원본 계정 정보나 사적인 문서를 카탈로그 샘플 데이터로 사용하지 않았습니다. 원본 스크린샷에는 표시명·메일이 남아 있을 수 있으므로 개인 참조용으로 다루고 외부 공유 전에 가림 처리를 권장합니다.

## 5. 핵심 컴포넌트 규칙

### Avatar

정적 렌더의 표준 size는 xs 16 / sm 20 / md 24 / lg 32 / xl 48px입니다. 기본 모서리는 `37.5%`입니다. 이미지, 이니셜 fallback, optional online presence가 확인됐습니다. 메뉴의 28px와 프로필의 80px는 화면별 크기 조합이며 표준 5단계와 같은 목록으로 합치지 않습니다. 다른 상태색이나 스택형 AvatarGroup 전체를 원 정의라고 추정하지 않습니다.

### Button

확인한 variants: default, destructive, outline, secondary, ghost, link, text.

확인한 sizes: default, xs, sm, lg, icon, icon-sm, icon-lg. **7개**입니다. 온보딩 CTA 44px와 같은 화면별 override는 별도로 존재합니다. 불확실한 8번째 size를 만들지 않았습니다.

### Switch와 Checkbox

Switch 원 정의는 md/sm/xs, 실제 기본 스위치는 36×20px와 14px thumb였습니다. 작은 변형은 정적 정의에 근거합니다. Checkbox는 16px·radius-xs·mixed 렌더 정의를 확인했으며 실제 원본 화면에서의 독립 노출은 미확인입니다. 키트는 네이티브 input으로 indeterminate를 구현했습니다.

### Select와 MultiSelect

- 단일 Select와 검색형 timezone picker를 직접 확인했습니다.
- Type 필터는 Doc·Table을 동시에 유지했습니다. selected 배열, chip remove, clear를 재구성했습니다.
- From 필터의 @me/Ramus는 이 조사에서 서로 대체됐습니다. ARIA multi flag만으로 모든 필터가 동일한 다중 동작이라고 일반화하지 않습니다.
- 키트 검색은 전달받은 로컬 배열만 사용합니다. 사람·문서 API 검색을 하지 않습니다.
- 원 Select/Command/Menu의 세부 서브 API 전체를 동일한 headless 엔진으로 재현한 것은 아닙니다.

### Menu·Popover·Tooltip·HoverCard

Desktop 메뉴의 28px 행, 12px item radius, 16px menu surface radius를 실측했습니다. Popover 20px, Tooltip의 border/작은 타이포도 출처 정의와 대조했습니다.

Tooltip은 실제 `data-slot="tooltip-content"` 렌더를 확인했습니다. 원본의 해당 캡처에서 role=tooltip selector는 발견되지 않았으며, 키트의 ARIA 처리는 접근성 재구성입니다.

Popover/Menu는 로컬 배치입니다. Portal, 완전한 collision engine, 모든 scroll container 대응은 포함하지 않습니다. Nonmodal Popover와 modal Dialog를 혼동하지 않습니다. HoverCard는 정적 정의 확인 수준입니다.

### Calendar·DateTime

실제 날짜 picker에서 7열 그리드, 32px 원형 day button, 오늘/선택 상태, 월 이동을 확인했습니다. 시간 목록은 실제 화면과 AX 트리의 96개 옵션을 확인했으나 해당 시간 popup의 DOM 실측 노드는 0이었습니다. 그 값을 임의 보충해 실측이라고 부르지 않습니다.

사용량 범위의 `input type=date`는 네이티브 브라우저 입력입니다. Ramus의 별도 날짜 popup과 다릅니다. 기존 DateTimeEditor는 로컬 날짜 문자열과 native time input을 사용하며 timezone 변환·모든 반복 예약 규칙·원본 시간 목록 엔진은 재현하지 않습니다.

### Table·Grid

Native Members table, Groups 1행, AG Grid 문서 목록을 실제 관측했습니다. Table의 8개 구조용 export와 DataGridLite는 다른 수준의 API입니다. DataGridLite는 정렬·문자열 필터·행 선택·sticky header·empty/loading 기본 조합이며, AG Grid의 가상화·셀 편집·열 리사이즈·고급 필터·내보내기 전체 구현이 아닙니다.

### Editor·OTP

ComposerToolbar는 실제 10개 formatting action과 link/mention/symbol picker 패턴에 근거합니다. 서식 상태를 시연하지만 실제 ProseMirror/Tiptap 편집 변환 엔진을 제공하지 않습니다.

InputOTP는 정적 slot/group 정의를 참고한 숫자 입력 UI입니다. 코드 발급, 검증, 문자 메시지, 인증 서비스는 전혀 연결하지 않았습니다. 샘플에 실제 OTP를 입력하지 마세요.

## 6. 추가 회수 UI

`RamusAdvanced.tsx`는 16개 값 export를 추가합니다.

- StructuredCard, OptionRow, OptionGroup, Hint, CardFooter, ActionRow.
- ContextMenu, ActionSheet. 두 계열은 source-only이며 원본의 모바일 Dropdown과 구분합니다.
- IconColorPicker, SymbolPicker. 원본 registry는 포함하지 않고 caller-supplied 데이터만 사용합니다.
- AlertDialog, StatusDialog. native modal·비동기 callback 보호·포커스 관리는 독립 재구성입니다.
- Toast, Toaster. 실제 커스텀 카드 실측과 독립 local 알림 동작을 구분합니다.
- FileDropzone, Disclosure. 원본 시각 어휘를 활용한 권장 조합이며 정확한 원본 컴포넌트 회수로 세지 않습니다.

현재 값 export는 73개(9+19+29+16)이며 상수 1개와 구조용 wrapper를 포함합니다. 카탈로그는 9개 컴포넌트 섹션의 49개 샘플 카드입니다. 준비된 ESM과 타입 선언은 `dist/`, 합친 스타일은 `dist/ramus-all.css`에 있습니다. Select 타입 별칭은 `SingleSelectOption` / `MultiSelectOption`입니다.

원 모듈 정의와 재사용을 위한 새 API는 구분합니다. EntityMenu의 모바일 long-press·전체 sub-view 전환, 원 source의 도메인 request 승인·실행, import conversion, 계정 status 저장, custom emoji 업로드는 구현 범위가 아닙니다.

Toast는 실제 표시된 다운로드 안내의 visual group을 추가 실측했습니다. radius16 / padding16 / gap12 / width356px이며 이는 package 기본 Sonner font13/gap6 recipe와 다릅니다. 단일 행 메시지는 콘텐츠에 따라 높이가 달라집니다.

## 7. 테마와 토큰

원 root는 Dark, 온보딩은 부분 Light scope였고 전체 앱 검색 모달은 Dark였습니다. 키트 Onboarding은 독립 사용을 위해 전체 Light 기반으로 정규화했습니다. source override 원문은 JSON에 남겼습니다.

- Primary는 고정 파란색이 아닙니다. Light에서 oat-700, Dark에서 흰색.
- 실제 body는 Inter 우선이지만 원 `--font-sans`는 시스템 스택입니다.
- UI / msg / doc / static typography를 분리했습니다.
- scoped theme의 alias는 로컬에서 재바인딩했습니다.
- 원 보조 글자 일부의 대비는 작은 본문 4.5:1에 못 미쳤습니다. 원본 값을 보존하고 `contrast="enhanced"`를 권장 opt-in으로 제공합니다.
- 추가 root 계산값 5개 중 4개는 ScrollArea overflow 상태, 하나는 voice wash입니다. 이를 새 색상/spacing 디자인 토큰 수로 무조건 합산하지 않았습니다.

색상·타이포·elevation 전체 원값과 계산 방법은 `ONBOARDING-FOUNDATIONS-v1.md` 및 `ramus.tokens.json`을 참고하세요.

## 8. 적용

```tsx
import './ramus.css';
import './ramus-primitives.css';
import './ramus-patterns.css';
import './ramus-advanced.css';
import { RamusProvider } from './RamusComponents';
import { Avatar, Select, Switch } from './RamusPrimitives';
import { MultiSelect, Calendar } from './RamusPatterns';

<RamusProvider theme="dark" contrast="enhanced">
  {/* Controlled props와 callbacks는 각 파일의 타입 정의 참고 */}
</RamusProvider>
```

React와 ReactDOM은 사용자 프로젝트의 의존성을 사용합니다. 키트 라이브러리는 계정 API·네트워크·스토리지·원 서비스 연결 코드를 포함하지 않습니다. 카탈로그 HTML에는 실제 제공 모듈과 React 런타임을 내장했습니다.

모든 option/item은 고유하고 안정적인 value/id를 사용하세요. Focusable trigger에는 접근 가능한 이름이 필요합니다. 중첩 테마 경계는 `.ramus` scope와 contrast opt-in을 다시 지정해야 할 수 있습니다. 팝업이 overflow ancestor에 의해 잘릴 수 있는 제약을 확인하세요.

## 9. 원본과 같지 않은 부분

- 독립 Light 기반 Onboarding, alias 재바인딩.
- 재작성한 React API와 h-/hp-/hx-/ha- namespace.
- 키보드·focus restoration·native semantics·reduced motion 등 접근성 보완.
- 새 로컬 state와 fixture. 실제 사용자·문서·연결 데이터 미사용.
- Native dialog 기반 modal. 원 Base UI portal/collision engine 전체 미복제.
- DataGridLite와 ComposerToolbar는 원 도구의 시각/상태 패턴만 참고.
- Native date/time 입력과 로컬 날짜 선택. 반복 일정·timezone·서버 스케줄러 미포함.
- 원 브랜드/앱 로고와 static 제품 배경은 키트 UI에 재배포하지 않음.
- 공개 JS 원 파일 전체를 재배포하지 않고 짧은 UI 근거와 독립 구현만 제공.

## 10. 탐색 중 외부 상태와 정리

스케줄 UI를 여는 과정에서 미발행 자동화 draft 1개가 생성됐습니다. 날짜/시각 상태를 조사한 뒤 **그 draft만 삭제**했고 “Draft deleted” 알림과 빈 목록을 확인했습니다. 발행·실행은 하지 않았습니다.

메시지 입력의 임시 @ 문자는 지웠고 메시지를 보내지 않았습니다. 프로필·상태·설정을 저장하지 않았고, 계정 연결·초대·결제도 실행하지 않았습니다. 마지막에는 원 채팅 URL, 빈 composer, 열린 sidebar, 1265×873 viewport로 복구했습니다.

## 11. 검증

- TypeScript 7.0.2 strict: 4개 라이브러리 모듈, 카탈로그, barrel entry 모두 통과.
- React/ReactDOM 19.3.1 StrictMode 실제 브라우저: runtime/console error 0.
- ESM JS + 타입 선언 + CSS 빌드 16파일 생성.
- 49개 카드 렌더 확인. Light 1440 / 1024 / 768 / 390px에서 가로 넘침 0. Dark 390px 추가 확인.
- 기본 검사: mixed checkbox, switch/radio, 검색 Select, MultiSelect 추가·제거·해제·복원, 메뉴 checkbox/radio/submenu/Escape, Tooltip focus, Popover, Calendar month, OTP 숫자 입력, grid 필터·empty, 명령 검색.
- 추가 검사: ContextMenu Shift+F10·선택·초점 복귀, ActionSheet 열기·취소, 아이콘 검색·색상·선택, 심볼 빈 검색·Escape, 로컬 AlertDialog 확인, StatusDialog 문구·만료·저장, 지속 토스트·전체 해제, 가상 파일 선택 fixture, Disclosure 닫기.
- SearchCommand가 최초 렌더에서 페이지를 자동 스크롤하던 재구성 버그를 수정했습니다.
- 파일 선택창·실제 업로드, 모든 비동기 실패 경로, source-only 상태 전부, 모든 기기/브라우저는 테스트하지 않았습니다.

기계가 읽을 수 있는 최종 결과는 `verification.json`을 참고하세요.

이 검증은 원 서비스의 전체 기능 테스트나 WCAG 인증, 모든 모바일 기기·IME·스크린리더·브라우저 호환성 보증이 아닙니다. 공개 정의만 있는 상태와 실제로 사용한 상태를 따로 유지했습니다.

## 12. 범위의 정확한 마감

현재 계정에서 접근해 확인한 화면, 그 화면의 실측·캡처, 실제 선언된 공개 UI asset graph에서 확인한 렌더/props/style을 대상으로 가능한 항목을 확장했습니다. 모든 다른 권한·유료 기능·미방문 경로·미사용 동적 chunk와 서버 상태까지 망라했다는 보장은 하지 않습니다.

토큰 개수, export 개수, 원 정의 그룹 수, 화면 상태 수를 서로 바꾸어 “전체 컴포넌트 개수”라고 표현하지 않습니다. 상세 지원 여부는 coverage 문서와 각 소스의 주석을 기준으로 확인하세요.
