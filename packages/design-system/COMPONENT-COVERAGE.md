# Ramus Design System v2 컴포넌트 Coverage

## 1. 이 문서가 보장하는 범위

확인 가능한 공개 정적 정의와 접근한 UI 범위에서 최대한 회수하고, React로 독립 재구성했다. **공식 원본 컴포넌트 패키지, 앱 전체 UI 전수 획득, 원본 동작과의 완전한 동등성을 보장하지 않는다.** 원본 JS를 대량 재배포한 결과물이 아니다.

원본 정적 정의, 실제 UI 관측, 재구성 구현, 접근성 추가를 따로 기록했다. 버튼·메뉴를 화면에서 관측했다고 해서 서버 액션이나 모든 keyboard 동작까지 검증한 것은 아니다.

### 수량을 읽는 방법

- 원정의 인벤토리: **30개 근거 그룹**, 공개 JS **22개** 확인. 24·25는 MultiSelect picker/listbox의 두 근거이므로 합치면 편집상 **29개 source API family**다. 공식 라이브러리의 family 총수라는 뜻은 아니다.
- 현재 4개 TSX의 **값 export 73개 = 9 + 19 + 29 + 16**. type/interface exports는 제외했다. `COMPOSER_FORMATS` 상수 1개, `RamusProvider`/`Demo`, `TableHead` 같은 서브래퍼가 포함되므로 **73개 컴포넌트 family**라고 부르면 안 된다.
- Table은 family 1개에 wrapper subexports 8개, Toolbar는 family 1개에 기본 subexports 3개다. 원정의 여러 subAPI가 재구성에서는 통합 props API로 축약되었다.
- 원본 캡처는 **64개 = 기존 16 + 추가 48**. 추가 실측 JSON은 48개이며 52는 nodes=0이다. 캡처 수를 서로 다른 컴포넌트 수로 해석하지 않는다.
- raw CSS **537건은 selector/선언값 근거**다. 537 components가 아니다.

## 2. 근거 레벨과 완전성 기준

- **정적 확인:** 실제 공개 JS에서 render/props/style 정의를 읽었다. 런타임 노출을 의미하지 않는다. 모든 아래 30행에 해당한다.
- **UI 관측:** 캡처·실측 또는 AX에서 실제 표면을 확인했다. 시각적으로 유사한 조합만 있으면 component identity를 특정하지 않는다.
- **UI-only 재구성:** 로컬 상태, callback과 native 요소로 구현했다. 서버·인증·저장·업무 실행은 연결하지 않았다.
- **접근성 재구성:** role/ARIA/keyboard/dismiss/focus 처리를 코드에 추가했다. 원본 동작을 관측했다거나 WCAG 인증을 받았다는 뜻이 아니다.
- **부분 대응:** 대표 동작을 제공하되 원본 subAPI·엔진 기능은 제외했다. 특히 DateTime/Calendar/TableGrid/ScrollArea가 여기에 해당한다.

## 3. 원정의 30그룹 대조표

UI 번호는 원본 캡처 링크다. 이미지의 계정 텍스트는 여기 복제하지 않았다. 모든 구현은 UI-only 독립 재구성이다.

