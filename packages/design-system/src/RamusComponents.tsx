/**
 * RamusComponents: independent reconstruction, NOT original Ramus source code.
 * 원 서비스 소스가 아닌 독립 제작 예제이며, 키보드/접근성 처리는 재구성 사항입니다.
 * React 18+ only. Load the sibling ramus.css once in your application's entry point.
 * No CSS-in-JS, extra packages, external assets, personal data, storage, or network.
 * Styles use only existing ramus.css classes; responsive behavior stays in that CSS.
 * Its onboarding theme is a standalone light normalization, not the original scope.
 * Options must have unique, stable values. Labels are plain accessible strings.
 * Controlled components require the parent to accept onValueChange/onClose updates.
 * CatalogDialog requires native HTMLDialogElement.showModal support.
 */
import * as React from "react";

export type RamusTheme = "light" | "dark" | "onboarding";
export type RamusContrast = "standard" | "enhanced";
export type RamusOption = Readonly<{
  value: string;
  label: string;
  disabled?: boolean;
}>;

type DivProps = Omit<React.HTMLAttributes<HTMLDivElement>, "style">;
const ThemeContext = React.createContext<RamusTheme>("light");
const cx = (...parts: Array<string | false | null | undefined>): string =>
  parts.filter(Boolean).join(" ");
const describedBy = (...parts: Array<string | false | undefined>): string | undefined => {
  const ids = parts.filter((part): part is string => typeof part === "string")
    .flatMap((part) => part.split(/\s+/)).filter(Boolean);
  return ids.length ? Array.from(new Set(ids)).join(" ") : undefined;
};
const hasContent = (node: React.ReactNode): boolean =>
  node !== undefined && node !== null && node !== false && node !== "";

export type RamusProviderProps = DivProps & {
  theme?: RamusTheme;
  contrast?: RamusContrast;
  "data-contrast"?: RamusContrast;
};
/** contrast takes precedence over data-contrast; neither is set by the original Ramus source. */
export function RamusProvider({ theme = "light", contrast, "data-contrast": dataContrast,
  className, children, ...rest }: RamusProviderProps) {
  return (
    <ThemeContext.Provider value={theme}>
      <div {...rest} className={cx("ramus", className)} data-theme={theme}
        data-contrast={contrast ?? dataContrast ?? "standard"}>
        {children}
      </div>
    </ThemeContext.Provider>
  );
}

export type ButtonProps = Omit<React.ButtonHTMLAttributes<HTMLButtonElement>, "style"> & {
  variant?: "primary" | "outline" | "ghost";
  size?: "default" | "cta" | "compact";
  comfortable?: boolean;
};
export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { variant = "primary", size = "default", comfortable = false, className,
    type = "button", children, ...rest }, ref,
) {
  return (
    <button {...rest} ref={ref} type={type} data-variant={variant} data-size={size}
      className={cx("h-button", comfortable && "h-button-comfortable", className)}>
      {children}
    </button>
  );
});

export type RadioChipsProps = Omit<DivProps,
  "children" | "onChange" | "defaultValue" | "role" | "tabIndex" | "aria-label" | "aria-labelledby"
