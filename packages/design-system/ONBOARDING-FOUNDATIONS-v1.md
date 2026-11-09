# Ramus 디자인 시스템

실제 웹 UI와 로드된 CSS를 바탕으로 만든 상세 관측 명세 + 재사용 구현 키트입니다. **원 서비스의 공식 디자인 시스템이나 원본 소스 코드가 아닙니다.**

- 관측일: 2026-11-09, Asia/Seoul
- 출처: [Ramus 온보딩](https://app.hops.ai/onboarding)
- 관측 환경: Desktop 1265 × 873, Mobile 390 × 844, DPR 2, root font-size 16px
- 고유 CSS 변수 이름: **293개**
- 그룹별 선언: foundation 193 / light 100 / dark 86 / onboarding override 28 = 407개. 테마 중복을 포함하므로 고유 개수와 다릅니다.
- 시각 카탈로그: `Ramus-Design-System.html`
- 개발 자산: `ramus.css`, `RamusComponents.tsx`, `ramus.tokens.json`
- 관측 근거: `ramus.evidence.json`

## 1. 근거를 읽는 방법

|표시|뜻|사용 원칙|
|---|---|---|
|실측|관측한 실제 요소의 computed style·치수·DOM 의미|해당 화면·뷰포트·상태에 한정|
|CSS 확인|로드된 CSS에 선언된 원값|제품 전체에서 실제 사용 중이라고 단정하지 않음|
|계산|rem 환산, 행간, sRGB 대비 등|계산 방법과 가정 함께 유지|
|재구성|관측한 규칙으로 새로 작성한 CSS·React·데모|원본 구현과 동일하다는 뜻이 아님|
|권장 확장|대비 강화, 큰 터치 영역, 추가 포커스 처리 등|원본에서 확인한 기능으로 표시하지 않음|

이 문서의 숫자는 모두 CSS pixel 기준입니다. DPR 2의 스크린샷 이미지 픽셀과 혼동하지 않습니다. viewport를 바꾼 직후의 애니메이션 중간값은 확정 수치로 사용하지 않았습니다.

### 확인한 화면과 상태

- 1단계: 최초 상태, 미선택 오류, business/team/personal 분기, Something else 자유 입력, 빈 입력 오류.
- 개인용 3단계 흐름과 업무용 4단계 흐름.
- 이메일 연결: Gmail/Outlook 전환, 건너뛰기 안내, 일시적인 전환 중 disabled 상태.
- 앱 추천: 개인 및 Product/eng 팀 추천, Browse all apps.
- 전체 앱 모달: 검색, 검색 지우기, Design 카테고리, 검색 결과 없음, 모바일 모양.
- 직함 자동완성: engineer 입력, 5개 추천 옵션, ArrowDown 선택, Escape 닫기.
- 팀 초대: 이메일 입력 3개, Add another로 4번째 필드 생성.
- Desktop·Mobile 레이아웃과 footer 처리.

### 실행하지 않은 것

외부 계정 인증·연결, 유효한 이메일 입력 및 초대 전송, 최종 온보딩 완료, 요금·결제 변경, 앱 본체의 데이터 생성은 실행하지 않았습니다. 관측 후 새로고침으로 최초 1단계 미선택 화면을 복구했습니다. 세션 내 UI 선택을 탐색한 것이며, 모든 서버 저장소의 무변경까지 감사한 것은 아닙니다.

## 2. 디자인 언어 요약

아래는 화면을 읽어 도출한 해석이며, Ramus가 발표한 브랜드 철학은 아닙니다.

1. **따뜻한 무채색 중심.** Oat 팔레트가 배경, 글자, 경계, 버튼의 중심입니다. 파랑은 primary 브랜드색이 아니라 링크·포커스 등에 분리되어 있습니다.
2. **넉넉한 큰 구조, 조밀한 내부 도구.** 온보딩 CTA는 44px지만 앱 카드의 Connect는 24px입니다.
3. **둥근 모서리의 위계.** shell 28px, 앱 카드 20px, context 입력 16px, 일반 필드·CTA 12px, 선택 칩은 pill입니다.
4. **얇은 경계와 낮은 대비의 표면.** 표면 차이와 hairline으로 구분하고, 큰 shell·모달에만 강한 elevation을 사용합니다.
5. **짧은 대화체.** “Hi, I'm Ramus.”처럼 1인칭으로 말하고 사용자의 결과를 먼저 설명합니다.
6. **점진적 정보 수집.** 선택에 따라 필요한 필드만 추가하고, 전체 단계 수를 바꿉니다.
7. **연결과 초대를 중심으로 한 온보딩.** 크레딧 안내는 보조 유채색으로 분리되지만, 실제 혜택이나 정책의 유효성은 이 분석에서 검증하지 않았습니다.

## 3. 가장 중요한 테마 구조

관측 시 `html`은 `dark`였고 body는 어두웠습니다. 하지만 실제 온보딩은 `.onboarding-light-scope`가 `color-scheme: light`와 흰 배경·짙은 글자 등을 부분 재정의합니다.

```text
html.dark / body
  ├─ onboarding-light-scope: 부분 light override
  │    └─ 온보딩 shell, 선택, 입력, CTA
  └─ Connect app 모달: 관측한 computed style은 dark
```

이 도식은 관측한 상속 결과를 설명합니다. 사용한 프레임워크의 portal 구현 방식까지 확정한 것은 아닙니다.

- root Dark 배경: oat-900과 oat-950의 srgb 50:50 혼합.
- root Dark 전경: oat-300.
- 온보딩 배경·card: 흰색.
- 온보딩 전경: oat-950.
- Light/온보딩 primary: oat-700, 글자 흰색.
- Dark primary: 흰색, 글자 oat-950.
- 온보딩 border/input: oat-300.
- 일반 Light border는 oat-200과 oat-300의 혼합이므로 온보딩과 다릅니다.

**키트의 의도적인 차이:** 독립적으로 재사용하기 쉽도록 `data-theme="onboarding"`은 완전한 Light 정의 위에 온보딩 override를 쌓습니다. 원본처럼 Dark에서 미재정의 토큰을 이어받는 부분 테마와 완전히 같지는 않습니다. 원본 정의는 JSON `definitions.onboarding`, selector·fallback·조건은 `sourceRules`에 보존했습니다.

## 4. 온보딩 레이아웃 명세

### Desktop: md 이상

|영역|관측값/규칙|
|---|---|
|바깥 stage|중앙 정렬, padding 32px|
|shell|max-width 42rem = 672px, radius 28px|
|shell max-height|`calc(100dvh - 4rem)`|
|shell overflow|hidden, 내부 본문 스크롤|
|header|좌우 40px, 위 32px, gap 16px|
|body|위 36px, 좌우 40px, 아래 32px|
|실제 콘텐츠 폭|1265px viewport에서 592px|
|footer|위·아래 16px, 좌우 40px, 상단 border|
|footer 위치|static|
|footer 내부 행|최소 높이 44px, gap 16px|
|footer 실제 높이|일반 상태에서 76.5px: padding + CTA + .5px border|

Shell shadow:

```css
box-shadow:
  0 2px 8px -2px rgb(0 0 0 / .08),
  0 32px 64px -24px rgb(0 0 0 / .28);
```

관측한 앱 추천 화면의 shell 높이는 약 616.8px였습니다. 높이는 콘텐츠와 상태에 따라 변하므로 고정 height로 제품 규칙에 넣지 않습니다.

### Desktop 장식 배경

원본 desktop 뒤에 보이는 제품 화면은 실제 앱 본체 탐색 결과가 아니라 `/assets/product-backdrop-OO4HAKvN.webp` 정적 이미지입니다. `aria-hidden`, pointer-events none인 고정 배경 위에 black 20% 레이어와 backdrop-filter blur(4px)를 적용합니다. md 미만에서는 제품 배경을 숨기고 배경색으로 대체합니다. 따라서 이 장식 이미지에서 앱 기능이나 인증된 사용자 상태를 추론하지 않습니다. 키트는 이 원본 이미지 배경을 복제하지 않고 단색 stage를 사용합니다.

### Mobile 및 sm 구간

|구간|규칙|
|---|---|
|640px 미만|온보딩 전체 화면, 콘텐츠 좌우 24px, 제목 28px, 앱 1열|
|640px 이상|콘텐츠 좌우 40px, 제목 32px, 앱 2열|
|768px 미만|shell의 desktop 카드 모서리·그림자 적용 안 됨, footer sticky|
|768px 이상|중앙 카드 전환, footer static|
|desktop 높이 544px 이하|max-height 제한 해제, overflow visible 예외|

Header 위 여백은 기본 20px → sm 24px → md 32px입니다. 본문 위 여백은 기본 24px → sm 28px → md 36px입니다. Body 아래는 기본 24px → sm 32px입니다.

원 footer는 safe-area와 가상 키보드 보정값을 사용합니다.

```css
padding-bottom: max(
  1rem,
  calc(env(safe-area-inset-bottom) - var(--keyboard-inset, 0px))
);
```

키트는 최소 16px와 safe-area를 처리하지만 원본의 키보드 inset 측정 로직은 구현하지 않았습니다. 실제 iOS·Android 키보드 대응은 추가 작업입니다.

## 5. 제목과 본문 컴포넌트

### 온보딩 제목

- 태그: `h1`, 전환 직후 `tabindex="-1"`로 프로그램적 포커스.
- Desktop: 32px / 35.84px, 600, letter-spacing −0.035em = −1.12px.
- Mobile: 28px / 31.36px, 600, letter-spacing −0.035em = −0.98px.
- `text-wrap: balance`, 불필요한 기본 outline 제거.
- 일반 문서 h1 토큰인 36px와 다른 화면 전용 조합입니다.

### 설명

앱 연결 단계에서 기본 14px, sm 이상 16px, 행간 24px, muted-foreground, max-width 36rem이었습니다. 제목과 설명을 같은 스타일로 뭉치지 않습니다.

### 진행 정보

`role="progressbar"`, “Onboarding progress: step n of m” 접근 가능한 이름과 “Step n of m” 텍스트가 관측됐습니다. 막대 그래프가 아니라 텍스트 중심입니다. 개인 선택 시 총 단계가 4에서 3으로 변했습니다.

## 6. 버튼

|변형|높이|타이포|좌우 padding|radius|표면|
|---|---:|---|---:|---:|---|
|온보딩 Primary CTA|44px|14/20, 500|20px|12px|primary / primary-foreground|
|온보딩 Outline CTA|44px|14/20, 500|20px|12px|background + input border|
|Ghost Back/Skip anyway|32px|14/20, 500|16px|12px|transparent, muted-foreground|
|Compact Connect|24px|12/16, 500|14px|pill|background + border + elevation-xs|

- 공통 inline-flex, 중앙 정렬, gap 8px, white-space nowrap.
- 기본 버튼 아이콘 utility는 20px. Compact는 16px.
- Continue의 자식 SVG에 `size-4`도 있었지만 상위 descendant utility가 최종 크기에 영향을 주므로 클래스 이름만 보고 최종 크기를 확정하지 않습니다.
- Primary hover: primary 90% 색상.
- Ghost hover: hover 배경과 accent-foreground.
- Outline hover: accent 30%를 투명 레이어로 더하는 원본 utility가 있었습니다. 키트는 단색 혼합으로 근사합니다.
- Focus-visible: ring 2px. 키트의 outline offset 2px는 재구성입니다.
- Disabled: opacity .5, pointer-events none.
- 기본 버튼에 공통 transition utility가 있는 것으로 일반화하지 않습니다. 실제 측정은 `transition-duration: 0s`인 버튼도 있었습니다.
- 일부 Back은 음수 좌측 margin −12px로 텍스트 시작선을 맞췄습니다. 이를 모든 버튼에 적용하지 않습니다.

**권장 확장:** 24px·32px 버튼은 터치 타깃을 별도 검토합니다. 키트의 `comfortable` 또는 `.h-button-comfortable`은 44px 최소 높이를 추가하는 선택 옵션입니다. 44px을 원본 모든 버튼의 규칙이나 WCAG AA의 일률적인 의무라고 설명하지 않습니다.

## 7. Radio 선택 칩

- `button type="button" role="radio"`, `aria-checked`, radiogroup 이름.
- padding 6px 14px, 14/20, 500, border, pill.
- 그룹: flex-wrap, gap 8px.
- 기본: background / foreground / border.
- hover: muted 배경.
- checked: primary 테두리 + primary 10% 투명 배경.
- 전환: 색상 150ms, cubic-bezier(.4,0,.2,1).
- 하나의 항목만 tabindex 0이고 나머지는 −1인 roving tabIndex가 관측됐습니다.
- 실제 원본 radio의 모든 방향키 규칙은 테스트하지 않았습니다. 키트는 방향키·Home·End를 지원하도록 보완했습니다.

개인용 선택에는 optional context input이, business에는 사업 종류 radio가, team에는 부서 radio가 추가됩니다. Something else는 자유 입력을 열고, 특정 팀 선택은 optional 직함 combobox를 엽니다.

## 8. 입력 필드

### 8.1 일반 이메일 필드

초대 화면 실측:

- height 40px = 온보딩 control-field-height.
- width 100%, radius 12px, border .5px at DPR 2.
- 좌우 padding 12px, 흰 배경.
- Desktop 14/20, Mobile 16/24.
- Focus-visible 기본 outline 제거, focus border input-focus.
- disabled opacity .5, cursor not-allowed.

일반 root control-field-height 32px를 온보딩 이메일 필드에 그대로 사용하면 다릅니다.

### 8.2 Context / 자유 입력

- height 고정 토큰을 사용하지 않고 padding으로 결정.
- 14/20, padding 8px 12px, radius 16px.
- 실측 높이 37px = line 20 + 세로 padding 16 + 위아래 .5px border.
- placeholder는 muted-foreground 60%.
- focus border: input-focus.
- `aria-invalid` border: link.

### 8.3 오류 표시: 테두리와 문구의 색을 구분

첫 화면의 “Pick one to continue”를 직접 측정했습니다.

- `span role="alert"`, 12px / 16px.
- 문구 색: **blue-600**, `oklch(54.6% .245 262.881)`.
- invalid 필드의 **테두리**에 사용되는 link blue-500과 다릅니다.
- 오류 문구를 무조건 destructive 빨강으로 바꾸면 원본과 달라집니다.
- “Please add a few words to continue”도 인라인 alert로 관측했습니다. 이 문구 자체의 별도 색 계산값은 반복 측정하지 않았으므로 키트는 확인한 alert 스타일을 재사용합니다.

## 9. 직함 Combobox

관측 입력: `engineer`. 표시된 옵션:

1. Engineering Manager
2. Engineering Team Lead
3. Sales Engineer
4. Solutions Engineer
5. VP of Engineering

이 목록이 전체 직함 사전이거나 추천 순위 정책이라는 뜻은 아닙니다.

|영역|실측/선언|
|---|---|
|팝오버 위치|필드 위 `bottom:100%`, margin-bottom 4px|
|폭|부모 100%, desktop 592px|
|max-height|256px, overflow-y auto|
|배경/경계|background, border|
|radius|16px|
|padding|위·아래 4px|
|elevation|lg|
|옵션|14/20, padding 6px 12px, 높이 32px|

원본에서 ArrowDown은 첫 옵션에 selected를 부여했고 Escape는 목록을 닫았습니다. 키트는 Enter 확정, 위·아래 이동, active-descendant, blur 닫기를 재구성했습니다. 모든 스크린리더와 입력기 조합에서 검증된 것은 아닙니다.

## 10. 추천 앱 카드

Desktop 592px 영역에 2열, gap 8px. 카드 한 개는 292 × 61px였습니다.

- radius 20px, border .5px, bg-muted.
- padding 위·아래 12px, 왼쪽 14px, 오른쪽 12px.
- 내부 gap 12px.
- 아이콘 타일 32 × 32px, radius **16px**, border .5px, bg-background.
- 설명 11/16, muted-foreground, 한 줄 truncate.
- 오른쪽 Connect: 24px, 12/16, pill.
- 앱 이름의 정확한 별도 typography는 키트에서 일반 14/20 medium으로 재구성했습니다.
- 작은 화면은 1열.

Browse all apps:

- radius 20px, dashed border, muted-foreground 40% 경계.
- padding 12px 14px 12px 16px, gap 14px.
- 592px desktop에서 높이 61px.
- hover 시 primary 35% border와 foreground 텍스트.
- focus-visible ring 2px.

팀 Product/eng 선택에서는 GitHub, Jira, Sentry, Amplitude, Notion 등의 추천을 관측했습니다. 추천 알고리즘이나 모든 팀별 목록은 추정하지 않습니다.

## 11. 전체 앱 검색 모달

|속성|Desktop 관측|
|---|---|
|테마|Dark root 값|
|max-width|896px = 56rem|
|실제 폭|896px at 1265px viewport|
|max-height|85vh = 약 742.05px at 873px 높이|
|radius|20px at sm 이상|
|표면|background|
|border|.5px, border 토큰|
|shadow|dark elevation-2xl, `0 25px 50px -12px #0009`|
|타이틀|h3, 24/24, 600, −.025em|
|제목 닫기 영역|32px close reserve utility|
|검색|높이 40px, radius 12px, bg-card, 왼쪽 padding 34px|
|탭 스트립|높이 40px, gap 16px, 가로 스크롤, 아래 border|
|탭|14/20, 500, 좌우 padding 4px, 활성 아래 border 2px|

검색 input은 원본에서 자동 포커스가 되어 focus border가 이미 적용된 상태로 측정됐습니다. 이를 unfocused 기본 테두리라고 기록하지 않습니다.

모바일 390 × 844에서는 모달 폭 358px, 최종 radius 0px였습니다. 뷰포트 변경 직후 transition 중 계산된 7px대 값은 제외했습니다. 85vh는 717.4px입니다. 결과가 적으면 모달 높이는 더 작아집니다.

검색 결과가 없을 때:

> No matching apps  
> Try a different name or category.

**재구성 범위:** 카탈로그 데모는 8개 샘플 앱, 검색, 4개 카테고리, clear, 빈 상태, native dialog Escape 닫기를 제공합니다. 원본 전체 앱 목록이나 인증 플로우를 복제하지 않습니다. 결과 카드 일부 모양은 근사 재구성이며 pixel-perfect 복제가 아닙니다.

## 12. 이메일 연결·건너뛰기·초대 패턴

### 이메일 연결

한 화면에서 Gmail/Outlook 제공자를 전환합니다. 사용자 데이터 연결 버튼을 누르지 않고 문구 및 로컬 화면 상태만 확인했습니다.

### Skip offer

Skip for now를 누르면 footer의 일반 버튼 행이 보상 안내 group으로 바뀌었습니다. 별도 overlay 모달은 아닙니다.

- 40px 타일, radius 20px, rewards 배경, 흰 아이콘.
- 제목 14/20, 600.
- 보조 문구 13/20, small 화면에서 숨김.
- Skip anyway + Connect CTA.
- 안내 제목에 프로그램적 포커스.
- small 화면에서 버튼 순서를 세로로 재배치하는 class 확인.

### 팀 초대

- 초기 이메일 input 3개, 그룹 이름 “Teammates' emails”.
- 각 input에 별도 접근 가능한 이름.
- Add another 클릭 시 4번째 필드 생성 후 해당 필드 포커스.
- 실제 이메일 주소는 입력하지 않았습니다.
- Send invites는 전환 완료 후 빈 상태에서도 enabled로 보였으나 클릭하지 않았습니다. 따라서 빈 전송 검증, 중복 이메일, 성공·실패 상태는 미검증입니다.
- Contact sales 링크는 존재를 확인했으나 연락하거나 양식을 제출하지 않았습니다.

## 13. 문안·아이콘·브랜드 자산

### 문안에서 관측한 방향

- 사용자의 업무 결과를 먼저 설명: “Spend less time in your inbox”.
- 제품 1인칭: “I can help…”.
- optional을 라벨 옆에 명시.
- 설정에서 나중에 연결할 수 있음을 설명해 압박을 낮춤.
- 연결의 혜택, 보안·개인정보 안내를 별도 보조 정보로 배치.

이는 문안 패턴 분석입니다. 보안 인증·데이터 처리·요금·크레딧 정책이 현재 사실이라고 별도 검증한 것이 아닙니다.

### 자산

아이콘은 currentColor SVG, 작은 정방형 크기를 주로 사용했습니다. 아이콘 라이브러리 이름은 확정하지 않았습니다. 키트는 원본 Ramus 로고 및 서드파티 앱 로고를 포함하지 않고 텍스트·중립 약자·기본 도형을 사용합니다. Inter Latin 파일은 관측한 자산에서 가져와 HTML에 내장했습니다. HTML에 Inter의 SIL OFL 1.1 전문을 내장했고 `licenses/Inter-OFL-1.1.txt`에도 포함했습니다. 독립 제품으로 배포할 때 그 고지와 자산 권리를 유지·확인하세요.

## 14. 접근성: 관측과 보완을 분리

### 확인된 좋은 구조

- radiogroup/radio와 checked 상태.
- 전환 후 h1 포커스.
- alert와 오류 시 첫 선택지 포커스.
- combobox/listbox/option과 방향키 선택.
- 앱 연결 버튼의 구체적인 accessible name.
- progressbar 이름.
- 모달 검색 input의 초기 포커스.

이 목록이 WCAG 전체 준수나 스크린리더 호환성 인증을 뜻하지는 않습니다.

### 제한적인 색 대비 계산

실제 온보딩의 computed color를 canvas로 8-bit sRGB로 변환한 뒤 상대 휘도를 계산했습니다. 불투명 단색 조합 기준이며 반올림 오차가 있습니다. 전체 접근성 감사가 아닙니다.

|조합|전경 sRGB 근사|배경 sRGB 근사|계산 대비|
|---|---|---|---|
|기본 본문|#090908|#ffffff|19.92:1|
|CTA|#ffffff|#46443f|9.73:1|
|보조 본문|#827f77|#ffffff|4.00:1|
|앱 보조 설명|#827f77|#f4f3f0|3.60:1|
|입력 테두리|#cccac5|#ffffff|1.64:1|
|링크 / invalid 테두리|#2b7fff|#ffffff|3.76:1|
|실측 오류 문구|#155dfc|#ffffff|5.25:1|

- 작은 일반 글자의 AA 기준은 4.5:1로 비교했습니다. 큰 글자·비활성 상태·비텍스트 경계에는 다른 조건과 예외가 있으므로 일괄 판정하지 않습니다.
- 보조 본문과 11px 카드 설명은 이 계산에서 4.5:1 미만입니다. 원본을 복제할 때 보완 후보입니다.
- 1.64:1 입력 경계는 경계가 유일한 식별 수단인 경우 비텍스트 대비 3:1 검토 대상입니다. 라벨 등 전체 맥락을 검사하지 않고 바로 위반 판정하지 않습니다.
- blue-500 링크는 작은 본문 링크로 사용하면 4.5:1 검토 대상입니다. 관측한 오류 문구는 더 진한 blue-600으로 약 5.25:1입니다.
- placeholder 60% 처리, 작은 폰트, 가로 탭, 작은 버튼, 상태의 색 의존성도 추가 검토합니다.

### 선택형 보완

```html
<div class="ramus" data-theme="onboarding" data-contrast="enhanced">
  <!-- 이 scope에서 보조 글자·링크·경계를 더 진하게 -->
</div>
```

- `data-contrast="enhanced"`: Light 보조 글자 oat-600, 링크·ring blue-600, border/input oat-500. Dark의 보조 글자·경계도 선택적으로 보완.
- `.h-input-accessible`: 추가 2px outline.
- `.h-button-comfortable`: 최소 높이 44px.
- reduced-motion: 키트에서 애니메이션·전환을 줄이는 별도 규칙.

위 네 가지는 **권장 확장**입니다. 원본에서 동일한 옵션이 있다고 주장하지 않습니다. 중첩 `.ramus` 테마 경계에는 opt-in 속성을 다시 지정해야 합니다. 보완값도 실제 사용 배경에서 다시 대비를 검증하세요.

## 15. 구현 아키텍처와 의도적인 차이

### 파일 역할

|파일|역할|
|---|---|
|Ramus-Design-System.html|서버 없이 볼 수 있는 단일 파일 시각 카탈로그. 폰트·CSS·데이터·JS 내장|
|ramus.css|이름 충돌을 줄인 .ramus 토큰 scope와 h- 컴포넌트 클래스|
|RamusComponents.tsx|React 통합 예제. 원본 소스가 아닌 새 구현|
|ramus.tokens.json|원 토큰 정의, 테마 그룹, 조건과 fallback 원 규칙|
|ramus.evidence.json|관측 환경, 실제 측정 노드, 색 대비 계산, 원본 복구 확인|
|README.md|가장 빠른 시작, 한계, 파일 설명|
|references/screenshots/|원본 캡처 16개. 실제 파일 포맷에 맞는 확장자 보존|
|references/index.html|원본 캡처 썸네일 모음. 폴더 구조 유지 필요|
|references/manifest.json|캡처 시각·viewport·이미지 픽셀·파일 정보|

`ramus.tokens.json`은 근거 보존용 JSON입니다. DTCG/Style Dictionary/Token Studio 전용 import schema라고 주장하지 않습니다. 해당 도구에 넣으려면 별도 어댑터가 필요합니다.

### 사용

```tsx
import './ramus.css';
import { RamusProvider, Button, RadioChips, TextField } from './RamusComponents';

<RamusProvider theme="onboarding" data-contrast="enhanced">
  <Button size="cta">Continue</Button>
</RamusProvider>
```

폰트는 별도 프로젝트에서 Inter를 제공하거나 시스템 폴백을 사용합니다. HTML에 내장된 Latin 폰트가 한국어 지원까지 제공하는 것은 아닙니다.

### React API 요약

|Export|주요 API / 역할|
|---|---|
|RamusProvider|theme, contrast; .ramus scope와 선택형 대비 강화|
|Button|variant=primary/outline/ghost, size=default/cta/compact, comfortable|
|RadioChips|label, options, value, onValueChange, disabled; roving focus|
|TextField|label, hint, error, invalid; input props와 ID/description 연결|
|RoleCombobox|label, options, value, onValueChange; 편집/부분 검색/자유 입력/옵션 확정|
|AppCard|title, subtitle, icon, action|
|StepProgress|step, total, label; progressbar 의미와 텍스트|
|CatalogDialog|open, onClose, theme 기본 dark, title, description; native modal|
|Demo|외부 API 없이 로컬 state만 사용하는 통합 예제|

옵션은 고유한 value를 가져야 합니다. Combobox에서 option.value와 일치하는 value는 label로 표시하며 그 외의 문자열은 자유 입력으로 유지합니다. TextField의 추가 outline과 combobox IME guard는 재구성 보완입니다. 실제 서비스 연결·submit 핸들러는 호출자가 제공해야 합니다.

### 원본과 같지 않은 부분

1. 전체 Light 기반 Onboarding 정규화.
2. scope마다 alias 재바인딩으로 상속된 이전 테마값을 예방.
3. h- prefix와 .ramus scope.
4. Outline hover의 투명 gradient 레이어를 단색 혼합으로 근사.
5. native dialog 사용. 원본 모달 프레임워크 구현을 복제하지 않음.
6. 키보드·reduced-motion·편의 props·대비 opt-in 추가.
7. 실제 서비스 연결·초대·저장 로직 제외.
8. 샘플 앱·중립 아이콘만 제공.
9. 원본 제품 프리뷰 배경 이미지는 생략하고 단색 stage를 사용.
10. 원본 utility의 전체 keyframes는 포함하지 않음. animate-* 토큰을 단독으로 소비하려면 keyframes를 추가해야 함.
11. 모바일 가상 키보드 inset 측정 로직 미구현.

### 현대 CSS 지원 범위

키트는 OKLCH, color-mix, 상대색, dvh, text-wrap 등 현대 브라우저 기능을 사용합니다. sourceRules에 원본 fallback이 있지만 키트 CSS 전체를 구형 브라우저 fallback으로 재작성하지 않았습니다. Chrome 계열 실사용 환경에서 렌더링을 확인했고 구형 Safari/Firefox까지 보장하지 않습니다.

## 16. Figma·팀 핸드오프 권장 구성

아래는 신규 도입을 위한 **권장 구조**이며 실제 Ramus Figma 네이밍이 아닙니다.

- Collections: `Primitive`, `Semantic`, `Component`.
- Modes: `Light`, `Dark`, `Onboarding`.
- Primitive 예: `color/oat/700`, `space/4`, `radius/md`.
- Semantic 예: `surface/background`, `text/default`, `action/primary`, `border/default`.
- Component 예: `button/cta/height`, `input/context/radius`, `onboarding/shell/max-width`.
- Button variants: visual × size × state. 원본 실측과 권장 확장을 문서 property로 구분.
- Radio chips: default/hover/focus/checked, 그룹 wrapping.
- Text field: email/context/search, default/focus/invalid/disabled.
- Dialog: desktop/mobile, populated/empty, root dark 경계.
- “Source status” 속성: Measured / CSS-only / Reconstructed / Recommended.

같은 HEX가 우연히 같아도 primary와 chrome-primary, border와 chrome-border처럼 역할이 다른 이름은 함부로 합치지 않습니다. primitive와 semantic alias 관계를 보존합니다.

## 17. 적용 전 QA 체크리스트

- [ ] 390 / 640 / 768 / 1265px 전환점 전후.
- [ ] 544px 이하 낮은 desktop 높이.
- [ ] 실제 iOS·Android 키보드, safe-area, 확대 200%.
- [ ] 긴 한국어 버튼과 라벨, 영문 URL, 앱 이름, RTL 필요 여부.
- [ ] Tab/Shift+Tab, 방향키, Space/Enter, Escape, Home/End.
- [ ] 모달 열기/닫기의 포커스 복귀, background inert, nested dialog.
- [ ] combobox IME 조합·스크린리더·클릭 및 키보드 확정.
- [ ] radio 선택 변경 시 새 필드와 오류의 포커스.
- [ ] 라이트/다크/중첩 scope/모달 테마 경계.
- [ ] disabled opacity, 작은 Connect의 실제 터치 타깃.
- [ ] 기본·hover·focus·invalid·selected의 텍스트/비텍스트 대비.
- [ ] 네트워크 대기·실패·재시도·연결 취소 상태. 이번 관측에서는 미확인.
- [ ] 유효·무효·중복 초대, 성공·부분 실패. 이번 관측에서는 미실행.
- [ ] reduced-motion, forced-colors/high-contrast, 폰트 로딩 실패.

## 18. 조사 한계

현재 페이지에서 안전하게 접근 가능한 온보딩과 앱 검색 모달을 중심으로 조사했습니다. 인증 이후의 앱 본체·채팅·에디터·설정·결제·차트·음성 UI를 직접 탐색한 것은 아닙니다. 해당 영역은 CSS 토큰이 존재한다는 수준으로만 기록했습니다.

공식 Figma, source repository, 디자이너의 명시적 의도, 전체 사이트의 모든 상태는 확인하지 않았습니다. 따라서 이 결과는 **관측 기반 reference system**으로 사용하고 원 서비스의 완전한 내부 시스템이라고 부르지 않습니다.

---

## 부록 A. 전체 Foundations 원값과 테마 비교

다음 Foundations는 토큰 자료에 초점을 둡니다. 이 부분에서의 ‘미검증’은 토큰 자료만으로 확정할 수 없다는 뜻이며, 앞쪽 컴포넌트 실측 장에서 보완한 내용은 그 장을 우선합니다.


이 문서는 Ramus 화면에서 추출한 CSS 토큰과 저장된 계산 스타일을 바탕으로 재구성한 Foundations다. 공식 제공 명세, 조직의 디자인 원칙, 전체 제품의 컴포넌트 카탈로그를 의미하지 않는다. 근거가 되는 원 선언과 해석을 구분하며, 토큰 이름만으로 화면의 사용처나 동작을 확정하지 않는다.

핵심 전제는 **캡처 당시 root는 dark이지만 onboarding에는 별도의 scoped light 규칙이 존재한다**는 점이다. root의 어두운 계산값을 onboarding의 색상표로 복사해서는 안 된다. 동시에 onboarding을 모든 토큰이 light로 바뀌는 완전한 테마로 간주해서도 안 된다. 이 문서는 두 가지 오류를 모두 피하도록 구성했다.

### F1. 근거, 범위, 수치 표기

#### 1.1 사용한 근거

|근거 파일|확인 가능한 내용|확정할 수 없는 내용|
|---|---|---|
|ramus.tokens.json → sourceRules|68개 규칙 항목의 selector, context, 원 선언, font-face|미포함 스타일과 요소별 최종 적용 결과|
|ramus.tokens.json → definitions|foundation 193개, light 100개, dark 86개, onboarding 28개로 정리된 토큰|그룹화 과정에서 생략된 조건과 전체 cascade|
|ramus.evidence.json → baseStyles|root/body 계산값, 변수, 폰트 상태, 캡처 환경|모든 자손 요소와 모든 컴포넌트 상태의 계산값|

정의 파일은 탐색과 값 대조에 사용하고 selector 및 조건은 규칙 파일을 우선한다. 특히 정의 파일의 light 그룹에 들어 있는 hairline 0.5px는 무조건적인 light 기본값이 아니다. 원 규칙은 해상도 조건 아래의 root 선언이다. 분류된 JSON만으로 테마의 완전성이나 조건 없는 적용을 판단하지 않는다.

#### 1.2 관측 환경과 환산 기준

저장된 viewport는 1265 × 873, DPR은 2다. root font-size는 16px이고 color-scheme은 dark다. body는 Inter 우선의 font-family, font-size 16px, line-height 24px를 가진다. 저장된 body 전경은 `oklch(0.84 0.008 91.5)`이고 배경은 `color(srgb 0.0731331 0.0706377 0.063272)`를 포함한 background 직렬화다. 이는 body의 증거이지 onboarding 자손의 계산 결과는 아니다.

이하 px는 root 16px에서 rem을 산술 환산한 참고값이다. 실제 요소 치수나 box model 측정값이 아니며, root 변경 시 결과가 달라질 수 있다. 표의 미재정의는 값이 없다는 뜻이 아니라 해당 scope에 로컬 재선언이 없다는 뜻이다. CSS 상속과 다른 규칙의 존재 여부를 함께 확인해야 한다.

### F2. 토큰 계층과 테마 적용 모델

기초 계층에는 색상 팔레트, spacing, container, 글자 크기, weight, tracking, leading, radius, easing이 있다. 의미 계층에는 background, foreground, primary, border, input, ring과 상태색이 있다. 제품 영역 계층에는 chrome, voice, credit, private, peer, rewards, playbooks 및 이름 있는 색상군이 있다. 별칭 계층은 shadow와 elevation, color-border와 border처럼 소비 이름과 원천 역할을 연결한다. 이 계층 구분은 문서 정리를 위한 해석이며 공식 아키텍처 명칭은 아니다.

기초 선언의 selector는 `:root, :host`다. 기본 역할값은 `:root`, dark 재정의는 `:root.dark`, onboarding 재정의는 `.onboarding-light-scope`에 있다. dark 선언에는 `color-scheme: dark`, onboarding에는 `color-scheme: light`와 `color: var(--foreground)`가 있다. color-scheme 설정은 브라우저에 색상 체계를 알리지만 모든 사용자 정의 색상 토큰을 자동으로 변환하지 않는다.

`--lightningcss-light`, `--lightningcss-dark`는 해당 선언과 함께 나타나는 컴파일 보조 변수로 구분한다. `--tw-*` 역시 저장된 스타일에 존재하지만 제품의 디자인 결정과 동일한 공개 토큰으로 취급하지 않는다. 두 종류의 변수를 디자인 토큰 수에 무차별 합산하거나 이름에서 제품 의미를 만들어내지 않는다.

### F3. 색상 원재료와 지원 조건

#### 3.1 Oat 11단계 원 OKLCH

|토큰|원값|
|---|---|
|`--color-oat-50`|`oklch(98.5% .002 91.5)`|
|`--color-oat-100`|`oklch(96.3% .004 91.5)`|
|`--color-oat-200`|`oklch(92% .005 91.5)`|
|`--color-oat-300`|`oklch(84% .008 91.5)`|
|`--color-oat-400`|`oklch(72% .011 91.5)`|
|`--color-oat-500`|`oklch(55.3% .013 91.5)`|
|`--color-oat-600`|`oklch(47% .012 91.5)`|
|`--color-oat-700`|`oklch(38.8% .01 91.5)`|
|`--color-oat-800`|`oklch(30.5% .008 91.5)`|
|`--color-oat-900`|`oklch(22.2% .005 91.5)`|
|`--color-oat-950`|`oklch(14% .003 91.5)`|

Oat는 모든 단계가 hue 91.5를 공유하고 낮은 chroma를 갖는 팔레트다. 이 수치에 근거해 중성에 가까운 따뜻한 계열이라고 설명할 수는 있지만 브랜드 철학이나 접근성 보증까지 추론할 수는 없다. 명도 간격이 일정한 등차 수열이 아니므로 빠진 중간 단계나 다른 shade를 보간해 원 토큰처럼 추가하지 않는다.

#### 3.2 보조 팔레트 원값

|토큰|원값|
|---|---|
|`--color-red-400`|`oklch(70.4% .191 22.216)`|
|`--color-red-500`|`oklch(63.7% .237 25.331)`|
|`--color-red-600`|`oklch(57.7% .245 27.325)`|
|`--color-orange-400`|`oklch(75% .183 55.934)`|
|`--color-orange-500`|`oklch(70.5% .213 47.604)`|
|`--color-orange-600`|`oklch(64.6% .222 41.116)`|
|`--color-amber-50`|`oklch(98.7% .022 95.277)`|
|`--color-amber-200`|`oklch(92.4% .12 95.746)`|
|`--color-amber-300`|`oklch(87.9% .169 91.605)`|
|`--color-amber-400`|`oklch(82.8% .189 84.429)`|
|`--color-amber-500`|`oklch(76.9% .188 70.08)`|
|`--color-amber-700`|`oklch(55.5% .163 48.998)`|
|`--color-amber-900`|`oklch(41.4% .112 45.904)`|
|`--color-amber-950`|`oklch(27.9% .077 45.635)`|
|`--color-yellow-100`|`oklch(97.3% .071 103.193)`|
|`--color-yellow-400`|`oklch(85.2% .199 91.936)`|
|`--color-yellow-500`|`oklch(79.5% .184 86.047)`|
|`--color-yellow-700`|`oklch(55.4% .135 66.442)`|
|`--color-green-400`|`oklch(79.2% .209 151.711)`|
|`--color-green-500`|`oklch(72.3% .219 149.579)`|
|`--color-green-600`|`oklch(62.7% .194 149.214)`|
|`--color-emerald-400`|`oklch(76.5% .177 163.223)`|
|`--color-emerald-500`|`oklch(69.6% .17 162.48)`|
|`--color-emerald-700`|`oklch(50.8% .118 165.612)`|
|`--color-teal-400`|`oklch(77.7% .152 181.912)`|
|`--color-teal-500`|`oklch(70.4% .14 182.503)`|
|`--color-teal-700`|`oklch(51.1% .096 186.391)`|
|`--color-cyan-400`|`oklch(78.9% .154 211.53)`|
|`--color-cyan-500`|`oklch(71.5% .143 215.221)`|
|`--color-sky-400`|`oklch(74.6% .16 232.661)`|
|`--color-sky-500`|`oklch(68.5% .169 237.323)`|
|`--color-sky-700`|`oklch(50% .134 242.749)`|
|`--color-blue-400`|`oklch(70.7% .165 254.624)`|
|`--color-blue-500`|`oklch(62.3% .214 259.815)`|
|`--color-blue-600`|`oklch(54.6% .245 262.881)`|
|`--color-indigo-400`|`oklch(67.3% .182 276.935)`|
|`--color-indigo-500`|`oklch(58.5% .233 277.117)`|
|`--color-indigo-600`|`oklch(51.1% .262 276.966)`|
|`--color-violet-400`|`oklch(70.2% .183 293.541)`|
|`--color-violet-500`|`oklch(60.6% .25 292.717)`|
|`--color-violet-600`|`oklch(54.1% .281 293.009)`|
|`--color-violet-700`|`oklch(49.1% .27 292.581)`|
|`--color-purple-400`|`oklch(71.4% .203 305.504)`|
|`--color-purple-500`|`oklch(62.7% .265 303.9)`|
|`--color-pink-400`|`oklch(71.8% .202 349.761)`|
|`--color-pink-500`|`oklch(65.6% .241 354.308)`|
|`--color-pink-600`|`oklch(59.2% .249 .584)`|
|`--color-rose-400`|`oklch(71.2% .194 13.428)`|
|`--color-rose-500`|`oklch(64.5% .246 16.439)`|
|`--color-rose-600`|`oklch(58.6% .253 17.585)`|
|`--color-gray-200`|`oklch(92.8% .006 264.531)`|
|`--color-gray-700`|`oklch(37.3% .034 259.733)`|
|`--color-neutral-500`|`oklch(55.6% 0 0)`|
|`--color-neutral-900`|`oklch(20.5% 0 0)`|
|`--color-black`|`#000`|
|`--color-white`|`#fff`|

이 표는 추출에서 확인된 단계만 나열한다. 모든 색상군에 50부터 950까지 완전한 단계가 존재한다고 단정하지 않는다. white와 black은 HEX, 다수의 유채색은 OKLCH다. 서로 다른 표기 형식을 보존하고, 문서 편의를 위해 색상을 임의로 반올림하거나 모두 HEX로 정규화하지 않는다.

#### 3.3 현대 color-mix 환경과 fallback

본문의 역할값은 `(color:color-mix(in lab, red, red))` 지원 조건이 충족되는 환경을 기준으로 한다. 이 context는 지원 여부 검사이며 실제 혼합 공간이 항상 lab라는 뜻은 아니다. 선언에는 srgb, oklab, oklch가 각각 사용된다. 두 번째 비율이 생략된 경우에도 원 수식을 그대로 유지한다.

transparent와 섞인 hover 및 selection 색상은 불투명 단색과 구분한다. 실제 보이는 결과는 아래 배경의 영향을 받으므로 단독 swatch의 겉보기 색을 모든 표면의 고정 결과로 정의하지 않는다. 상대색 `oklch(from var(--link) .7 c h)`도 사용하므로 color-mix 지원만으로 관련 문법 전체의 동작을 별도 검증 없이 보증하지 않는다.

아래는 조건 이전 값의 대표 사례다. 지원 조건에서 대체되는 최종식은 이후 역할표에 원문으로 수록한다.

|selector|토큰|조건 이전 값 / fallback|
|---|---|---|
|:root|--secondary / --frame|#edece8|
|:root|--muted-foreground / --chrome-muted-foreground|#827f77|
|:root|--border|#d9d7d3|
|:root|--chrome-secondary / --chrome-accent / --chrome-border|#e1dfdb / #ebeae7 / #dfdeda|
|:root|--private-accent|#a685ff4d|
|:root.dark|--background / --card / --popover|#131210 / #262522 / #262522|
|:root.dark|--secondary-foreground / --muted-foreground|#bab7b1 / #8e8b83|
|:root.dark|--message-highlight / --border|#59401c / #3b3a35|
|:root.dark|--chrome-secondary / --chrome-muted-foreground / --chrome-border|#3b3a35 / #8e8b83 / #3b3a35|
|:root.dark|--private-accent|#7008e799|
|.onboarding-light-scope|--secondary / --muted-foreground|#edece8 / #827f77|

hover의 조건 이전 값은 accent 참조이며, chrome-hover는 chrome-accent 참조다. doc-table-selection-fill도 light에서 link, dark에서 selection-ring을 먼저 참조한 뒤 지원 조건에서 투명 혼합식으로 바뀐다. fallback은 항상 HEX라는 뜻이 아니다. 구형 환경 호환성 자체는 이 문서에서 검증하지 않았다.

### F4. Light, dark, onboarding 역할값

#### 4.1 표면, 전경, 입력, 경계

|토큰|기본 light 선언|root dark 유효 선언|onboarding 로컬 선언|
|---|---|---|---|
|`--background`|`var(--color-white)`|`color-mix(in srgb, var(--color-oat-900) 50%, var(--color-oat-950))`|`var(--color-white)`|
|`--foreground`|`var(--color-oat-950)`|`var(--color-oat-300)`|`var(--color-oat-950)`|
|`--foreground-strong`|`var(--foreground)`|`var(--color-oat-50)`|미재정의: 상위 값 상속|
|`--card`|`var(--color-white)`|`color-mix(in srgb, var(--color-oat-800) 50%, var(--color-oat-900))`|`var(--color-white)`|
|`--card-foreground`|`var(--color-oat-950)`|`var(--color-oat-300)`|`var(--color-oat-950)`|
|`--popover`|`var(--color-white)`|`color-mix(in srgb, var(--color-oat-800) 50%, var(--color-oat-900))`|미재정의: 상위 값 상속|
|`--popover-foreground`|`var(--color-oat-950)`|`var(--color-oat-300)`|미재정의: 상위 값 상속|
|`--primary`|`var(--color-oat-700)`|`var(--color-white)`|`var(--color-oat-700)`|
|`--primary-foreground`|`var(--color-white)`|`var(--color-oat-950)`|`var(--color-white)`|
|`--secondary`|`color-mix(in srgb, var(--color-oat-200) 50%, var(--color-oat-100))`|`var(--color-oat-800)`|`color-mix(in srgb, var(--color-oat-200) 50%, var(--color-oat-100))`|
|`--secondary-foreground`|`var(--muted-foreground)`|`color-mix(in srgb, var(--color-oat-300) 50%, var(--color-oat-400))`|`var(--muted-foreground)`|
|`--muted`|`var(--color-oat-100)`|`var(--color-oat-800)`|`var(--color-oat-100)`|
|`--muted-foreground`|`color-mix(in srgb, var(--color-oat-400) 25%, var(--color-oat-500))`|`color-mix(in srgb, var(--color-oat-400) 50%, var(--color-oat-500))`|`color-mix(in srgb, var(--color-oat-400) 25%, var(--color-oat-500))`|
|`--code`|`var(--color-oat-200)`|`var(--muted)`|미재정의: 상위 값 상속|
|`--accent`|`var(--color-oat-100)`|`var(--color-oat-800)`|`var(--color-oat-100)`|
|`--hover`|`color-mix(in oklab, var(--accent) 50%, transparent)`|`color-mix(in oklab, var(--accent) 50%, transparent)`|`color-mix(in oklab, var(--accent) 50%, transparent)`|
|`--accent-foreground`|`var(--color-oat-950)`|`var(--color-oat-300)`|`var(--color-oat-950)`|
|`--border`|`color-mix(in srgb, var(--color-oat-200) 50%, var(--color-oat-300))`|`color-mix(in srgb, var(--color-oat-800) 50%, var(--color-oat-700))`|`var(--color-oat-300)`|
|`--popover-border`|`var(--color-oat-300)`|`var(--color-oat-700)`|미재정의: 상위 값 상속|
|`--input`|`var(--color-oat-300)`|`var(--color-oat-700)`|`var(--color-oat-300)`|
|`--input-focus`|`var(--color-oat-600)`|`var(--color-oat-400)`|`var(--color-oat-600)`|
|`--link`|`var(--color-blue-500)`|`var(--color-blue-500)`|미재정의: 상위 값 상속|
|`--ring`|`var(--link)`|`oklch(from var(--link) .7 c h)`|`var(--link)`|
|`--frame`|`color-mix(in srgb, var(--color-oat-100) 50%, var(--color-oat-200))`|`var(--color-oat-950)`|미재정의: 상위 값 상속|

primary는 light에서 oat-700, dark에서 white다. 따라서 primary를 고정된 유채색 브랜드 토큰이라고 정의하면 원 선언과 어긋난다. link는 blue-500을 참조하며 primary와 분리된다. dark ring은 link의 hue와 chroma를 유지하면서 OKLCH 명도 성분을 0.7로 지정한다. 이는 색상 정의이며 focus outline의 두께나 offset을 규정하지 않는다.

기본 light border는 oat-200과 oat-300의 50:50 srgb 혼합이지만 onboarding border는 oat-300 단독이다. onboarding의 control 높이도 별도이므로 scoped light를 기본 light의 다른 이름으로 취급하지 않는다. card나 popover라는 토큰 이름은 색상 역할을 보여줄 뿐 실제 컴포넌트의 배치, padding, 테두리 여부, 열림 상태를 입증하지 않는다.

#### 4.2 상태색과 강조

|토큰|기본 light 선언|root dark 유효 선언|onboarding 로컬 선언|
|---|---|---|---|
|`--destructive`|`oklch(57.7% .245 27.325)`|`var(--color-red-500)`|`oklch(57.7% .245 27.325)`|
|`--destructive-foreground`|`var(--color-white)`|`var(--color-white)`|미재정의: 상위 값 상속|
|`--destructive-accent`|`#ff4a4d`|`var(--destructive)`|미재정의: 상위 값 상속|
|`--success`|`oklch(60% .179 142.495)`|`oklch(69.6% .17 162.48)`|`oklch(60% .179 142.495)`|
|`--warning`|`oklch(76.9% .188 70.08)`|`oklch(82.8% .189 84.429)`|미재정의: 상위 값 상속|
|`--message-highlight`|`var(--color-yellow-100)`|`color-mix(in srgb, var(--color-yellow-700) 35%, var(--color-oat-800))`|미재정의: 상위 값 상속|

성공색은 light와 dark 사이에서 명도뿐 아니라 hue와 chroma도 달라진다. destructive는 light에서 red-600과 같은 원 OKLCH, dark에서 red-500 참조다. warning과 message-highlight 역시 별도 테마값이다. 같은 이름의 상태를 유지하면서 색상값이 바뀐다는 사실과 그 상태가 특정 버튼 또는 알림에 적용됐다는 주장은 분리한다.

#### 4.3 Onboarding의 적용 경계

추출된 onboarding 그룹은 28개 사용자 정의 속성을 재선언한다. control-field-height, 표면과 전경 일부, primary, secondary, muted, accent, hover, destructive, success, border, input, input-focus, ring, 일곱 elevation, raised가 해당한다. 여기에 일반 CSS 속성인 color-scheme과 color가 별도로 있다. 사용자 정의 속성 수와 CSS 선언 전체 수를 혼동하지 않는다.

반대로 foreground-strong, popover 계열, code, warning, destructive-accent, message-highlight, frame, chrome, chart, voice, private, peer, 이름 있는 domain 색상은 이 scope에서 재정의되지 않는다. dark root 아래에서는 원칙적으로 상위에서 계산된 토큰이 이어진다. 이를 실제 화면의 오류라고 단정하지는 않는다. 해당 토큰이 onboarding에서 사용되는지, 요소가 scope 안에 있는지, 추가 규칙이 있는지는 현재 근거로 확인되지 않았다.

### F5. Chrome 색상 계층

|토큰|기본 light 선언|root dark 유효 선언|onboarding 로컬 선언|
|---|---|---|---|
|`--chrome`|`var(--color-oat-50)`|`var(--color-oat-900)`|미재정의: 상위 값 상속|
|`--chrome-foreground`|`var(--color-oat-950)`|`var(--color-oat-400)`|미재정의: 상위 값 상속|
|`--chrome-foreground-strong`|`var(--chrome-foreground)`|`var(--color-oat-50)`|미재정의: 상위 값 상속|
|`--chrome-primary`|`var(--color-oat-700)`|`var(--color-white)`|미재정의: 상위 값 상속|
|`--chrome-primary-foreground`|`var(--color-white)`|`var(--color-oat-950)`|미재정의: 상위 값 상속|
|`--chrome-secondary`|`color-mix(in srgb, var(--color-oat-300) 20%, var(--color-oat-200))`|`color-mix(in srgb, var(--color-oat-700) 50%, var(--color-oat-800))`|미재정의: 상위 값 상속|
|`--chrome-secondary-foreground`|`var(--chrome-muted-foreground)`|`var(--chrome-muted-foreground)`|미재정의: 상위 값 상속|
|`--chrome-muted`|`var(--color-oat-200)`|`var(--color-oat-800)`|미재정의: 상위 값 상속|
|`--chrome-muted-foreground`|`color-mix(in srgb, var(--color-oat-400) 25%, var(--color-oat-500))`|`color-mix(in srgb, var(--color-oat-400) 50%, var(--color-oat-500))`|미재정의: 상위 값 상속|
|`--chrome-accent`|`color-mix(in srgb, var(--color-oat-200) 60%, var(--color-oat-100))`|`var(--color-oat-800)`|미재정의: 상위 값 상속|
|`--chrome-hover`|`color-mix(in oklab, var(--chrome-accent) 50%, transparent)`|`color-mix(in oklab, var(--chrome-accent) 50%, transparent)`|미재정의: 상위 값 상속|
|`--chrome-accent-foreground`|`var(--color-oat-950)`|`var(--color-oat-300)`|미재정의: 상위 값 상속|
|`--chrome-border`|`color-mix(in srgb, var(--color-oat-200) 75%, var(--color-oat-300))`|`color-mix(in srgb, var(--color-oat-800) 50%, var(--color-oat-700))`|미재정의: 상위 값 상속|

chrome은 콘텐츠 표면과 구분된 별도의 색상 역할군이다. 기본 light chrome은 oat-50이며 dark chrome은 oat-900이다. dark chrome-foreground는 oat-400으로 일반 foreground의 oat-300과도 다르다. secondary와 muted의 참조 관계가 일부 같더라도 이름을 합쳐 제거하지 않는다. 현재도 역할 구분과 일부 값 차이가 존재한다.

chrome-hover는 chrome-accent를 oklab에서 transparent와 50% 혼합한다. light chrome-border는 oat-200이 75%인 srgb 혼합이며 일반 border의 50% 혼합과 다르다. 근접한 경계색을 하나로 통합하면 추출한 차이가 사라진다. onboarding은 chrome을 다시 선언하지 않으므로 scoped light의 포괄적인 재설정 대상으로 오인하지 않는다.

### F6. Chart와 제품 영역 토큰

#### 6.1 Chart 팔레트

|토큰|기본 light 선언|root dark 유효 선언|onboarding 로컬 선언|
|---|---|---|---|
|`--chart-1`|`oklch(64.6% .222 41.116)`|`oklch(63% .19 41.116)`|미재정의: 상위 값 상속|
|`--chart-2`|`oklch(60% .118 184.704)`|`oklch(63% .118 184.704)`|미재정의: 상위 값 상속|
|`--chart-3`|`oklch(39.8% .07 227.392)`|`oklch(63% .07 227.392)`|미재정의: 상위 값 상속|
|`--chart-4`|`oklch(82.8% .189 84.429)`|`oklch(63% .15 84.429)`|미재정의: 상위 값 상속|
|`--chart-5`|`oklch(76.9% .188 70.08)`|`oklch(63% .15 70.08)`|미재정의: 상위 값 상속|

light chart는 단계별 명도가 다르고 dark chart는 모두 63% 명도를 갖는다. hue와 chroma는 여전히 다르며 chart-1, chart-4, chart-5는 테마 사이에서 chroma도 바뀐다. 번호가 특정 사업 지표, 시리즈 순서, 위험도 또는 성공과 실패를 뜻한다는 근거는 없다. 배경 대비, 범례 가독성, 색각 다양성, 시리즈 식별 성능도 수치만으로 통과 판정하지 않는다.

#### 6.2 Voice 역할값

|토큰|기본 light 선언|root dark 유효 선언|onboarding 로컬 선언|
|---|---|---|---|
|`--voice-listening`|`oklch(91.5% .055 62)`|`oklch(34% .055 55)`|미재정의: 상위 값 상속|
|`--voice-speaking`|`oklch(86.5% .095 58)`|`oklch(42% .09 55)`|미재정의: 상위 값 상속|
|`--voice-thinking`|`oklch(91.5% .04 258)`|`oklch(33% .05 262)`|미재정의: 상위 값 상속|
|`--voice-answering`|`oklch(87% .075 258)`|`oklch(41% .09 262)`|미재정의: 상위 값 상속|
|`--voice-idle`|`oklch(92.5% .004 91.5)`|`oklch(30% .005 91.5)`|미재정의: 상위 값 상속|

각 이름과 색상 정의는 확인되지만 실제 음성 UI의 전이 규칙, 애니메이션, 이벤트 타이밍은 확인되지 않았다. listening과 speaking이 서로 다른 수치라는 점을 기록하되 항상 어떤 순서로 재생되거나 어떤 상황에서 활성화되는지 설명을 만들어 넣지 않는다.

#### 6.3 이름 있는 domain 색상군

|토큰|기본 light 선언|root dark 유효 선언|onboarding 로컬 선언|
|---|---|---|---|
|`--sun-surface`|`oklch(88.62% .094 79.4)`|`oklch(36% .06 79.5)`|미재정의: 상위 값 상속|
|`--sun`|`oklch(83% .155 79.5)`|`oklch(72% .13 79.5)`|미재정의: 상위 값 상속|
|`--sun-foreground`|`oklch(26% .06 79.5)`|`oklch(90% .08 79.5)`|미재정의: 상위 값 상속|
|`--flame-surface`|`oklch(80.82% .112 38.2)`|`oklch(36% .07 38)`|미재정의: 상위 값 상속|
|`--flame`|`oklch(70% .185 38)`|`oklch(66% .16 38)`|미재정의: 상위 값 상속|
|`--flame-foreground`|`oklch(26% .065 38)`|`oklch(89% .07 38)`|미재정의: 상위 값 상속|
|`--ultra-surface`|`oklch(86.28% .062 261)`|`oklch(34% .06 261)`|미재정의: 상위 값 상속|
|`--ultra`|`oklch(72% .14 261)`|`oklch(66% .13 261)`|미재정의: 상위 값 상속|
|`--ultra-foreground`|`oklch(26% .05 261)`|`oklch(89% .05 261)`|미재정의: 상위 값 상속|
|`--leaf-surface`|`oklch(86.22% .078 149.5)`|`oklch(34% .06 150)`|미재정의: 상위 값 상속|
|`--leaf`|`oklch(79% .13 150)`|`oklch(70% .12 150)`|미재정의: 상위 값 상속|
|`--leaf-foreground`|`oklch(26% .05 150)`|`oklch(89% .06 150)`|미재정의: 상위 값 상속|
|`--iris-surface`|`oklch(87% .06 320)`|`oklch(34% .05 327)`|미재정의: 상위 값 상속|
|`--iris`|`oklch(72% .14 327)`|`oklch(66% .13 327)`|미재정의: 상위 값 상속|
|`--iris-foreground`|`oklch(30.65% .1083 327.1)`|`oklch(89% .05 327)`|미재정의: 상위 값 상속|

sun, flame, ultra, leaf, iris는 surface, 본색, foreground의 세 토큰을 가진다. light에서 밝은 surface와 어두운 foreground, dark에서 어두운 surface와 밝은 foreground라는 수치 방향을 확인할 수 있다. 그러나 각 이름이 특정 요금제, 에이전트, 기능, 사용자 유형을 뜻하는지는 자료에 없다. 명칭과 원값을 보존하고 제품 의미의 확정은 보류한다.

#### 6.4 Credit, private, peer, rewards, 기타

|토큰|기본 light 선언|root dark 유효 선언|onboarding 로컬 선언|
|---|---|---|---|
|`--credit-warning`|`#f59e0b`|`#f59e0b`|미재정의: 상위 값 상속|
|`--credit-warning-admin`|`#f19700`|`#f19700`|미재정의: 상위 값 상속|
|`--credit-exhausted`|`#ff4a4d`|`#ff4a4d`|미재정의: 상위 값 상속|
|`--private-accent`|`color-mix(in srgb, var(--color-violet-400) 30%, transparent)`|`color-mix(in srgb, var(--color-violet-700) 60%, transparent)`|미재정의: 상위 값 상속|
|`--private-badge`|`var(--color-violet-400)`|`var(--color-violet-500)`|미재정의: 상위 값 상속|
|`--private-badge-foreground`|`var(--color-white)`|`var(--color-white)`|미재정의: 상위 값 상속|
|`--icon-tile`|`var(--color-oat-400)`|`var(--color-oat-500)`|미재정의: 상위 값 상속|
|`--icon-tile-muted`|`var(--color-oat-200)`|`var(--color-oat-700)`|미재정의: 상위 값 상속|
|`--doc-table-selection-ring`|`var(--link)`|`oklch(from var(--link) .7 c h)`|미재정의: 상위 값 상속|
|`--doc-table-selection-fill`|`color-mix(in oklch, var(--link) 12%, transparent)`|`color-mix(in oklch, var(--doc-table-selection-ring) 24%, transparent)`|미재정의: 상위 값 상속|

credit 세 값은 light와 dark에서 같은 값으로 선언된다. private-accent는 light에서 violet-400의 30%, dark에서 violet-700의 60%를 transparent와 혼합한다. 문서 표 선택 fill은 light 12%, dark 24%의 oklch 혼합이다. 비율만 비교해 실제 체감 강도가 정확히 두 배라고 표현하지 않는다.

|토큰|원값|
|---|---|
|`--peer-red`|`#ef4444`|
|`--peer-amber`|`#f59e0b`|
|`--peer-lime`|`#84cc16`|
|`--peer-emerald`|`#10b981`|
|`--peer-teal`|`#14b8a6`|
|`--peer-cyan`|`#06b6d4`|
|`--peer-sky`|`#0ea5e9`|
|`--peer-blue`|`#3b82f6`|
|`--peer-indigo`|`#6366f1`|
|`--peer-purple`|`#a855f7`|
|`--peer-pink`|`#ec4899`|
|`--peer-rose`|`#f43f5e`|

peer 색상은 기본 root에 있으며 별도의 dark 재정의가 추출되지 않았다. 이름만으로 협업자의 배정 알고리즘이나 동시 편집 기능의 상세 동작을 보증하지 않는다.

|토큰|원값|
|---|---|
|`--color-rewards`|`#2e8c99`|
|`--color-rewards-hover`|`#257884`|
|`--color-rewards-hover-dark`|`#3fa2b1`|
|`--color-rewards-ink`|`#1f6e7a`|
|`--color-rewards-ink-soft`|`#7fc9d4`|
|`--color-rewards-chip`|`#d5eaec`|
|`--color-rewards-wash`|`#f4fafb`|
|`--color-rewards-chip-ink-soft`|`#8fd0da`|
|`--color-playbooks-accent`|`#14b8a6`|

rewards-hover와 rewards-hover-dark는 둘 다 foundation에 등록된 서로 다른 값이다. 이름에 dark가 포함됐다는 이유만으로 root dark 전환 시 자동 선택된다고 가정하면 안 된다. 실제 소비 규칙이 필요하다. 나머지 rewards와 playbooks 값도 관측된 상수와 이름만 기록하며 미관측 화면의 색상 배치를 추정하지 않는다.

### F7. Typography

#### 7.1 Font family와 로딩 경계

|토큰|원값|
|---|---|
|`--font-sans`|`ui-sans-serif, system-ui, sans-serif, "Apple Color Emoji", "Segoe UI Emoji", "Segoe UI Symbol", "Noto Color Emoji"`|
|`--font-serif`|`ui-serif, Georgia, Cambria, "Times New Roman", Times, serif`|
|`--font-mono`|`"Geist Mono", ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace`|
|`--default-font-family`|`var(--font-sans)`|
|`--default-mono-font-family`|`var(--font-mono)`|

저장된 body font-family는 `Inter, system-ui, -apple-system, "Segoe UI", Roboto, sans-serif`다. font-sans의 원 스택과 body에 실제 지정된 스택을 각각 남긴다. Inter의 font-face는 normal, weight 400 700, font-display swap이며 Latin, Latin Extended, Cyrillic, Cyrillic Extended 하위 집합이 등록되어 있다. Geist Mono는 normal, weight 100 900, swap으로 등록된다.

계산 스타일 캡처의 폰트 목록에는 Inter 한 항목이 loaded, 나머지 세 항목이 unloaded, Geist Mono가 unloaded로 나타난다. 어느 글리프가 최종적으로 어떤 폰트로 표시됐는지까지 확인한 것은 아니다. 추출된 face의 unicode-range에는 한글 음절 범위가 없으므로 한국어용 Inter 지원을 주장하지 않는다. 한국어의 실제 fallback 폰트와 코드 영역의 mono 사용 여부는 별도 관측이 필요하다.

#### 7.2 일반 text 크기

|크기 토큰|font-size 원값|16px 기준 크기|line-height 원값|환산 행 높이|
|---|---|---|---|---|
|`--text-xs`|`.75rem`|12px|`calc(1 / .75)`|16px|
|`--text-sm`|`.875rem`|14px|`calc(1.25 / .875)`|20px|
|`--text-base`|`1rem`|16px|`calc(1.5 / 1)`|24px|
|`--text-lg`|`1.125rem`|18px|`calc(1.75 / 1.125)`|28px|
|`--text-xl`|`1.25rem`|20px|`calc(1.75 / 1.25)`|28px|
|`--text-2xl`|`1.5rem`|24px|`calc(2 / 1.5)`|32px|
|`--text-3xl`|`1.875rem`|30px|`calc(2.25 / 1.875)`|36px|
|`--text-4xl`|`2.25rem`|36px|`calc(2.5 / 2.25)`|40px|
|`--text-5xl`|`3rem`|48px|`1`|48px|
|`--text-6xl`|`3.75rem`|60px|`1`|60px|

행 높이는 size와 line-height를 함께 사용했을 때의 산술 결과다. 크기 토큰만 선언돼 있다고 모든 요소가 해당 행 높이를 자동 적용한다고 단정하지 않는다. 일반 5xl과 6xl은 line-height 1이며 다른 단계의 calc 원식도 정확히 보존한다.

#### 7.3 Message 계열

|크기 토큰|font-size 원값|16px 기준 크기|line-height 원값|환산 행 높이|
|---|---|---|---|---|
|`--text-msg-h1`|`1rem`|16px|`1.375`|22px|
|`--text-msg-h2`|`.9375rem`|15px|`1.375`|20.625px|
|`--text-msg-code`|`.8125rem`|13px|`1.5`|19.5px|

msg-h1은 16px, msg-h2는 15px로 일반 헤딩보다 작은 별도 규모다. 이름에 h1이 있다는 이유로 doc-h1과 같은 36px를 부여하지 않는다. 이 값만으로 실제 메시지 마크업의 heading 태그나 시맨틱 계층을 확정할 수는 없다.

#### 7.4 Document 계열

|크기 토큰|font-size 원값|16px 기준 크기|line-height 원값|환산 행 높이|
|---|---|---|---|---|
|`--text-doc-body`|`1rem`|16px|`1.5`|24px|
|`--text-doc-h1`|`2.25rem`|36px|`1.1112`|40.0032px|
|`--text-doc-h2`|`1.5rem`|24px|`1.3334`|32.0016px|
|`--text-doc-h3`|`1.25rem`|20px|`1.4`|28px|
|`--text-doc-h4`|`1.125rem`|18px|`1.4445`|26.001px|
|`--text-doc-code`|`.8125rem`|13px|`1.5`|19.5px|

doc-h1의 line-height 1.1112는 36px 기준 40.0032px다. h2는 32.0016px, h4는 26.001px로 환산된다. 의도상 둥근 수치처럼 보이더라도 원 선언을 40px, 32px, 26px 고정값으로 바꿔 쓰지 않는다. 근사 표시가 필요하면 원값과 근삿값을 명확히 구분한다.

#### 7.5 Static 계열

|크기 토큰|font-size 원값|16px 기준 크기|line-height 원값|환산 행 높이|
|---|---|---|---|---|
|`--text-static-3xs`|`.5rem`|8px|`1`|8px|
|`--text-static-2xs`|`.625rem`|10px|`1`|10px|
|`--text-static-xs`|`.75rem`|12px|`1`|12px|
|`--text-static-sm`|`.875rem`|14px|`1`|14px|
|`--text-static-base`|`1rem`|16px|`1`|16px|
|`--text-static-lg`|`1.125rem`|18px|`1`|18px|
|`--text-static-xl`|`1.25rem`|20px|`1`|20px|
|`--text-static-2xl`|`1.5rem`|24px|`1`|24px|
|`--text-static-3xl`|`1.875rem`|30px|`1`|30px|
|`--text-static-4xl`|`2.25rem`|36px|`1`|36px|

static은 모든 관측 단계의 line-height가 1이다. 일반 text와 크기가 같아도 행 높이가 다르다. 8px와 10px 단계가 존재한다는 사실은 확인되지만 본문, 법적 고지, 버튼 레이블에 사용해도 적절하다는 권고는 아니다. 작은 글자 사용처나 접근성 판단은 이 추출 범위에서 검증되지 않았다.

#### 7.6 Weight, tracking, leading

|토큰|원값|
|---|---|
|`--font-weight-normal`|`400`|
|`--font-weight-medium`|`500`|
|`--font-weight-semibold`|`600`|
|`--font-weight-bold`|`700`|
|`--tracking-tight`|`-.025em`|
|`--tracking-normal`|`0em`|
|`--tracking-wide`|`.025em`|
|`--tracking-widest`|`.1em`|
|`--leading-tight`|`1.25`|
|`--leading-snug`|`1.375`|
|`--leading-normal`|`1.5`|
|`--leading-relaxed`|`1.625`|

weight 토큰과 폰트 파일의 지원 범위를 혼동하지 않는다. Geist Mono의 100~900 지원 선언이 곧 제품이 모든 weight를 사용한다는 뜻은 아니다. tracking은 em 단위라 글자 크기에 비례한다. leading 토큰은 비율값이며 msg/doc/static의 개별 line-height를 무시하는 상위 규칙으로 해석하지 않는다.

### F8. Spacing, container, control

기준 spacing은 `--spacing: .25rem`이며 root 16px에서 4px다. 이 한 값에서 모든 화면의 padding과 gap이 몇 배수를 사용한다고 역으로 확정할 수는 없다. 토큰 기반 계산을 설명할 때에도 실제 추출된 표현식과 단순한 수학적 가능성을 분리한다.

|토큰|원값|16px 기준 환산|
|---|---|---|
|`--container-xs`|`20rem`|320px|
|`--container-sm`|`24rem`|384px|
|`--container-md`|`28rem`|448px|
|`--container-lg`|`32rem`|512px|
|`--container-xl`|`36rem`|576px|
|`--container-2xl`|`42rem`|672px|
|`--container-3xl`|`48rem`|768px|
|`--container-4xl`|`56rem`|896px|
|`--container-5xl`|`64rem`|1024px|
|`--container-6xl`|`72rem`|1152px|

container 값은 크기 자원이다. 현재 화면의 실제 콘텐츠 폭, breakpoint, max-width 적용 여부가 아니다. 값이 작은 것부터 큰 것까지 나열돼 있어도 responsive 전환 기준으로 재해석하지 않는다.

|역할|root 기본값|onboarding 로컬값|
|---|---|---|
|control-field-height|`2rem` = 32px|`calc(var(--spacing) * 10)` = 40px|

control-field-height의 차이는 실제 원 선언이다. 다만 이 토큰을 참조하는 모든 입력창이나 버튼을 조사한 것은 아니므로 전역 버튼 높이가 32px이고 onboarding 버튼 높이가 40px라고 일반화하지 않는다. 화면 컴포넌트의 임의 치수는 이 Foundations에 추가하지 않는다.

### F9. Radius, hairline, blur, aspect

|토큰|원값|16px 기준 또는 해석|
|---|---|---|
|`--radius-xs`|`.25rem`|4px|
|`--radius-sm`|`.5rem`|8px|
|`--radius-md`|`.75rem`|12px|
|`--radius-lg`|`1rem`|16px|
|`--radius-xl`|`1.25rem`|20px|
|`--radius-2xl`|`1.5rem`|24px|
|`--radius-3xl`|`1.75rem`|28px|
|`--radius`|`.5rem`|8px|
|`--radius-avatar`|`37.5%`|백분율 값 그대로|

avatar의 37.5%는 50% 원형과 다르다. 백분율 곡률은 해당 상자의 치수에 영향을 받으므로 특정 px 반경으로 고정 변환하지 않는다. 기본 radius 0.5rem과 radius-sm 0.5rem이 동일해도 이름별 실제 사용처는 현재 자료로 확정되지 않는다. 관측된 radius에는 테마별 재정의가 없다.

원 규칙은 context `(resolution >= 2x)`의 `:root { --hairline: .5px; }`다. 캡처 DPR 2는 이 조건과 부합한다. 조건 바깥에서도 0.5px라고 문서화해서는 안 된다. raised의 `var(--hairline,1px)`에는 hairline이 유효하게 정의되지 않았을 때 1px를 쓰는 fallback이 있다. 이를 모든 border의 기본 두께로 확대하지 않는다.

|토큰|원값|
|---|---|
|`--blur-xs`|`4px`|
|`--blur-sm`|`8px`|
|`--aspect-video`|`16 / 9`|

blur 4px와 8px는 독립 원값이며 어떤 배경이나 overlay에 적용됐는지까지 증명하지 않는다. aspect-video 16 / 9도 비율 자원일 뿐 실제 카드, 비디오 또는 미디어 요소의 존재나 화면 크기를 뜻하지 않는다.

### F10. Elevation과 shadow

|토큰|기본 light 선언|root dark 유효 선언|onboarding 로컬 선언|
|---|---|---|---|
|`--elevation-2xs`|`0 1px #0000000d`|`0 1px 2px #00000040`|`0 1px #0000000d`|
|`--elevation-xs`|`0 1px 2px #0000000d`|`0 1px 3px #0000004d`|`0 1px 2px #0000000d`|
|`--elevation-sm`|`0 1px 3px #0000001a, 0 1px 2px -1px #0000001a`|`0 1px 3px #00000059, 0 1px 2px -1px #00000059`|`0 1px 3px #0000001a, 0 1px 2px -1px #0000001a`|
|`--elevation-md`|`0 4px 6px -1px #0000001a, 0 2px 4px -2px #0000001a`|`0 4px 6px -1px #0006, 0 2px 4px -2px #00000059`|`0 4px 6px -1px #0000001a, 0 2px 4px -2px #0000001a`|
|`--elevation-lg`|`0 10px 15px -3px #0000001a, 0 4px 6px -4px #0000001a`|`0 10px 15px -3px #00000073, 0 4px 6px -4px #0006`|`0 10px 15px -3px #0000001a, 0 4px 6px -4px #0000001a`|
|`--elevation-xl`|`0 20px 25px -5px #0000001a, 0 8px 10px -6px #0000001a`|`0 20px 25px -5px #00000080, 0 8px 10px -6px #0006`|`0 20px 25px -5px #0000001a, 0 8px 10px -6px #0000001a`|
|`--elevation-2xl`|`0 25px 50px -12px #00000040`|`0 25px 50px -12px #0009`|`0 25px 50px -12px #00000040`|
|`--raised`|`0 0 0 var(--hairline,1px) #0000000d, 0 1px 3px #0000001f`|`0 0 0 var(--hairline,1px) #0003, 0 2px 4px #0000004d`|`0 0 0 var(--hairline,1px) #0000000d, 0 1px 3px #0000001f`|

여러 shadow 성분은 쉼표로 구분된 원값 그대로 보존한다. light에서 dark로 바뀔 때 alpha만 바뀌는 것은 아니다. 2xs는 light의 `0 1px`에서 dark의 `0 1px 2px`가 되고 xs도 blur가 2px에서 3px로 달라진다. raised의 낙하 성분 역시 light의 `0 1px 3px`와 dark의 `0 2px 4px`가 다르다.

raised의 첫 성분은 offset과 blur가 0인 경계형 shadow이며 spread 자리에 hairline을 사용한다. 따라서 단일 낙하 shadow와 구분한다. onboarding은 elevation과 raised 원천값을 light와 동일하게 재선언하지만 shadow 별칭을 로컬에서 재선언하지는 않는다. 실제 소비 속성이 어느 토큰을 참조하는지에 따라 이 차이가 중요해진다.

|토큰|원값|
|---|---|
|`--shadow-2xs`|`var(--elevation-2xs)`|
|`--shadow-xs`|`var(--elevation-xs)`|
|`--shadow-sm`|`var(--elevation-sm)`|
|`--shadow-md`|`var(--elevation-md)`|
|`--shadow-lg`|`var(--elevation-lg)`|
|`--shadow-xl`|`var(--elevation-xl)`|
|`--shadow-2xl`|`var(--elevation-2xl)`|
|`--shadow-raised`|`var(--raised)`|

단계 이름을 modal, dropdown, tooltip 같은 미관측 컴포넌트에 임의 배정하지 않는다. z-index, 표면의 실제 겹침 순서, 그림자의 clip 여부는 이 값에서 도출할 수 없다. dark shadow가 수치상 더 진하다는 사실만으로 모든 배경에서 더 잘 구분된다고 평가하지 않는다.

### F11. Motion과 transition

|토큰|원값|
|---|---|
|`--ease-in`|`cubic-bezier(.4, 0, 1, 1)`|
|`--ease-out`|`cubic-bezier(0, 0, .2, 1)`|
|`--ease-in-out`|`cubic-bezier(.4, 0, .2, 1)`|
|`--default-transition-duration`|`.15s`|
|`--default-transition-timing-function`|`cubic-bezier(.4, 0, .2, 1)`|
|`--animate-spin`|`spin 1s linear infinite`|
|`--animate-pulse`|`pulse 2s cubic-bezier(.4, 0, .6, 1) infinite`|
|`--animate-text-shimmer`|`text-shimmer 2.4s linear infinite`|
|`--animate-message-highlight`|`message-highlight 6.5s ease-out forwards`|

default-transition-duration은 0.15s, 즉 150ms다. spin은 1초 linear infinite, pulse는 2초의 지정 cubic-bezier infinite, text-shimmer는 2.4초 linear infinite, message-highlight는 6.5초 ease-out forwards다. duration, easing, 반복, 종료 후 유지 옵션을 구분한다. `forwards`는 종료 후 마지막 keyframe 스타일을 유지하는 옵션이지 모든 highlighting 상태의 지속 시간을 직접 보증하는 것은 아니다.

이 자료에는 위 이름의 전체 keyframes 본문이 없다. 움직임의 방향, 이동 거리, opacity 범위, shimmer의 밝기, pulse의 정확한 시각 패턴을 복원했다고 주장하지 않는다. reduced-motion 지원 여부, hover 전환의 적용 속성, 애니메이션이 실행되는 화면도 미검증이다. 저장된 `--tw-animation-*` 기본값을 제품 전체의 motion 정책으로 끌어올리지 않는다.

### F12. 별칭 상속과 scoped light의 주의점

#### 12.1 같은 요소의 cascade와 자손 상속은 다르다

root에 `--shadow-xs: var(--elevation-xs)`가 있고 root.dark가 같은 요소에서 elevation-xs를 바꾸면 root의 별칭은 그 요소에서 cascade된 dark elevation을 기준으로 계산될 수 있다. 반면 계산된 별칭이 자손으로 상속된 뒤 자손이 elevation-xs만 light로 바꾼다고 상속된 shadow-xs가 새 참조식으로 자동 재실행되지는 않는다. 일반적인 사용자 정의 속성의 계산 시점과 상속을 구분해야 한다.

이 규칙은 테마가 바뀌는 같은 root와 root 아래에 부분적으로 추가되는 onboarding scope를 구분하는 핵심이다. 원 텍스트에 var가 남아 있는 것과 상속된 computed value가 아직 참조를 유지한다는 것은 같은 의미가 아니다. 정의 파일의 문자열만 검색해서 모든 별칭이 정상적으로 로컬 토큰을 따라간다고 결론 내리지 않는다.

#### 12.2 우선 검토할 별칭

|별칭|원천 참조|onboarding 해석상 주의|
|---|---|---|
|--shadow-2xs ~ --shadow-2xl|대응 --elevation-*|원천만 로컬 재정의되며 별칭 재선언은 추출되지 않음|
|--shadow-raised|--raised|같은 상속 주의가 적용됨|
|`--color-border`|`var(--border)`|border와 상속된 별칭이 서로 다른 테마값일 수 있음|
|`--color-muted-foreground`|`var(--muted-foreground)`|로컬 원천과 상속된 별칭을 구분|
|--foreground-strong|root dark에서는 --color-oat-50|로컬 foreground가 어두워져도 strong은 미재정의|
|--destructive-accent|root dark에서는 --destructive|로컬 destructive가 상속된 accent를 자동 변경하지 않음|

이 표는 CSS 의미에서 확인해야 할 경계를 기술한다. 실제 onboarding에서 어두운 그림자나 대비 문제가 발생했다는 관측 보고는 아니다. 정확한 판정에는 소비 속성, 요소의 scope 소속, 최종 computed style이 필요하다. 별칭을 scope 안에서 다시 연결하거나 소비 속성이 로컬 원천을 직접 참조하도록 설계할 수는 있지만 이는 검토 권고이며 현재 구현 사실은 아니다.

#### 12.3 Scope 밖 요소의 경계

scoped light는 해당 요소와 그 상속 범위에 대한 규칙이다. 별도 DOM 위치에 렌더링되는 요소가 있다면 같은 scope를 공유하는지 확인해야 한다. 토큰 자료만으로 portal 구현을 확정하지 않는다. 별도 화면 관측에서는 Connect app 모달의 최종 computed style이 dark인 것을 확인했으며 앞쪽 모달 장에 기록했다. 다만 테마 검증에는 화면상의 근접성과 DOM 상속 범위가 다를 수 있다는 점을 포함한다.

### F13. 검증 상태와 문서 사용 원칙

**확인된 것:** 원 토큰 문자열, 추출된 selector와 context, 정의 파일의 그룹별 항목, root/body 계산값, 저장된 환경, font-face 등록과 폰트 목록의 상태다. 선언값과 계산값을 서로 바꾸어 표현하지 않는다. OKLCH의 백분율 표기와 계산 스타일의 0~1 표기는 동일 의미일 수 있지만 원 근거의 직렬화를 문서에서 구분한다.

**산술로 도출한 것:** root 16px 기준의 rem→px, 토큰 size와 line-height의 곱, 0.15s→150ms, spacing 곱에 따른 control 높이다. 모두 실제 요소 측정과 구분한다. 근거에서 직접 읽은 값과 계산 결과를 분리해 두면 다른 root 크기나 환경에서 검토를 반복하기 쉽다.

**이 Foundations의 토큰 자료만으로 미검증인 것:** 개별 컴포넌트의 padding, gap, width, height, border 두께, 아이콘 크기, hover/focus/disabled/selected 상태, 반응형 breakpoint, 키보드 접근성, 대비 적합성, 포커스 가시성, 모션 저감 대응, 각 domain 이름의 업무 의미, onboarding 모든 자손의 최종 스타일이다. 이는 부재나 결함의 확정이 아니라 현재 근거의 경계다.

후속 검증에서는 root dark와 onboarding scope를 별도 대상으로 잡고 소비되는 토큰과 computed style을 연결해야 한다. 특히 border와 color-border, elevation과 shadow 별칭, foreground와 foreground-strong처럼 부분 재정의에서 분기되는 관계를 우선 확인한다. chart와 상태색의 접근성은 실제 배경과 사용 맥락으로 검사하고 폰트는 한국어와 코드 글리프를 별도로 관측한다.

이 Foundations는 원값을 보존한 출발점이다. 새로운 컴포넌트 치수나 상태를 추가하려면 별도의 관측 근거를 연결하고 제안값은 추출값과 명확히 구별해야 한다. 전체 제품의 공식 규칙이라는 표현은 소유자 문서 등 추가 근거가 확인되기 전까지 사용하지 않는다.


---

## 부록 B. 관측·키트 검증 기록

- HTML: 14개 섹션 / 407개 그룹별 선언 / 293개 고유 변수 / sourceRules 68개 확인.
- HTML viewport 1440 / 768 / 640 / 390px에서 문서 가로 넘침 없음.
- Light / Dark / Onboarding 전환, radio 방향키, 자동완성 검색·선택·자유 입력, 모달 검색·빈 상태·clear·Escape·포커스 복귀 확인.
- CSS·JSON 다운로드 버튼을 로컬 Blob 캡처로 확인: CSS 원본 일치, JSON 원 규칙 68개 포함. 사용자의 Downloads에는 중복 파일을 만들지 않음.
- React 19.3.1 + TypeScript 7.0.2: strict 타입 검사 통과. React StrictMode 브라우저 실행 확인.
- React TextField 오류, disabled 옵션 건너뛰기, 편집 가능한 combobox, dark 모달, Escape 닫기와 포커스 복귀 확인.
- React native dialog: desktop 896px, 390px mobile에서 358px / radius 0 확인.
- 관측한 테스트 동안 runtime error 및 console.error 없음.
- 원본 캡처 16개: 실제 MIME·파일 존재·이미지 로딩 16/16 확인. 전환 중 캡처는 별도 표기.
- 원본 Ramus는 최초 1단계 미선택 상태로 복구. 외부 연결·초대 전송·최종 완료 미실행.
- 자동화된 완전한 접근성 감사, 모든 브라우저·기기·IME·스크린리더 검증은 미실행.

