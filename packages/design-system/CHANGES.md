# 키트 소스 수정 기록

`src/`의 키트 파일에 가한 모든 변경을 적는다. 원본은 `Ramus-Design-System-v2` 키트(사용자 제공)다. 키트를 다시 들여올 때는 이 목록대로 같은 수정을 다시 적용한다. 키보드·ARIA 동작은 바꾸지 않았고 사용자에게 보이는 영어 문구와 영어 기본 prop 값만 한국어로 바꿨다.

## 수정하지 않은 것

- `RamusCatalog.tsx`, `catalog.css`, `ramus*.css`, `index.ts`, `RamusComponents.tsx`(이미 한국어), `ramus-env.d.ts`는 원본 그대로다.
- 타입 오류 수정은 없다. 키트는 TypeScript 7로만 검사됐지만 이 저장소의 TypeScript 5.9 `tsc -b`를 오류 없이 통과했다.
- `COMPOSER_FORMATS`의 값("Bold" 등)은 API 식별자라서 영어로 둔다. 화면에 보이는 이름만 아래 `COMPOSER_FORMAT_LABELS`로 한국어화했다.

## 수정 목록

### `src/RamusPrimitives.tsx`

| 대상 | 변경 | 이유 |
| --- | --- | --- |
| `Avatar` `presenceLabel` 기본값 | `"Online"` → `"온라인"` | 접근성 이름에 들어가는 기본 문구 |
| `Select` `searchPlaceholder`, `placeholder`, `emptyLabel` 기본값 | `"Search options"` / `"Select"` / `"No matches"` → `"옵션 검색"` / `"선택"` / `"일치하는 항목이 없습니다"` | 기본 UI 문구 |
| `Spinner` `label` 기본값 | `"Loading"` → `"불러오는 중"` | 스크린리더 상태 문구 |

### `src/RamusPatterns.tsx`

| 대상 | 변경 | 이유 |
| --- | --- | --- |
| `PrincipalCell` | `"Unavailable"` / `"Unknown"` → `"사용할 수 없음"` / `"알 수 없음"` | 화면 문구 |
| `Chip` 제거 버튼 | ``Remove ${label}``(대체값 `"item"`) → ``${label} 제거``(대체값 `"항목"`) | 접근성 이름. 한국어 어순 |
| `Toolbar` `label` 기본값 | `"Toolbar"` → `"도구 모음"` | 접근성 이름 |
| `InputOTP` `label` 기본값 | `"One-time code"` → `"일회용 코드"` | 기본 라벨 |
| `MultiSelect` 기본값 | `label "Select items"`, `placeholder "Search options"`, `emptyLabel "No options found"` → `"항목 선택"`, `"옵션 검색"`, `"옵션이 없습니다"` | 기본 UI 문구 |
| `MultiSelect` 버튼 | `"Clear selection"` → `"선택 해제"`, `"Close options"`/`"Open options"` → `"옵션 닫기"`/`"옵션 열기"` | 접근성 이름 |
| `Calendar` | `locale` 기본값 `"en-US"` → `"ko-KR"`, `"Today"` → `"오늘"`, `"Previous month"`/`"Next month"` → `"이전 달"`/`"다음 달"` | 월·요일·날짜 표기와 버튼 문구 |
| `DateTimeEditor` | `label "Date"` → `"날짜"`, `"Choose date"` → `"날짜 선택"`, `"Time"` → `"시간"` | 기본 UI 문구 |
| `DataGridLite` | `label "Data"` → `"데이터"`, `emptyLabel "No rows"` → `"행이 없습니다"`, `"Filter rows"` → `"행 필터"`, `"Select visible rows"` → `"표시된 행 모두 선택"`, ``Select row ${key}`` → ``${key} 행 선택``, `"Loading rows"` → `"행을 불러오는 중"`, ``${n} rows, ${m} selected`` → ``${n}개 행, ${m}개 선택됨`` | 기본 UI 문구와 상태 안내 |
| `Breadcrumbs` `label` 기본값 | `"Breadcrumb"` → `"이동 경로"` | 접근성 이름 |
| `ResizablePanels` | `label "Resize panels"` → `"패널 크기 조절"`, `aria-valuetext` ``${n} percent`` → ``${n}퍼센트`` | 접근성 이름과 값 문구 |
| `FileCard` | `"File"` → `"파일"`, `"Uploading"`/`"Unable to upload"` → `"업로드 중"`/`"업로드할 수 없음"`, ``Remove ${name}`` → ``${name} 제거`` | 화면 문구와 접근성 이름 |
| `SearchCommand` 기본값 | `label "Search commands"`, `placeholder "Search"`, `emptyLabel "No results"` → `"명령 검색"`, `"검색"`, `"결과가 없습니다"` | 기본 UI 문구 |
| `COMPOSER_FORMAT_LABELS` 추가 | `ComposerFormat` 식별자별 한국어 이름(굵게, 기울임, 밑줄, 취소선, 링크, 번호 목록, 글머리 기호 목록, 인용, 인라인 코드, 코드 블록) | 식별자는 유지하고 표시 이름만 분리하려고 추가한 새 export |
| `ComposerToolbar` | 서식 버튼 `aria-label`/`title`을 `COMPOSER_FORMAT_LABELS`로, 링크 버튼 글자 `"Link"` → `"링크"`, 도구 모음 `"Message formatting"` → `"메시지 서식"`, `"Mention"`/`"Emoji"` → `"멘션"`/`"이모지"`, `"Link URL"` → `"링크 주소"`, `"Use link"` → `"링크 사용"`, `"Cancel"` → `"취소"`, 검색 라벨 `"Mention someone"`/`"Search emoji names"` → `"멘션할 사람 검색"`/`"이모지 이름 검색"` | 화면 문구와 접근성 이름 |