> & {
  label: string;
  options: readonly RamusOption[];
  value: string | null;
  onValueChange: (value: string) => void;
  disabled?: boolean;
};
export function RadioChips({ label, options, value, onValueChange, disabled = false,
  className, onKeyDown, ...rest }: RadioChipsProps) {
  const labelId = React.useId();
  const nodes = React.useRef(new Map<string, HTMLButtonElement>());
  const [focusValue, setFocusValue] = React.useState<string | null>(value);
  const enabled = options.filter((option) => !disabled && !option.disabled);
  const isEnabled = (candidate: string | null) => enabled.some((option) => option.value === candidate);
  const tabValue = isEnabled(focusValue) ? focusValue
    : isEnabled(value) ? value : enabled[0]?.value ?? null;

  React.useEffect(() => { setFocusValue(value); }, [value]);

  function handleKeyDown(event: React.KeyboardEvent<HTMLDivElement>) {
    onKeyDown?.(event);
    if (event.defaultPrevented || event.altKey || event.ctrlKey || event.metaKey || !enabled.length) return;
    const keys = ["ArrowRight", "ArrowDown", "ArrowLeft", "ArrowUp", "Home", "End"];
    if (!keys.includes(event.key)) return;
    event.preventDefault();
    const focused = enabled.findIndex((option) => nodes.current.get(option.value) === event.target);
    const current = focused >= 0 ? focused : Math.max(0, enabled.findIndex((option) => option.value === tabValue));
    const index = event.key === "Home" ? 0 : event.key === "End" ? enabled.length - 1
      : (current + (event.key === "ArrowLeft" || event.key === "ArrowUp" ? -1 : 1) + enabled.length) % enabled.length;
    const next = enabled[index];
    if (!next) return;
    setFocusValue(next.value);
    nodes.current.get(next.value)?.focus();
    if (next.value !== value) onValueChange(next.value);
  }

  return (
    <div className="h-field">
      <span id={labelId} className="h-label">{label}</span>
      <div {...rest} role="radiogroup" aria-labelledby={labelId} aria-disabled={disabled || undefined}
        className={cx("h-chip-group", className)} onKeyDown={handleKeyDown}>
        {options.map((option) => (
          <button key={option.value} type="button" role="radio" className="h-chip"
            ref={(node) => {
              if (node) nodes.current.set(option.value, node);
              else nodes.current.delete(option.value);
            }}
            aria-checked={value === option.value} disabled={disabled || option.disabled}
            tabIndex={!disabled && !option.disabled && option.value === tabValue ? 0 : -1}
            onFocus={() => setFocusValue(option.value)}
            onClick={() => {
              if (disabled || option.disabled) return;
              setFocusValue(option.value);
              if (option.value !== value) onValueChange(option.value);
            }}>
            {option.label}
          </button>
        ))}
      </div>
    </div>
  );
}

export type TextFieldProps = Omit<React.InputHTMLAttributes<HTMLInputElement>,
  "style" | "size" | "children" | "aria-invalid"
> & {
  label: React.ReactNode;
  hint?: React.ReactNode;
  error?: React.ReactNode;
  invalid?: boolean;
  inputClassName?: string;
};
export const TextField = React.forwardRef<HTMLInputElement, TextFieldProps>(function TextField(
  { label, hint, error, invalid = false, id, className, inputClassName,
    "aria-describedby": externalDescription, ...rest }, ref,
) {
  const generatedId = React.useId();
  const inputId = id ?? `${generatedId}-input`;
  const hintId = `${generatedId}-hint`;
  const errorId = `${generatedId}-error`;
  const showHint = hasContent(hint);
  const showError = hasContent(error);
  return (
    <div className={cx("h-field", className)}>
      <label className="h-label" htmlFor={inputId}>{label}</label>
      <input {...rest} ref={ref} id={inputId}
        className={cx("h-input", "h-input-accessible", inputClassName)}
        aria-invalid={invalid || showError || undefined}
        aria-describedby={describedBy(externalDescription, showHint && hintId, showError && errorId)} />
      {showHint && <p id={hintId} className="h-hint">{hint}</p>}
      {showError && <p id={errorId} className="h-error" role="alert">{error}</p>}
    </div>
  );
});

export type RoleComboboxProps = Omit<React.InputHTMLAttributes<HTMLInputElement>,
  "style" | "size" | "children" | "value" | "defaultValue" | "onChange" | "type" |
  "readOnly" | "autoComplete" | "role" | "required" | "aria-invalid" |
  "aria-activedescendant" | "aria-controls" | "aria-expanded" | "aria-autocomplete" | "aria-haspopup"