| # / 원정의 | 공개 source asset | UI 관측 번호·상태 | 대응 export | 구현 완전성·제공 범위 | 접근성 재구성 | 미지원·주의 |
|---|---|---|---|---|---|---|
| 1. Button | [button-BRocK4d0.js](https://app.hops.ai/assets/button-BRocK4d0.js) | [17](references/screenshots/17-app-shell-chat.png), [18](references/screenshots/18-user-menu.png), [20](references/screenshots/20-profile-edit-form.png), [22](references/screenshots/22-new-item-menu.png), [30](references/screenshots/30-composer-format-toolbar.png), [34](references/screenshots/34-settings-general.png), [51](references/screenshots/51-calendar-popup.png), [54](references/screenshots/54-destructive-alert-dialog.png), [60](references/screenshots/60-status-dialog.png)<br>직접 UI 관측. 모든 variant/size 조합을 관측한 것은 아님 | `Button`, `ButtonV2` | **핵심 스타일·native 동작 재구성**<br>ButtonV2: 7 variants(default/destructive/outline/secondary/ghost/link/text), 7 sizes(default/xs/sm/lg/icon/icon-sm/icon-lg). 기존 Button은 별도 간소 API | native button, type=button 기본, disabled, focus-visible | 원본 asChild/Slot API 미재현; 백엔드 액션 없음; 7 variants × 7 sizes의 전수 시각 검증 아님 |
| 2. Input | [tooltip-DgbuciXR.js](https://app.hops.ai/assets/tooltip-DgbuciXR.js) | [20](references/screenshots/20-profile-edit-form.png), [23](references/screenshots/23-create-space-form.png), [24](references/screenshots/24-icon-color-picker.png), [31](references/screenshots/31-link-popover.png), [36](references/screenshots/36-users-table.png), [41](references/screenshots/41-custom-date-range.png), [50](references/screenshots/50-date-time-editor.png), [60](references/screenshots/60-status-dialog.png)<br>직접 slot=input 및 native input 관측 | `InputV2`, `TextField` | **native 입력 래퍼 재구성**<br>InputV2 native props/ref, TextField label/hint/error 조합 | label 연결, describedBy/invalid는 API 또는 native props로 전달 | 원본 모든 입력 타입별 브라우저 외관·validation 동일성 미보장; 서버 검증 없음 |
| 3. Label | [tooltip-DgbuciXR.js](https://app.hops.ai/assets/tooltip-DgbuciXR.js) | [20](references/screenshots/20-profile-edit-form.png), [23](references/screenshots/23-create-space-form.png), [41](references/screenshots/41-custom-date-range.png), [58](references/screenshots/58-playbook-detail.png), [60](references/screenshots/60-status-dialog.png)<br>직접 slot=label 및 LABEL 관측 | `LabelV2` | **native label 재구성**<br>htmlFor 등 native label props/ref | 표준 label/입력 연결은 소비자가 id와 htmlFor 제공 | 원본 label primitive의 모든 peer/group 상태 자동 재현 아님 |
| 4. Checkbox | [checkbox-CeZ5BQbX.js](https://app.hops.ai/assets/checkbox-CeZ5BQbX.js) | 없음<br>정적 정의 확인, 이번 실측에서 standalone Checkbox 직접 노출 미확인 | `Checkbox` | **상태 UI 재구성, 정적 근거 기반**<br>boolean/indeterminate, controlled/defaultChecked, native input | mixed 상태, native checkbox 키보드, disabled; form reset은 호스트 관리 | 프로덕션 Checkbox 상태 전환 실동작 미관측; 앱 저장·폼 reset 자동 동기화 없음 |
| 5. Select | [select-C8hjZ6mU.js](https://app.hops.ai/assets/select-C8hjZ6mU.js) | [20](references/screenshots/20-profile-edit-form.png), [21](references/screenshots/21-searchable-single-select.png), [34](references/screenshots/34-settings-general.png), [35](references/screenshots/35-theme-select.png), [39](references/screenshots/39-usage-summary.png), [40](references/screenshots/40-period-select.png), [49](references/screenshots/49-automation-trigger-select.png), [58](references/screenshots/58-playbook-detail.png), [60](references/screenshots/60-status-dialog.png)<br>단일선택 trigger/listbox/option 직접 관측 | `Select` | **통합 API로 핵심 기능 재구성**<br>단일선택, 검색 옵션, empty, typeahead, controlled/defaultValue, hidden form value | combobox/listbox/option, 방향키·Home/End·Enter/Space·Escape, IME guard, disabled 건너뛰기 | Trigger/Content/Item 등 원본 subexport 별도 공개 안 함; popper/portal/collision/scroll-button API 미재현 |
| 6. DropdownMenu | [dropdown-menu-D4MPvagG.js](https://app.hops.ai/assets/dropdown-menu-D4MPvagG.js) | [18](references/screenshots/18-user-menu.png), [22](references/screenshots/22-new-item-menu.png), [29](references/screenshots/29-sort-radio-menu.png), [37](references/screenshots/37-filter-radio-items.png), [43](references/screenshots/43-activity-type-menu.png), [53](references/screenshots/53-delete-draft-menu.png)<br>menu/menuitem 직접 관측. 37·43은 menuitemradio; 29는 일반 menuitem | `DropdownMenu` | **데이터 기반 통합 메뉴 재구성**<br>action/checkbox/radio/submenu/label/separator 항목, controlled open | menu 역할·checked 상태, 방향키/서브메뉴 이동/typeahead/Escape/focus 복원 | 원본 root/subcontent별 조립 API 미재현; shortcut 문자열은 표시만; 무한 충돌회피·portal·업무명령 실행 없음 |
| 7. Tooltip | [tooltip-DgbuciXR.js](https://app.hops.ai/assets/tooltip-DgbuciXR.js) | [59](references/screenshots/59-navigation-tooltip.png), [61](references/screenshots/61-mobile-app-shell.png), [62](references/screenshots/62-mobile-chat-sidebar-closed.png)<br>59에서 data-slot=tooltip-content 실제 관측. 해당 측정의 role은 null이며 role=tooltip selector로 찾은 결과는 없음 | `Tooltip` | **관측 스타일 + 접근성 동작 재구성**<br>측면별 tooltip, focus/hover 표시, configurable delay | 구현에서는 role=tooltip 및 aria-describedby를 추가. focus/blur/Escape/timer cleanup | 원본 runtime role을 관측했다고 주장하지 않음; delay 값은 구현 기본값; portal/collision 없음; children은 focus 가능한 요소가 필요 |
| 8. Popover | [open-profile-CLoLVf5-.js](https://app.hops.ai/assets/open-profile-CLoLVf5-.js) | [24](references/screenshots/24-icon-color-picker.png), [31](references/screenshots/31-link-popover.png), [33](references/screenshots/33-emoji-picker-search.png), [51](references/screenshots/51-calendar-popup.png)<br>popover-content slot 및 비모달 popup 실제 관측 | `Popover` | **로컬 overlay 핵심 재구성**<br>controlled/default open, side/align, trigger content와 children | labelled dialog role, focus 진입/Escape/외부 포커스·포인터 닫힘/trigger 복원 | portal 없음, collision/flip/viewport 경계 자동조정 없음, focus trap/aria-modal 없음. 투명하게 배치 엔진까지 재현한 Popover 아님; overflow ancestor에서 잘릴 수 있음 |
| 9. HoverCard | [open-profile-CLoLVf5-.js](https://app.hops.ai/assets/open-profile-CLoLVf5-.js) | [48](references/screenshots/48-automation-draft-editor.png)<br>hover-card-trigger slot 관측만. HoverCard content가 열린 장면은 미확인 | `HoverCard` | **정적 정의 기반 로컬 hover UI**<br>Popover 기반 hover/focus, configurable open/close delay | keyboard focus 열림, Escape 닫힘, timer cleanup | 완전한 원본 hover 동작/지연 실측 없음; portal/collision/focus trap 없음 |
| 10. ScrollArea / ScrollBar | [open-profile-CLoLVf5-.js](https://app.hops.ai/assets/open-profile-CLoLVf5-.js) | 없음<br>정적 ScrollArea/ScrollBar 정의 확인. 스크롤 표면은 있으나 원본 ScrollArea 직접 식별은 미확인 | `ScrollArea` | **native overflow 대체, 부분 구현**<br>vertical/horizontal/both, native scroll, region label | focus 가능한 region과 native 키보드 스크롤 | 원본 커스텀 ScrollBar/Thumb/Corner 및 별도 ScrollBar export 미구현 |
| 11. Textarea | [open-profile-CLoLVf5-.js](https://app.hops.ai/assets/open-profile-CLoLVf5-.js) | [20](references/screenshots/20-profile-edit-form.png)<br>profile 편집 textarea slot, 높이 80px 직접 관측 | `TextareaV2` | **native textarea 재구성**<br>native props/ref, min-height와 resize 스타일 | native textarea 및 외부 label/htmlFor | profile 저장/자동완성/서버 반영 없음; field-sizing 지원은 브라우저별 차이 |
| 12. Avatar-like principal renderer | [use-personal-space-label--9IRlhqb.js](https://app.hops.ai/assets/use-personal-space-label--9IRlhqb.js) | [17](references/screenshots/17-app-shell-chat.png), [18](references/screenshots/18-user-menu.png), [19](references/screenshots/19-profile-dialog.png), [36](references/screenshots/36-users-table.png), [38](references/screenshots/38-groups-empty-state.png)<br>이미지·fallback·presence 형태 관측; 모든 원본 scale 조합의 UI 전수 관측은 아님 | `Avatar`, `UserChip` | **크기·fallback UI 재구성**<br>Avatar 5 scales 16/20/24/32/48px. UserChip md 28px, profile 80px는 별도 실측 override. presence 17은 8px, 18은 10px, 19는 12px | 이미지 오류 fallback, initials, 접근 가능한 name/presence | 자동 사용자 조회·사진 업로드 없음. UserChip 28px를 원본 Avatar md=24px로 혼동하지 않음. away/offline은 추가 UI 상태이지 검증된 원본 상태 전수 아님 |
| 13. UserChip | [user-chip-D9Q7LYMB.js](https://app.hops.ai/assets/user-chip-D9Q7LYMB.js) | [17](references/screenshots/17-app-shell-chat.png), [36](references/screenshots/36-users-table.png), [45](references/screenshots/45-artifact-list.png)<br>avatar+이름 조합 관측. 런타임 React 컴포넌트 identity는 미검증 | `UserChip` | **전달 데이터 기반 사용자 칩**<br>user 객체 입력, size/presence 옵션, 이미지 오류 fallback | 보조 presence 텍스트와 이름 노출 | 원본 userId→계정조회/탈퇴상태 fetch 없음; 로컬 props만 사용 |
| 14. PrincipalCell | [principal-cell-DOuK8FXE.js](https://app.hops.ai/assets/principal-cell-DOuK8FXE.js) | [36](references/screenshots/36-users-table.png), [38](references/screenshots/38-groups-empty-state.png), [45](references/screenshots/45-artifact-list.png)<br>사용자·그룹 행의 principal 유사 셀 조합 관측. component identity 미검증 | `PrincipalCell` | **표현 셀 재구성**<br>principal/null/undefined+settled, children/size | native span/텍스트 의미, Unavailable/Unknown 구분 | 원본 principal resolution, 소유자 lookup, 멤버 데이터 접근 없음 |
| 15. Badge | [badge-cjm_mrFp.js](https://app.hops.ai/assets/badge-cjm_mrFp.js) | [36](references/screenshots/36-users-table.png), [38](references/screenshots/38-groups-empty-state.png), [39](references/screenshots/39-usage-summary.png), [41](references/screenshots/41-custom-date-range.png), [48](references/screenshots/48-automation-draft-editor.png)<br>20px pill과 success/outline/secondary/private 계열 클래스 직접 관측 | `Badge` | **8 variants 스타일 재구성**<br>default/secondary/destructive/outline/muted/success/warning/private | 비대화형 span과 소비자 제공 텍스트 | 각 variant의 모든 theme/상태 조합은 미관측; 업무상 권한·상태 판정 없음 |
| 16. Skeleton | [skeleton-C9t3bRGl.js](https://app.hops.ai/assets/skeleton-C9t3bRGl.js) | 없음<br>정적 skeleton 정의와 CSS 근거 확인, 현재 화면 노출 미확인 | `Skeleton` | **정적 근거 기반 loading 표현**<br>muted 배경, radius, pulse | 장식 요소 aria-hidden, reduced motion | 네트워크 로딩 상태 자동 연결 없음; CSS 근거 수를 Skeleton 수로 세지 않음 |
| 17. Separator | [separator-CKsopgBT.js](https://app.hops.ai/assets/separator-CKsopgBT.js) | [18](references/screenshots/18-user-menu.png), [43](references/screenshots/43-activity-type-menu.png), [48](references/screenshots/48-automation-draft-editor.png), [50](references/screenshots/50-date-time-editor.png)<br>메뉴 separator와 editor slot=separator 직접 관측 | `Separator`, `ToolbarSeparator` | **native 의미·스타일 재구성**<br>horizontal/vertical/decorative 옵션; toolbar는 별도 세로 separator | 장식 시 role none/aria-hidden, 의미 있을 때 role separator/orientation | 원본 크기·조합 variant 전수 재현 아님; resize handle은 별도 ResizablePanels |
| 18. Tabs | [move-menu-item-g_rcZJ-z.js](https://app.hops.ai/assets/move-menu-item-g_rcZJ-z.js) | [24](references/screenshots/24-icon-color-picker.png), [33](references/screenshots/33-emoji-picker-search.png), [36](references/screenshots/36-users-table.png), [38](references/screenshots/38-groups-empty-state.png), [44](references/screenshots/44-artifact-browser.png), [48](references/screenshots/48-automation-draft-editor.png), [55](references/screenshots/55-automation-empty-after-cleanup.png)<br>tabs-list/trigger/content 및 tab/tabpanel 실제 관측 | `Tabs` | **통합 Tabs API 재구성**<br>segmented/underline, controlled/default, automatic/manual activation | tablist/tab/tabpanel 연결, roving focus, Arrow/Home/End, RTL, disabled | 원본 TabsList/Trigger/Content별 subexport 미공개; 라우팅·서버 데이터 전환 없음 |
| 19. Switch | [reload-screen-BSKiqJk2.js](https://app.hops.ai/assets/reload-screen-BSKiqJk2.js) | [34](references/screenshots/34-settings-general.png)<br>role=switch, checked/unchecked 직접 관측; md 36×20px, thumb14px | `Switch` | **3 sizes 상태 UI 재구성**<br>md/sm/xs, controlled/default, optional hidden form field | native button role switch, aria-checked, Space/Enter와 disabled | 설정 저장 없음; form reset은 호스트 관리; md 외 size는 정적 정의 근거 |
| 20. Chip / ChipBody | [reload-screen-BSKiqJk2.js](https://app.hops.ai/assets/reload-screen-BSKiqJk2.js) | [27](references/screenshots/27-search-filter-selected.png), [28](references/screenshots/28-search-type-filter.png)<br>선택 pill와 remove action 관측. 28은 Doc와 Table 동시 선택 | `Chip` | **interactive/removable 통합 Chip API**<br>onClick와 onRemove를 분리한 형제 button, selected/disabled | 중첩 button 방지, remove accessible name, focus-visible | 원본 ChipBody 별도 export/asChild 없음. 칩 상태는 소비자 제어 |
| 21. Toolbar | [reload-screen-BSKiqJk2.js](https://app.hops.ai/assets/reload-screen-BSKiqJk2.js) | [30](references/screenshots/30-composer-format-toolbar.png), [48](references/screenshots/48-automation-draft-editor.png), [50](references/screenshots/50-date-time-editor.png)<br>role=toolbar 직접 관측. 30의 format action은 10개, 각24×24px | `Toolbar`, `ToolbarGroup`, `ToolbarSeparator`, `ComposerToolbar` | **기본 toolbar 및 composer UI 상태 재구성**<br>default/pill/pill-compact, group/separator, 10개 format toggle, link/mention/emoji-name 로컬 popup | toolbar/group/separator 의미, Left/Right/Home/End focus, disabled/Escape | 실제 rich-text editor command/문서 mutation 없음. mention/emoji 후보는 전달한 local items, 외부 조회 없음; 원본 toolbar subAPI 전체 동등성 미보장 |
| 22. Alert | [reload-screen-BSKiqJk2.js](https://app.hops.ai/assets/reload-screen-BSKiqJk2.js) | [54](references/screenshots/54-destructive-alert-dialog.png)<br>정적 inline Alert 정의 확인. 54는 별도 destructive alertdialog이며 inline Alert의 직접 노출 근거는 아님 | `Alert` | **default/destructive inline UI 재구성**<br>variant/title/icon/description(children) 통합 API | role alert와 텍스트 구성 | AlertTitle/Description subexport 미공개; alertdialog·확인 후 삭제 동작은 이 Alert에 없음. 원본 inline Alert runtime 미관측 |
| 23. InputOTP UI slots | [reload-screen-BSKiqJk2.js](https://app.hops.ai/assets/reload-screen-BSKiqJk2.js) | 없음<br>정적 InputOTP/group/slot 정의 확인; 실제 인증 화면 노출 미확인 | `InputOTP` | **입력 UI만 재구성**<br>controlled digit string, length1~12, paste/native selection, onComplete callback | 실제 input 1개 + aria-hidden visual slots, accessible label, one-time-code autocomplete | 실제 OTP 발급/전송/인증/보안 정책 미구현; slot/group 조립 API 및 인증 네트워크 없음 |
| 24. Multi-select option picker | [reload-screen-BSKiqJk2.js](https://app.hops.ai/assets/reload-screen-BSKiqJk2.js) | [26](references/screenshots/26-search-people-filter.png), [27](references/screenshots/27-search-filter-selected.png), [28](references/screenshots/28-search-type-filter.png)<br>28 + accessibility multiselect에서 Type: Doc, Table와 두 selected option 확인 | `MultiSelect` | **검색·선택배열 로컬 UI 재구성**<br>options/value:string[]/onValueChange, 검색, chip 제거, clear, empty | combobox/listbox aria-multiselectable, active-descendant, Arrow/Home/End/Enter/Escape, disabled | 원본 leadingOptions·대규모 가상화/원격검색 없음. From 필터의 @me→Ramus 대체 관측은 동시 복수선택 근거가 아님 |
| 25. Multi-select listbox | [reload-screen-BSKiqJk2.js](https://app.hops.ai/assets/reload-screen-BSKiqJk2.js) | [28](references/screenshots/28-search-type-filter.png), [32](references/screenshots/32-mention-picker.png)<br>28 Type options listbox 복수선택, 32 mention listbox는 인접 별도 선택 UI | `MultiSelect` | **24와 동일 API family, 중복 컴포넌트로 세지 않음**<br>선택 여부·active option·체크 표시, 키보드 토글 | option aria-selected/disabled, focus 유지와 live selected count | 원본 listbox 별도 저수준 API 미공개. mention option 관측을 Type selector와 동일 구현체라고 단정하지 않음 |
| 26. Date / Time editor | [reload-screen-BSKiqJk2.js](https://app.hops.ai/assets/reload-screen-BSKiqJk2.js) | [41](references/screenshots/41-custom-date-range.png), [50](references/screenshots/50-date-time-editor.png), [51](references/screenshots/51-calendar-popup.png), [52](references/screenshots/52-time-listbox.png)<br>50 날짜/시각 필드, 51 날짜 popup. 52 측정 nodes=0이나 accessibility timeOptions에 option96개 확인 | `DateTimeEditor` | **native 날짜/시각 필드 + 별도 Calendar 연결**<br>date/time captions, min/max, local string value, Calendar 선택 | native date/time 입력, label/invalid/describedBy, Escape/외부이탈 닫힘 | 네이티브 input과 Ramus Calendar를 동일 제어로 보지 않음. 원본 96개 시간 option listbox는 재현하지 않고 native time 사용; timezone/자연어 파싱/예약실행 없음 |
| 27. Calendar month/table view | [reload-screen-BSKiqJk2.js](https://app.hops.ai/assets/reload-screen-BSKiqJk2.js) | [51](references/screenshots/51-calendar-popup.png)<br>data-slot=calendar, role=grid의 7열, 32px 원형 day button, 선택 날짜/today 상태 확인 | `Calendar` | **단일 날짜picker 재구성, 원본 entries calendar는 부분 대응**<br>월 탐색/Today/date pick, controlled month, min/max, locale label | grid/row/gridcell, roving date focus, Arrow/Home/End/PageUp/PageDown | 범위선택·일정 entries·fetch·달력 뷰 전체 미구현; native date input과 별도 export; locale는 label 표기이고 Gregorian date grid |
| 28. Table | [main-holVUCd9.js](https://app.hops.ai/assets/main-holVUCd9.js) | [36](references/screenshots/36-users-table.png), [38](references/screenshots/38-groups-empty-state.png)<br>native Members/Groups TABLE 직접 관측. 38은 실제 1행 Groups table | `Table`, `TableHeader`, `TableBody`, `TableFooter`, `TableRow`, `TableHead`, `TableCell`, `TableCaption` | **HTML table wrapper 8 subexports**<br>table/thead/tbody/tfoot/tr/th/td/caption native props/ref | native table semantics, th scope=col 기본, caption 지원 | TableHead 등8개를8개 family로 세지 않음. 38의 empty 파일명은 오기; virtual grid/서버행 관리 없음 |
| 29. TableGrid | [table-grid-BfM2_9SA.js](https://app.hops.ai/assets/table-grid-BfM2_9SA.js) | [45](references/screenshots/45-artifact-list.png)<br>실제 AG Grid role grid/row/columnheader/gridcell 목록 관측 | `DataGridLite` | **명시적 Lite 대체, 전체 기능 미재현**<br>native table sort/filter/row selection/sticky header/empty/loading | native sortable header aria-sort, checkbox/indeterminate 선택, loading status | AG Grid virtualization, cell editing, column resize/reorder/pin, grouping, drag/drop, aggregation, remote row model, range clipboard/export 미구현 |
| 30. Command palette family | [user-chip-D9Q7LYMB.js](https://app.hops.ai/assets/user-chip-D9Q7LYMB.js) | [25](references/screenshots/25-command-search.png), [26](references/screenshots/26-search-people-filter.png), [27](references/screenshots/27-search-filter-selected.png), [28](references/screenshots/28-search-type-filter.png), [32](references/screenshots/32-mention-picker.png), [33](references/screenshots/33-emoji-picker-search.png)<br>검색 command/listbox·mention·emoji-name popup 직접 관측 | `SearchCommand` | **local-items command UI 재구성**<br>query match, disabled items, empty, local select callback. RoleCombobox는 별도 onboarding autocomplete 조합 | combobox/listbox/option, active-descendant, Arrow/Home/End/Enter/Escape | 원본 Command Group/Shortcut 등 조립 subexports 전체 미공개; 전역 단축키 바인딩·원격 사용자/업무 검색·vendor API 없음 |

### 추가 shared 계열·회수 조합·추천 조합

기존 30행은 위에 보존했다. 아래 추가 항목을 원정의 30에 기계적으로 가산해 공식 family 총수로 만들지 않는다. 추가 JSX 값 export 16개와 family/조합 수는 다르다.

| 계열·분류 | source / 실제 관측 | 대응 export | 구현·접근성 재구성 | 부분지원·미지원 |
|---|---|---|---|---|
| **EntityMenu / ActionSheet / ContextMenu**<br>추가 공개 정의의 shared family 1 | [entity-menu-D70clu3c.js](https://app.hops.ai/assets/entity-menu-D70clu3c.js)<br>직접 UI 캡처 없음<br>sheet/point-context/action-row는 공개 정적 정의 확인. 63 desktop과64 mobile은 모두 DropdownMenu이며 ActionSheet 직접 UI 관측 근거 아님 | `ActionRow`, `ContextMenu`, `ActionSheet` | ActionRow icon/label/trailing/disabled/destructive/multiline, 좌표 context menu와 native-dialog ActionSheet<br>접근성: Shift+F10/ContextMenu key, menu 방향키/typeahead/Escape·focus복원, showModal 기반 sheet focus containment를 독립 재구성 | 원본 sheet sub-view, long-press,92svh 확장 상태 전량·keyboard inset 대응·headless vendor 엔진·portal 미재현. ContextMenu viewport clamp는 자체 추가이며 transformed ancestor에 영향 |
| **StructuredCard / OptionRow**<br>추가 공개 정의의 shared family 2 | [request-card-DRvRhM9x.js](https://app.hops.ai/assets/request-card-DRvRhM9x.js)<br>[62](references/screenshots/62-mobile-chat-sidebar-closed.png)<br>정적 shared card/option 정의 확인. 62에 대응 가능한 option-row class 패턴이 있으나 React component identity와 모든 card 상태를 검증한 것은 아님 | `StructuredCard`, `OptionRow`, `OptionGroup`, `Hint`, `CardFooter` | title/icon/accessory/eyebrow/description과 children, option label/gloss/trailing/pressed/current, group/hint/footer<br>접근성: native button, aria-pressed/current/describedby와 선택 가능한 접근성 텍스트 | request 승인·실행·업무 상태·backend 연결 없음. 5개 subexport를5개 새 family로 세지 않음 |
| **IconColorPicker**<br>기존 source와 캡처에서 별도 회수한 조합 | [reload-screen-BSKiqJk2.js](https://app.hops.ai/assets/reload-screen-BSKiqJk2.js)<br>[24](references/screenshots/24-icon-color-picker.png)<br>검색/색 swatch/icon grid popup 직접 관측. source select-element-icon SVG utility가 picker 근거인 것은 아님 | `IconColorPicker` | caller-supplied icon/color options, 검색, controlled icon/color value,36px icon cell/20px swatch/304px popup<br>접근성: 버튼 group의2D roving focus, color radiogroup, disabled/Escape/외부이탈/trigger 복원은 재구성 | 원본 icon registry·palette 대량 복제, 업로드, 원본 tab 조립 API, portal/collision/focus trap 없음. overflow ancestor에서 잘릴 수 있음 |
| **SymbolPicker (원본 emoji picker 참조)**<br>기존 source와 캡처에서 별도 회수한 조합 | [move-menu-item-g_rcZJ-z.js](https://app.hops.ai/assets/move-menu-item-g_rcZJ-z.js)<br>[33](references/screenshots/33-emoji-picker-search.png)<br>원본은 search combobox/listbox/options/category tabs popup. 재구성 API명은SymbolPicker | `SymbolPicker` | caller-supplied symbol/category/keywords, 검색과 category filter, selected value,32px option grid<br>접근성: 구현은 group/buttons와 aria-pressed/2D keyboard navigation. 원본 listbox/tab 역할을 그대로 복제했다고 주장하지 않음 | 내장 emoji 사전·custom account items·tone variants·emoji 업로드·외부검색 없음. nonmodal local popup에 portal/collision/focus trap 없음 |
| **AlertDialog**<br>별도 회수한 modal foundation 조합 | [tooltip-DgbuciXR.js](https://app.hops.ai/assets/tooltip-DgbuciXR.js)<br>[54](references/screenshots/54-destructive-alert-dialog.png)<br>실제 destructive alertdialog/title/cancel/action 관측. 기존 Alert(role=alert)와 별도 | `AlertDialog` | controlled open/title/description/cancel/confirm/busy, async callback 성공 시 닫힘·실패 시 generic error 유지<br>접근성: native showModal focus containment, 초기 cancel focus, return focus, labelled/described alertdialog, busy 중 중복제출 방지 재구성 | 삭제/인증/백엔드 직접 수행 없음. onConfirm은소비자 callback. native showModal 지원 필요; nonmodal Popover에 focus trap이 생긴 것은 아님 |
| **StatusDialog**<br>별도 회수한 UI-only domain composite | [reload-screen-BSKiqJk2.js](https://app.hops.ai/assets/reload-screen-BSKiqJk2.js)<br>[60](references/screenshots/60-status-dialog.png)<br>status text/preset/clear-after control과footer의 dialog 직접 관측 | `StatusDialog` | local draft text/preset/expiry, caller presets/expiry options, Clear/Cancel/Save callback, async busy/error<br>접근성: native modal focus flow와label/native select, disabled/busy와generic error 처리 재구성 | 실제 계정 status 저장·expiry scheduling·account API 없음. 원본 picker 대신 native select를 사용하며 모든 원본 control 동등성 미보장 |
| **Toast / Toaster**<br>실제 DOM 실측까지 회수한 UI family | [tooltip-DgbuciXR.js](https://app.hops.ai/assets/tooltip-DgbuciXR.js)<br>직접 UI 캡처 없음<br>[실제 Toast DOM](references/evidence/toast-computed.json)<br>최신 toast-computed의 LI/실제 custom group/body/title/description/CTA DOM을 확인. 앞선 추가조사 inventory의 미실측 결론을 최신 근거로 갱신 | `Toast`, `Toaster` | controlled items/announcement/title/description/action/dismiss, 자체 duration/pause와 cleanup, 실제 custom card recipe 반영<br>접근성: Toaster polite live announcement와 group label, hover/focus/hidden-document 중 timer pause는 독립 재구성 | 모든 Sonner rich variant·swipe dismissal·vendor stack animation·production trigger/업무액션 미재현. 위치·timing 기본값은 구현 추가이며 원본 실측 동작값이 아님 |
| **FileDropzone**<br>추천 조합, 원본 exact dropzone 회수 주장 금지 | [import-deck-dialog-D_HulIDs.js](https://app.hops.ai/assets/import-deck-dialog-D_HulIDs.js)<br>직접 UI 캡처 없음<br>ImportDeckDialog의 summary/busy 시각 정의와 기존card/field 어휘를 참조. exact FileDropzone UI 관측은 없음 | `FileDropzone` | native file input/button, local drag/drop와dragging state, disabled, multiple, onFiles callback<br>접근성: labelled group와키보드 native file-picker button. drop 수신은 UI 재구성 | 파일 업로드·변환·검증·저장·원본 ImportDeckDialog domain flow 없음. accept는picker hint일 뿐 dropped file 검증은 소비자 책임 |
| **Disclosure**<br>추천 조합, 원본 panel 회수 주장 금지 | 원본 exact 정의 없음<br>[58](references/screenshots/58-playbook-detail.png)<br>58의 example/playbook preview·trigger 어휘만 참조. iframe 예시는production state가 아니며 열린content panel은 미관측 | `Disclosure` | controlled/default open, native button trigger, labelled children panel과hidden state<br>접근성: aria-expanded/controls, native Enter/Space, disabled를독립 구현 | 원본 full Accordion family/subAPI·애니메이션·다중panel keyboard 정책·미관측 content layout 동등성 미보장 |

### 추가 공개 JS4개 판정

6개 선언을 중복 제거한 **실제 공개 URL 4개 모두 확인**했다. 분류는 **shared 2 + domain composite 1 + SVG utility 1**이며, 4개의 새 컴포넌트 family가 아니다.

| 공개 asset | 판정·대응 |
|---|---|
| [entity-menu-D70clu3c.js](https://app.hops.ai/assets/entity-menu-D70clu3c.js) | shared-family: 위 추가 shared-family 대응 export에 반영 |
| [select-element-icon-DpI9dtls.js](https://app.hops.ai/assets/select-element-icon-DpI9dtls.js) | svg-utility: 별도 picker export로 세지 않음. glyph utility일 뿐 |
| [import-deck-dialog-D_HulIDs.js](https://app.hops.ai/assets/import-deck-dialog-D_HulIDs.js) | domain-composite: ImportDeckDialog 자체는 별도 export 미제공. FileDropzone에 import-inspired 어휘만 추천 조합으로 참조 |
| [request-card-DRvRhM9x.js](https://app.hops.ai/assets/request-card-DRvRhM9x.js) | shared-family: 위 추가 shared-family 대응 export에 반영 |

`ImportDeckDialog`는 source의 실제 domain 조합으로 확인했지만 동일한 별도 export를 제공하지 않는다. import-inspired `FileDropzone`은 추천 조합일 뿐 원본 import 변환·검증·저장 흐름의 회수/구현으로 세지 않는다. `select-element-icon`은 SVG utility이므로 IconColorPicker의 근거가 아니다.

추가 원조사 파일도 패키지에 포함했다: [JSON](references/evidence/additional-ui-inventory.json), [Markdown](references/evidence/additional-ui-inventory.md). 선행 Toast 미실측 보고는 후속 toast-computed 실측으로 보완되었다.

### 실제 Toast와 Sonner 기본 recipe 구분

[toast-computed.json](references/evidence/toast-computed.json)의 실제 DOM 10개에서 custom group을 확인했다. 카드 **width 356px / radius 16px / padding 16px / gap 12px**, title·description **14px/20px**, CTA **height 24px / radius 8px / 12px/16px**다. 샘플 높이 153px는 해당 콘텐츠의 측정값이며 **content-led 높이**이므로 고정 recipe로 쓰지 않는다.

Sonner package 기본값 `p16 / font13 / gap6`는 별도 generic recipe이며 실제 Ramus custom Toast와 혼동하지 않는다. 추가 inventory의 선행 “Toast 미실측” 보고보다 최신 DOM 실측을 우선한다. 위치·duration·pause/live announcement는 독립 구현 추가이며 원본 timing 관측이나 모든 Toast variant의 검증을 뜻하지 않는다.

## 4. 값 export 전체 목록과 API family 구분

### RamusComponents.tsx (9개 값 export)

- `RamusProvider` (현재 소스 40행)
- `Button` (현재 소스 57행)
- `RadioChips` (현재 소스 78행)
- `TextField` (현재 소스 143행)
- `RoleCombobox` (현재 소스 179행)
- `AppCard` (현재 소스 331행)
- `StepProgress` (현재 소스 347행)
- `CatalogDialog` (현재 소스 367행)
- `Demo` (현재 소스 435행)

### RamusPrimitives.tsx (19개 값 export)

- `ButtonV2` (현재 소스 104행)
- `InputV2` (현재 소스 107행)
- `LabelV2` (현재 소스 110행)
- `TextareaV2` (현재 소스 113행)
- `Checkbox` (현재 소스 120행)
- `Switch` (현재 소스 135행)
- `RadioControl` (현재 소스 142행)
- `Avatar` (현재 소스 149행)
- `Badge` (현재 소스 159행)
- `Select` (현재 소스 169행)
- `DropdownMenu` (현재 소스 306행)
- `Popover` (현재 소스 351행)
- `HoverCard` (현재 소스 352행)
- `Tooltip` (현재 소스 357행)
- `Tabs` (현재 소스 376행)
- `ScrollArea` (현재 소스 399행)
- `Separator` (현재 소스 402행)
- `Skeleton` (현재 소스 405행)
- `Spinner` (현재 소스 406행)

### RamusPatterns.tsx (29개 값 export)

- `UserChip` (현재 소스 44행)
- `PrincipalCell` (현재 소스 49행)
- `Chip` (현재 소스 55행)
- `Toolbar` (현재 소스 59행)
- `ToolbarGroup` (현재 소스 60행)
- `ToolbarSeparator` (현재 소스 61행)
- `Alert` (현재 소스 63행)
- `InputOTP` (현재 소스 67행)
- `MultiSelect` (현재 소스 75행)
- `Calendar` (현재 소스 87행)
- `DateTimeEditor` (현재 소스 98행)
- `Table` (현재 소스 105행)
- `TableHeader` (현재 소스 106행)
- `TableBody` (현재 소스 107행)
- `TableFooter` (현재 소스 108행)
- `TableRow` (현재 소스 109행)
- `TableHead` (현재 소스 110행)
- `TableCell` (현재 소스 111행)
- `TableCaption` (현재 소스 112행)
- `DataGridLite` (현재 소스 116행)
- `EmptyState` (현재 소스 126행)
- `Breadcrumbs` (현재 소스 128행)
- `ResizablePanels` (현재 소스 131행)
- `MessageCard` (현재 소스 138행)
- `FileCard` (현재 소스 141행)
- `SearchCommand` (현재 소스 146행)
- `COMPOSER_FORMATS` : 상수, 컴포넌트 아님 (현재 소스 150행)
- `ComposerToolbar` (현재 소스 154행)
- `SettingsRow` (현재 소스 160행)

### RamusAdvanced.tsx (16개 값 export)

- `StructuredCard` (현재 소스 84행)
- `OptionRow` (현재 소스 96행)
- `OptionGroup` (현재 소스 104행)
- `Hint` (현재 소스 105행)
- `CardFooter` (현재 소스 106행)
- `ActionRow` (현재 소스 108행)
- `ContextMenu` (현재 소스 116행)
- `ActionSheet` (현재 소스 159행)
- `IconColorPicker` (현재 소스 190행)
- `SymbolPicker` (현재 소스 207행)
- `AlertDialog` (현재 소스 220행)
- `StatusDialog` (현재 소스 231행)
- `Toast` (현재 소스 246행)
- `Toaster` (현재 소스 261행)
- `FileDropzone` (현재 소스 267행)
- `Disclosure` (현재 소스 278행)

`Button`/`ButtonV2`, `TextField`/`InputV2`는 같은 원정의 영역을 다른 API로 다룬다. `MultiSelect` 1개가 원정의 24·25에 대응한다. Table 8개 / Toolbar 기본 3개 / StructuredCard 5개 subexports처럼 export 수와 family 수는 1:1이 아니다. Toast/Toaster 2개도 한 family의 표현이다. **73개 값 exports에는 COMPOSER_FORMATS 상수 1개가 포함**된다.

패키지 `index.ts`는 이름이 겹치는 SelectOption 타입을 `SingleSelectOption` / `MultiSelectOption` 별칭으로 구분한다. 타입 별칭은 73개 값 export 수에 포함하지 않는다.

## 5. 권장 조합, 원본 공식 export로 단정하지 않는 것

| 재구성 export | 참조 표면 | 근거와 경계 |
|---|---|---|
| `MessageCard` | [17](references/screenshots/17-app-shell-chat.png) | 채팅의 author/avatar/time/content 조합 참조. **회수한 공식 MessageCard 정의가 아님. 메시지 전송·수신·실시간 갱신 없음** |
| `FileCard` | [44](references/screenshots/44-artifact-browser.png), [45](references/screenshots/45-artifact-list.png) | artifact 목록과 CSS의 doc-image loading/broken 계약 참조. **범용 첨부파일 카드 원정의로 단정하지 않음. upload/download 서비스 연결 없음** |
| `EmptyState` | [13](references/screenshots/13-app-search-empty.webp), [46](references/screenshots/46-automation-empty-state.png), [55](references/screenshots/55-automation-empty-after-cleanup.png) | 검색 결과 없음과 automation empty 화면 조합 참조. **회수한 공식 EmptyState 정의 아님. 38 Groups는 여기 포함하지 않음** |
| `Breadcrumbs` | [44](references/screenshots/44-artifact-browser.png), [45](references/screenshots/45-artifact-list.png) | 탐색/경로 UI를 이용한 native nav 조합. **회수한 공식 Breadcrumbs 정의 아님. router 연결은 소비자 책임** |
| `SettingsRow` | [34](references/screenshots/34-settings-general.png), [36](references/screenshots/36-users-table.png), [60](references/screenshots/60-status-dialog.png) | 설정의 label/description/control 배치 참조. **회수한 공식 SettingsRow 정의 아님. 설정 저장·권한 판정 없음** |
| `ResizablePanels` | [45](references/screenshots/45-artifact-list.png), [48](references/screenshots/48-automation-draft-editor.png) | Resize navigation panel separator 관측과 editor/sidebar 배치 참조. **회수한 공식 ResizablePanels 정의 아님. 두패널 percentage/키보드 구현은 추가 재구성, 원본 geometry와 동등하지 않음** |
| `FileDropzone` | 직접 UI 캡처 없음 | ImportDeckDialog의 summary/busy 시각 정의와 기존card/field 어휘를 참조. exact FileDropzone UI 관측은 없음. **파일 업로드·변환·검증·저장·원본 ImportDeckDialog domain flow 없음. accept는picker hint일 뿐 dropped file 검증은 소비자 책임** |
| `Disclosure` | [58](references/screenshots/58-playbook-detail.png) | 58의 example/playbook preview·trigger 어휘만 참조. iframe 예시는production state가 아니며 열린content panel은 미관측. **원본 full Accordion family/subAPI·애니메이션·다중panel keyboard 정책·미관측 content layout 동등성 미보장** |

`ComposerToolbar` 역시 원본 Toolbar와 실측10개 format action을 바탕으로 만든 조합 이름이다. 실제 editor command를 수행하지 않는다. `RadioControl`/`Spinner`는 보수적 native/애니메이션 재구성이다. `AppCard`/`StepProgress`/`CatalogDialog`/`RadioChips` 등 초기 onboarding 조합과 `Demo`도 공식 회수 export 목록으로 승격하지 않는다.

## 6. 반드시 구분해야 하는 관측 차이

- **time-52**: 캡처52의 measure JSON은 nodes=0이다. 이것을 time picker 없음으로 해석하지 않는다. accessibility-evidence.json의 timeOptions AX에는 listbox 아래 option 96개가 확인된다. 구현 DateTimeEditor는 이 listbox 대신 native time input을 사용한다.

- **tooltip-59**: 캡처59는 data-slot=tooltip-content 1개를 직접 확인했다. 해당 측정 role은 null이며 role=tooltip selector 결과는 없었다. 구현 Tooltip의 role=tooltip/aria-describedby는 접근성 재구성이다.

- **groups-38**: 38-groups-empty-state 파일명은 잘못 붙었다. 실제 Groups native table에는 1개 행이 있으므로 empty 화면으로 분류하지 않는다.

- **type-multiple-28**: 캡처28과 AX multiselect에서 Doc와 Table 두 option이 동시에 selected이고 두 remove chip이 있다. Type 복수선택 근거다.

- **from-replacement**: From의 @me와 Ramus 관측은 서로 대체된 시점 차이다. 두 From 값이 동시에 선택된 것으로 세지 않는다. 개인 이름·이메일 원문은 이 문서에 복제하지 않는다.

- **preview-not-production**: 캡처58 playbook iframe preview는 예시 UI다. preview 내부 문서/표/승인·발행 상태를 실제 workspace production state나 실제 업무 실행으로 세지 않는다.

- **css-not-components**: raw CSS 537건은 selector·선언값 검증 근거 수이며 537개 컴포넌트가 아니다. Tailwind utility 수나 HTML wrapper subexport 수를 API family 수로 환산하지 않는다.

- **not-exhaustive**: 확인 가능한 공개 정적 정의와 접근한 UI 범위에서 최대한 회수했다. 공식 전체 디자인 시스템이나 미방문 route/미노출 chunk의 전수 획득을 보장하지 않는다.

### 크기와 variant 근거

- 원 Button: variants **7개**, sizes **7개**. 8번째 size를 임의로 추가하지 않았다.
- Avatar 원정의 scale: `xs16 / sm20 / md24 / lg32 / xl48px`. profile **80px**와 shell/user-chip **28px**는 별도 관측 override이며 원래 scale 숫자에 합산하지 않는다. shell presence8px, user-menu10px, profile12px의 위치별 관측 차이가 있다.
- Switch: `md/sm/xs` **3개 sizes**. 직접 실측한 md는36×20px, thumb14px다.
- profile textarea80px, composer format10개 버튼24×24px, 날짜 popup의7열/32px day button은 해당 장면의 실측이다. 모든 viewport/theme에서의 고정 불변값이라는 의미는 아니다.

### 최신 관측 추가

- 63/64 대화 action menu는 desktop/mobile 모두 Dropdown slot이다. **64를 ActionSheet 관측으로 세지 않는다.** ActionSheet의 원본 sheet UI는 정적 확인 수준이다.
- 원본 52의 time 측정 nodes=0 / AX 96 options 구분은 그대로 유지한다.
- native modal AlertDialog/StatusDialog/ActionSheet가 추가되었어도 기존 비모달 Popover/Tooltip/Picker의 portal·vendor collision·full headless·focus trap 미지원은 그대로다.

## 7. 명시적 제외·비동등 영역

- 원본 Ramus 전체 source·공식 npm/component package를 제공하거나 전체 전수 획득했다고 주장하지 않음
- 날짜 native input과 별도 Calendar popup을 동일 컴포넌트로 취급하지 않음. DateTimeEditor는 native date/time UI를 사용
- AG Grid 전체 기능, virtualization, advanced cell/column/group/remote row model 재현 없음
- OTP 발급·SMS/email 전송·실제 인증·rate limit·계정 보안 연동 없음
- Popover/HoverCard/Tooltip/menu의 portal·collision/flip·자동 viewport 경계조정·focus trap 없음. 로컬 DOM overlay이며 overflow ancestor에 잘릴 수 있음
- backend, vendor OAuth, 이메일 연결, 초대 전달, 계정 조회, 사용자 검색 API, 설정 persistence, 결제·사용량 청구·업무 로직 미구현
- composer formatting은 UI 상태와 callback만. 실제 editor mutation·mention resolution·emoji remote search·메시지 전송 없음
- Calendar 일정 entries와 범위선택/시간96개 listbox/자연어 날짜/시간대 예약 로직 미재현
- 공식 keyboard 동작·full WCAG·교차브라우저·모든 theme/state/size의 동등성 보장 없음

## 8. 조사 중 생긴 상태와 복구

`cleanup.json`, `restored-state.json`, AX의 deleteConfirmation/cleanup/restored를 대조했다.

- agent 조사 경로에서 **미발행 automation draft 1개가 생성되었고 삭제 완료**했다. 삭제 toast와 automation 목록 복귀 근거가 있다. draft ID와 개인 route는 문서에 복제하지 않았다.
- **발행 실행 없음, automation 실행 없음, 메시지 미전송, 설정 미저장**이다.
- composer는 비어 있고 sidebar는 열린 상태로 복구됐다. viewport는1265×873으로 복구됐다.
- 이 문서 작업은 두 documentation 파일만 썼으며 계정·브라우저를 조작하지 않았다.

## 9. 검증 상태와 남은 한계

- 기존 source 30행을 보존하고 추가 shared 2계열·별도 회수 5조합·추천 2조합 및 현재 **73값 exports / 64캡처**를 정적으로 대조했다. 기존 30그룹 미매핑은 0개지만 전체 원본 subAPI/업무 기능의 완전 구현을 의미하지 않는다.
- **최종 `verification.json`을 우선한다.** 통합 검증 기록은 부모 작업에서 갱신 중이다. 이 문서 작업은 신규 타입검사·브라우저 테스트를 실행하지 않았으며, 선행/부분 검증을 현재 73 exports 전체의 통과로 추정하지 않는다.
- 통합 보정: `SearchCommand`의 `scrollIntoView`는 현재 commandRoot 내에 focus가 있을 때만 실행한다. 초기 render가 전체 catalog를 강제 scroll하지 않도록 한 독립 구현 보정이다.
- 실제 원본 UI 관측과 재구성 runtime 검증은 서로 다르다. 접근성 동작은 코드 재구성 수준이며 별도 스크린리더·cross-browser·WCAG 검증이 필요하다.
- assets는 당시 앱에서 선언된 공개 URL의 정적 정의다. 공식 공개 API 계약이나 향후 버전 안정성은 보장하지 않는다.
- 개인 사용자/이메일 원문은 복제하지 않았다. Playbook iframe preview의 예시 데이터 역시 생산 상태 통계에 포함하지 않았다.

## 10. 캡처와 측정 파일 색인

캡처01~16은 초기 onboarding 자료이며 추가17~64의 실측 node count를 함께 표시했다. raw 측정은 추출 범위에 한정되므로 nodes=0이 UI 부재를 뜻하지 않는다.

| 번호 | 원본 캡처 | 실측 node 수·상태 |
|---|---|---|
| 1 | [01-onboarding-initial.png](references/screenshots/01-onboarding-initial.png) | 초기16개 캡처 자료, 추가 실측48개 범위 밖 |
| 2 | [02-required-selection-error.png](references/screenshots/02-required-selection-error.png) | 초기16개 캡처 자료, 추가 실측48개 범위 밖 |
| 3 | [03-personal-desktop.png](references/screenshots/03-personal-desktop.png) | 초기16개 캡처 자료, 추가 실측48개 범위 밖 |
| 4 | [04-personal-mobile.png](references/screenshots/04-personal-mobile.png) | 초기16개 캡처 자료, 추가 실측48개 범위 밖 |
| 5 | [05-team-choices.png](references/screenshots/05-team-choices.png) | 초기16개 캡처 자료, 추가 실측48개 범위 밖 |
| 6 | [06-business-other-input.png](references/screenshots/06-business-other-input.png) | 초기16개 캡처 자료, 추가 실측48개 범위 밖 |
| 7 | [07-role-combobox.png](references/screenshots/07-role-combobox.png) | 초기16개 캡처 자료, 추가 실측48개 범위 밖 |
| 8 | [08-email-connect.png](references/screenshots/08-email-connect.png) | 초기16개 캡처 자료, 추가 실측48개 범위 밖 |
| 9 | [09-email-skip-offer.png](references/screenshots/09-email-skip-offer.png) | 초기16개 캡처 자료, 추가 실측48개 범위 밖 |
| 10 | [10-suggested-apps-desktop.png](references/screenshots/10-suggested-apps-desktop.png) | 초기16개 캡처 자료, 추가 실측48개 범위 밖 |
| 11 | [11-suggested-apps-mobile.png](references/screenshots/11-suggested-apps-mobile.png) | 초기16개 캡처 자료, 추가 실측48개 범위 밖 |
| 12 | [12-all-apps-dialog-desktop.webp](references/screenshots/12-all-apps-dialog-desktop.webp) | 초기16개 캡처 자료, 추가 실측48개 범위 밖 |
| 13 | [13-app-search-empty.webp](references/screenshots/13-app-search-empty.webp) | 초기16개 캡처 자료, 추가 실측48개 범위 밖 |
| 14 | [14-app-dialog-mobile-transition.png](references/screenshots/14-app-dialog-mobile-transition.png) | 초기16개 캡처 자료, 추가 실측48개 범위 밖 |
| 15 | [15-team-invite-desktop.png](references/screenshots/15-team-invite-desktop.png) | 초기16개 캡처 자료, 추가 실측48개 범위 밖 |
| 16 | [16-team-invite-mobile.png](references/screenshots/16-team-invite-mobile.png) | 초기16개 캡처 자료, 추가 실측48개 범위 밖 |
| 17 | [17-app-shell-chat.png](references/screenshots/17-app-shell-chat.png) | 313 nodes |
| 18 | [18-user-menu.png](references/screenshots/18-user-menu.png) | 25 nodes |
| 19 | [19-profile-dialog.png](references/screenshots/19-profile-dialog.png) | 33 nodes |
| 20 | [20-profile-edit-form.png](references/screenshots/20-profile-edit-form.png) | 39 nodes |
| 21 | [21-searchable-single-select.png](references/screenshots/21-searchable-single-select.png) | 6 nodes |
| 22 | [22-new-item-menu.png](references/screenshots/22-new-item-menu.png) | 16 nodes |
| 23 | [23-create-space-form.png](references/screenshots/23-create-space-form.png) | 38 nodes |
| 24 | [24-icon-color-picker.png](references/screenshots/24-icon-color-picker.png) | 36 nodes |
| 25 | [25-command-search.png](references/screenshots/25-command-search.png) | 43 nodes |
| 26 | [26-search-people-filter.png](references/screenshots/26-search-people-filter.png) | 8 nodes |
| 27 | [27-search-filter-selected.png](references/screenshots/27-search-filter-selected.png) | 63 nodes |
| 28 | [28-search-type-filter.png](references/screenshots/28-search-type-filter.png) | 24 nodes |
| 29 | [29-sort-radio-menu.png](references/screenshots/29-sort-radio-menu.png) | 7 nodes |
| 30 | [30-composer-format-toolbar.png](references/screenshots/30-composer-format-toolbar.png) | 17 nodes |
| 31 | [31-link-popover.png](references/screenshots/31-link-popover.png) | 4 nodes |
| 32 | [32-mention-picker.png](references/screenshots/32-mention-picker.png) | 12 nodes |
| 33 | [33-emoji-picker-search.png](references/screenshots/33-emoji-picker-search.png) | 28 nodes |
| 34 | [34-settings-general.png](references/screenshots/34-settings-general.png) | 140 nodes |
| 35 | [35-theme-select.png](references/screenshots/35-theme-select.png) | 11 nodes |
| 36 | [36-users-table.png](references/screenshots/36-users-table.png) | 157 nodes |
| 37 | [37-filter-radio-items.png](references/screenshots/37-filter-radio-items.png) | 13 nodes |
| 38 | [38-groups-empty-state.png](references/screenshots/38-groups-empty-state.png) | 120 nodes / 실제 Groups1행, empty 오기 |
| 39 | [39-usage-summary.png](references/screenshots/39-usage-summary.png) | 100 nodes |
| 40 | [40-period-select.png](references/screenshots/40-period-select.png) | 17 nodes |
| 41 | [41-custom-date-range.png](references/screenshots/41-custom-date-range.png) | 107 nodes |
| 42 | [42-activity-layout.png](references/screenshots/42-activity-layout.png) | 165 nodes |
| 43 | [43-activity-type-menu.png](references/screenshots/43-activity-type-menu.png) | 14 nodes |
| 44 | [44-artifact-browser.png](references/screenshots/44-artifact-browser.png) | 285 nodes |
| 45 | [45-artifact-list.png](references/screenshots/45-artifact-list.png) | 298 nodes |
| 46 | [46-automation-empty-state.png](references/screenshots/46-automation-empty-state.png) | 174 nodes |
| 47 | [47-automation-create-choice.png](references/screenshots/47-automation-create-choice.png) | 49 nodes |
| 48 | [48-automation-draft-editor.png](references/screenshots/48-automation-draft-editor.png) | 355 nodes |
| 49 | [49-automation-trigger-select.png](references/screenshots/49-automation-trigger-select.png) | 34 nodes |
| 50 | [50-date-time-editor.png](references/screenshots/50-date-time-editor.png) | 129 nodes |
| 51 | [51-calendar-popup.png](references/screenshots/51-calendar-popup.png) | 95 nodes |
| 52 | [52-time-listbox.png](references/screenshots/52-time-listbox.png) | 0 nodes / AX option96개 별도 확인 |
| 53 | [53-delete-draft-menu.png](references/screenshots/53-delete-draft-menu.png) | 2 nodes |
| 54 | [54-destructive-alert-dialog.png](references/screenshots/54-destructive-alert-dialog.png) | 11 nodes |
| 55 | [55-automation-empty-after-cleanup.png](references/screenshots/55-automation-empty-after-cleanup.png) | 206 nodes |
| 56 | [56-apps-overview.png](references/screenshots/56-apps-overview.png) | 203 nodes |
| 57 | [57-playbook-cards.png](references/screenshots/57-playbook-cards.png) | 79 nodes |
| 58 | [58-playbook-detail.png](references/screenshots/58-playbook-detail.png) | 181 nodes / iframe preview는 예시 UI |
| 59 | [59-navigation-tooltip.png](references/screenshots/59-navigation-tooltip.png) | 1 nodes |
| 60 | [60-status-dialog.png](references/screenshots/60-status-dialog.png) | 42 nodes |
| 61 | [61-mobile-app-shell.png](references/screenshots/61-mobile-app-shell.png) | 271 nodes |
| 62 | [62-mobile-chat-sidebar-closed.png](references/screenshots/62-mobile-chat-sidebar-closed.png) | 190 nodes |
| 63 | [63-conversation-action-menu.png](references/screenshots/63-conversation-action-menu.png) | 14 nodes / desktop conversation Dropdown |
| 64 | [64-mobile-action-menu.png](references/screenshots/64-mobile-action-menu.png) | 210 nodes / mobile Dropdown, ActionSheet UI관측 아님 |

기계 판독 가능한 같은 매핑은 `components.inventory.json`에 있다. source asset URL, source group, 대응 export, 관측 번호, 구현·접근성·미지원 범위를 분리했다.