### `src/RamusAdvanced.tsx`

| 대상 | 변경 | 이유 |
| --- | --- | --- |
| `ActionSheet` `cancelLabel` 기본값 | `"Cancel"` → `"취소"` | 기본 버튼 문구 |
| `IconColorPicker` | `searchLabel "Search icons"`, `emptyLabel "No icons found"` → `"아이콘 검색"`, `"아이콘이 없습니다"`, 색상 그룹 `aria-label "Icon color"` → `"아이콘 색상"` | 기본 UI 문구와 접근성 이름 |
| `AlertDialog` 기본값 | `confirmLabel "Confirm"`, `cancelLabel "Cancel"`, `errorLabel "The action could not be completed."` → `"확인"`, `"취소"`, `"작업을 완료하지 못했습니다."` | 기본 버튼과 오류 문구 |
| `StatusDialog` 기본값 | `title "Set a status"`, `textLabel "Status"`, `expiryLabel "Clear after"`, `saveLabel "Save"`, `cancelLabel "Cancel"`, `clearLabel "Clear status"`, `errorLabel "The status could not be updated."` → `"상태 설정"`, `"상태"`, `"지울 시점"`, `"저장"`, `"취소"`, `"상태 지우기"`, `"상태를 업데이트하지 못했습니다."` | 기본 UI 문구 |
| `Toast` `dismissLabel` 기본값 | `"Dismiss"` → `"닫기"` | 기본 버튼 문구 |
| `Toaster` `label` 기본값 | `"Notifications"` → `"알림"` | 접근성 이름 |
| `FileDropzone` `chooseLabel` 기본값 | `"Choose files"` → `"파일 선택"` | 기본 버튼 문구 |

## 의도적으로 영어로 남긴 것

- `RamusAdvanced.tsx`의 `"Files"`는 브라우저 `DataTransfer.types` 값이라 번역하지 않는다.
- 키보드 키 이름(`"Escape"`, `"Enter"` 등)과 CSS 클래스·역할 이름은 코드 값이다.
- `RamusCatalog.tsx`와 `catalog.css`는 개발용 카탈로그라서 손대지 않았다. 카탈로그 안의 `./references/index.html` 링크는 `references/`를 가져오지 않았으므로 연결되지 않는다.