> & {
  label: string;
  options: readonly RamusOption[];
  value: string | null;
  onValueChange: (value: string) => void;
  hint?: React.ReactNode;
  error?: React.ReactNode;
};
/** Editable combobox: typing emits raw text; Enter/click on an option emits its value. */
export function RoleCombobox({ label, options, value, onValueChange, hint, error, id,
  name, form, disabled = false, className, onKeyDown, onBlur, onClick,
  onCompositionStart, onCompositionEnd,
  "aria-describedby": externalDescription, ...rest }: RoleComboboxProps) {
  const baseId = React.useId();
  const inputId = id ?? baseId + "-combo";
  const listId = baseId + "-listbox";
  const hintId = baseId + "-hint";
  const errorId = baseId + "-error";
  const inputRef = React.useRef<HTMLInputElement>(null);
  const optionNodes = React.useRef(new Map<string, HTMLLIElement>());
  const composingRef = React.useRef(false);
  const [compositionText, setCompositionText] = React.useState<string | null>(null);
  const [expanded, setExpanded] = React.useState(false);
  const [activeValue, setActiveValue] = React.useState<string | null>(null);
  const selected = options.find((option) => option.value === value);
  // Preserve IME draft text even if an intermediate raw value matches an option ID.
  const inputValue = compositionText ?? selected?.label ?? value ?? "";
  const search = inputValue.toLowerCase();
  const filtered = options.filter((option) => option.label.toLowerCase().includes(search));
  const enabled = filtered.filter((option) => !option.disabled);
  const active = enabled.find((option) => option.value === activeValue);
  const isOpen = expanded && !disabled && filtered.length > 0;
  const activeIndex = active ? filtered.findIndex((option) => option.value === active.value) : -1;
  const showHint = hasContent(hint);
  const showError = hasContent(error);
  const optionId = (index: number) => baseId + "-option-" + index;

  React.useEffect(() => {
    if (disabled) {
      setExpanded(false);
      setActiveValue(null);
      composingRef.current = false;
      setCompositionText(null);
    }
  }, [disabled]);
  React.useEffect(() => {
    if (isOpen && active) optionNodes.current.get(active.value)?.scrollIntoView({ block: "nearest" });
  }, [isOpen, active?.value]);

  function closeList() {
    setExpanded(false);
    setActiveValue(null);
  }
  function commit(option: RamusOption | undefined) {
    if (disabled || !option || option.disabled || composingRef.current) return;
    if (option.value !== value) onValueChange(option.value);
    closeList();
    inputRef.current?.focus();
  }
  function handleKeyDown(event: React.KeyboardEvent<HTMLInputElement>) {
    onKeyDown?.(event);
    // isComposing plus legacy 229 covers IME confirmation keys, including Safari cases.
    if (event.defaultPrevented || disabled || composingRef.current || event.nativeEvent.isComposing ||
      event.nativeEvent.keyCode === 229 || event.altKey || event.ctrlKey || event.metaKey) return;
    if (event.key === "Escape") {
      if (expanded) { event.preventDefault(); event.stopPropagation(); closeList(); }
      return;
    }
    if (event.key === "Tab") { closeList(); return; }
    if (event.key === "Enter") {
      if (isOpen && active) { event.preventDefault(); commit(active); }
      else closeList(); // No active result: retain free text; do not block normal form submission.
      return;
    }
    // Space/Home/End keep their normal editing/caret behavior.
    if (event.key !== "ArrowDown" && event.key !== "ArrowUp") return;
    if (!enabled.length) return;
    event.preventDefault();
    const current = isOpen ? enabled.findIndex((option) => option.value === active?.value) : -1;
    const next = current < 0 ? (event.key === "ArrowUp" ? enabled.length - 1 : 0)
      : (current + (event.key === "ArrowUp" ? -1 : 1) + enabled.length) % enabled.length;
    setActiveValue(enabled[next]?.value ?? null);
    setExpanded(true);
  }

  return (
    <div className={cx("h-field", className)}>
      <label htmlFor={inputId} className="h-label">{label}</label>
      <div className="h-combobox-wrap">
        <input {...rest} ref={inputRef} id={inputId} form={form} type="text"
          autoComplete="off" disabled={disabled} value={inputValue}
          role="combobox" aria-haspopup="listbox" aria-autocomplete="list"
          aria-expanded={isOpen} aria-controls={isOpen ? listId : undefined}
          aria-activedescendant={isOpen && activeIndex >= 0 ? optionId(activeIndex) : undefined}
          aria-invalid={showError || undefined}
          aria-describedby={describedBy(externalDescription, showHint && hintId, showError && errorId)}
          className="h-input h-input-accessible" onKeyDown={handleKeyDown}
          onChange={(event) => {
            if (disabled) return;
            const raw = event.currentTarget.value;
            if (composingRef.current) setCompositionText(raw);
            setActiveValue(null);
            setExpanded(true);
            onValueChange(raw);
          }}
          onCompositionStart={(event) => {
            composingRef.current = true;
            setCompositionText(event.currentTarget.value);
            onCompositionStart?.(event);
          }}
          onCompositionEnd={(event) => {
            const raw = event.currentTarget.value;
            composingRef.current = false;
            setCompositionText(null);
            if (!disabled && raw !== value) onValueChange(raw);
            onCompositionEnd?.(event);
          }}
          onClick={(event) => {
            onClick?.(event);
            if (!event.defaultPrevented && !disabled) setExpanded(true);
          }}
          onBlur={(event) => {
            closeList();
            composingRef.current = false;
            setCompositionText(null);
            onBlur?.(event);
          }} />
        {name && <input type="hidden" name={name} form={form} value={value ?? ""} disabled={disabled} />}
        {isOpen && (
          <ul id={listId} role="listbox" aria-label={label} className="h-listbox">
            {filtered.map((option, index) => (
              <li key={option.value} id={optionId(index)} role="option" className="h-option"
                ref={(node) => {
                  if (node) optionNodes.current.set(option.value, node);
                  else optionNodes.current.delete(option.value);
                }}
                aria-selected={!option.disabled && option.value === active?.value}
                aria-disabled={option.disabled || undefined}
                onPointerDown={(event) => { if (event.button === 0) event.preventDefault(); }}
                onMouseDown={(event) => { if (event.button === 0) event.preventDefault(); }}
                onPointerMove={() => { if (!option.disabled) setActiveValue(option.value); }}
                onClick={() => commit(option)}>
                {option.label}
              </li>
            ))}
          </ul>
        )}
      </div>
      {showHint && <p id={hintId} className="h-hint">{hint}</p>}
      {showError && <p id={errorId} role="alert" className="h-error">{error}</p>}
    </div>
  );
}

export type AppCardProps = Omit<DivProps, "title" | "children"> & {
  title: string;
  subtitle?: string;
  /** Decorative, noninteractive content. Give actions their own accessible names. */
  icon?: React.ReactNode;
  action?: React.ReactNode;
};
export function AppCard({ title, subtitle, icon, action, className, ...rest }: AppCardProps) {
  return (
    <div {...rest} className={cx("h-app-card", className)}>
      <span className="h-app-icon" aria-hidden="true">{icon ?? title.charAt(0)}</span>
      <div className="h-app-meta">
        <strong title={title}>{title}</strong>
        {subtitle && <small title={subtitle}>{subtitle}</small>}
      </div>
      {action}
    </div>
  );
}

export type StepProgressProps = Omit<DivProps,
  "children" | "role" | "aria-valuemin" | "aria-valuemax" | "aria-valuenow" | "aria-valuetext" | "aria-label"
> & { step: number; total: number; label?: string };
export function StepProgress({ step, total, label = "설정 진행 상황", className, ...rest }: StepProgressProps) {
  const maximum = Number.isFinite(total) ? Math.max(1, Math.floor(total)) : 1;
  const current = Number.isFinite(step) ? Math.min(maximum, Math.max(0, Math.floor(step))) : 0;
  return (
    <div {...rest} role="progressbar" aria-label={label} aria-valuemin={0}
      aria-valuemax={maximum} aria-valuenow={current} aria-valuetext={`${current} / ${maximum} 단계`}
      className={cx("h-step", className)}>{current} / {maximum}</div>
  );
}

export type CatalogDialogProps = Omit<React.DialogHTMLAttributes<HTMLDialogElement>,
  "style" | "open" | "onClose" | "onCancel" | "title" | "aria-label" | "aria-labelledby" | "aria-describedby"
> & {
  open: boolean;
  onClose: () => void;
  title?: React.ReactNode;
  description?: React.ReactNode;
  /** Defaults to the observed dark modal; pass the outer theme explicitly to match it. */
  theme?: RamusTheme;
};
export function CatalogDialog({ open, onClose, title = "앱 카탈로그", description,
  theme = "dark", children, className, ...rest }: CatalogDialogProps) {
  const id = React.useId();
  const dialogRef = React.useRef<HTMLDialogElement>(null);
  const openerRef = React.useRef<HTMLElement | null>(null);
  const closeRequested = React.useRef(false);
  const callbackRef = React.useRef(onClose);
  const openRef = React.useRef(open);
  const [nativeOpen, setNativeOpen] = React.useState(false);
  callbackRef.current = onClose;
  openRef.current = open;
  const showDescription = hasContent(description);

  function requestClose() {
    if (!openRef.current || closeRequested.current) return;
    closeRequested.current = true;
    callbackRef.current();
  }
  React.useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;
    if (!open) { setNativeOpen(false); return; }
    closeRequested.current = false;
    const focused = dialog.ownerDocument.activeElement;
    openerRef.current = focused instanceof HTMLElement ? focused : null;
    if (typeof dialog.showModal !== "function") {
      throw new Error("CatalogDialog requires native dialog.showModal().");
    }
    if (!dialog.open) dialog.showModal();
    setNativeOpen(true);
    return () => {
      // Runs on controlled close, unmount, and StrictMode effect replay.
      // The close handler ignores queued close events if a new modal is already open.
      if (dialog.open) dialog.close();
      const opener = openerRef.current;
      openerRef.current = null;
      if (opener?.isConnected) opener.focus({ preventScroll: true });
    };
  }, [open]);

  // .h-dialog sets display:flex, so it must not be applied to a controlled-closed dialog.
  return (
    <dialog {...rest} ref={dialogRef} data-theme={theme}
      className={cx("ramus", open && nativeOpen && "h-dialog", className)}
      aria-labelledby={`${id}-title`} aria-describedby={showDescription ? `${id}-description` : undefined}
      onCancel={(event) => {
        if (event.target !== event.currentTarget) return;
        event.preventDefault();
        event.stopPropagation();
        requestClose();
      }}
      onClose={(event) => {
        if (event.target !== event.currentTarget || event.currentTarget.open) return;
        setNativeOpen(false);
        requestClose();
      }}>
      <header className="h-dialog-header">
        <div className="h-field">
          <h2 className="h-dialog-title" id={`${id}-title`}>{title}</h2>
          {showDescription && <p className="h-hint" id={`${id}-description`}>{description}</p>}
        </div>
        <Button variant="ghost" autoFocus aria-label="카탈로그 닫기" onClick={requestClose}>닫기</Button>
      </header>
      <div className="h-dialog-body">{children}</div>
    </dialog>
  );
}

export function Demo() {
  const [theme, setTheme] = React.useState<RamusTheme>("onboarding");
  const [purpose, setPurpose] = React.useState<string | null>("explore");
  const [role, setRole] = React.useState<string | null>(null);
  const [task, setTask] = React.useState("로컬 샘플 작업");
  const [showError, setShowError] = React.useState(false);
  const [step, setStep] = React.useState(1);
  const [catalogOpen, setCatalogOpen] = React.useState(false);
  const [chosenApp, setChosenApp] = React.useState<string | null>(null);
  const themes: readonly RamusOption[] = [
    { value: "light", label: "Light" }, { value: "dark", label: "Dark" },
    { value: "onboarding", label: "Onboarding" },
  ];
  const roles: readonly RamusOption[] = [
    { value: "explorer", label: "탐색 역할" }, { value: "builder", label: "제작 역할" },
    { value: "unavailable", label: "비활성 예시", disabled: true },
    { value: "reviewer", label: "검토 역할" },
  ];
  return (
    <RamusProvider theme={theme}>
      <div className="h-onboarding-stage">
        <main className="h-onboarding-shell">
          <div className="h-onboarding-content">
            <header className="h-onboarding-header">
              <strong>독립 제작 UI 데모</strong>
              <StepProgress step={step} total={3} />
            </header>
            <div className="h-field">
              <h1 className="h-onboarding-title">로컬에서 컴포넌트 둘러보기</h1>
              <p className="h-onboarding-description">모든 변경은 메모리 안에서만 유지됩니다. 실제 계정 연결이나 전송은 하지 않습니다.</p>
              <RadioChips label="테마" options={themes} value={theme} onValueChange={(next) => {
                if (next === "light" || next === "dark" || next === "onboarding") setTheme(next);
              }} />
              <RadioChips label="사용 목적 예시" value={purpose} onValueChange={setPurpose} options={[
                { value: "explore", label: "둘러보기" }, { value: "build", label: "만들기" },
                { value: "disabled", label: "비활성", disabled: true },
              ]} />
              <TextField label="샘플 작업 이름" value={task} autoComplete="off"
                hint="개인정보 대신 예시 문구만 입력하세요."
                error={showError && !task.trim() ? "샘플 작업 이름을 입력하세요." : undefined}
                onChange={(event) => { setTask(event.target.value); setShowError(false); }} />
              <RoleCombobox label="역할 예시" options={roles} value={role} onValueChange={setRole}
                placeholder="역할 선택 또는 직접 입력" hint="직접 입력하거나 방향키로 탐색하고 Enter로 선택하세요. Escape로 닫습니다." />
              <div className="h-app-grid">
                <AppCard title="샘플 앱 A" subtitle={chosenApp === "A" ? "로컬 선택됨" : "실제 서비스와 연결되지 않음"}
                  action={<Button size="compact" variant="outline" onClick={() => setChosenApp("A")}>A 선택</Button>} />
                <AppCard title="샘플 앱 B" subtitle={chosenApp === "B" ? "로컬 선택됨" : "실제 서비스와 연결되지 않음"}
                  action={<Button size="compact" variant="outline" onClick={() => setChosenApp("B")}>B 선택</Button>} />
              </div>
              <Button variant="outline" comfortable onClick={() => setCatalogOpen(true)}>로컬 카탈로그 열기</Button>
              <p className="h-hint" role="status">{chosenApp ? `샘플 앱 ${chosenApp} 선택됨` : "아직 선택한 샘플 앱이 없습니다."}</p>
            </div>
          </div>
          <footer className="h-onboarding-footer">
            <span className="h-hint">네트워크 요청 없음</span>
            <div className="h-onboarding-footer-actions">
              <Button variant="ghost" disabled={step <= 1} onClick={() => setStep((current) => Math.max(1, current - 1))}>이전</Button>
              <Button size="cta" onClick={() => {
                setShowError(true);
                if (task.trim()) setStep((current) => Math.min(3, current + 1));
              }}>{step === 3 ? "다시 확인" : "다음 단계"}</Button>
            </div>
          </footer>
        </main>
      </div>
      <CatalogDialog open={catalogOpen} onClose={() => setCatalogOpen(false)}
        title="로컬 샘플 카탈로그" description="선택해도 API 호출이나 외부 연결이 발생하지 않습니다.">
        <div className="h-app-grid">
          {["A", "B"].map((app) => (
            <AppCard key={app} title={`샘플 앱 ${app}`} subtitle="데모 데이터"
              action={<Button variant="outline" onClick={() => { setChosenApp(app); setCatalogOpen(false); }}>
                {app} 선택
              </Button>} />
          ))}
        </div>
      </CatalogDialog>
    </RamusProvider>
  );
}
