/**
 * README: independent React reconstruction, not the original service source.
 * Usage: import { RamusProvider } from './RamusComponents'; load ramus.css followed
 * by ramus-primitives.css once, and render these components inside RamusProvider.
 * Only React is imported. No portals, packages, persistence, or account calls.
 *
 * STATIC EVIDENCE, not a claim of original runtime behavior:
 * button-BRocK4d0: 7 variants, 7 sizes, NOT 8 sizes. No speculative eighth size.
 * tooltip-DgbuciXR: Input/Label/Tooltip; checkbox-CeZ5BQbX: mixed checkbox.
 * open-profile-CLoLVf5-: Textarea/Popover/HoverCard/ScrollArea.
 * reload-screen-BSKiqJk2: Switch md/sm/xs; move-menu-item-g_rcZJ-z: Tabs.
 * use-personal-space-label--9IRlhqb: Avatar xs/sm/md/lg/xl, picture fallback,
 * initials, optional online presence. Its additional 2xl is intentionally not exposed.
 * badge-cjm_mrFp: 8 variants; dropdown-menu-D4MPvagG/select-C8hjZ6mU:
 * menu roles, checked items, submenus, single-select styling.
 * Measurements 21/22/29/31/34/35: rows 28px, 4px popup padding, 8px gap,
 * item radius 12px, menu radius 16px, popover radius 20px, border hairline.
 *
 * ACCESSIBILITY RECONSTRUCTION / additions, not observed original behavior:
 * Native checkbox/radio, roving focus, typeahead, IME guards, dismiss stack,
 * Escape/outside-focus cleanup, focus restoration, hover timers and reduced motion.
 * RadioControl/Spinner styling is a conservative reconstruction, not a recovered
 * complete source recipe. Hover delays are configurable implementation defaults.
 *
 * LIMITS: overlays stay inside .ramus for token inheritance, so overflow ancestors
 * can clip them. No portal/collision engine/focus trap or modal semantics. Popover
 * is nonmodal. Trigger prop is button CONTENT, never an interactive element.
 * Tooltip children must be a focusable element forwarding aria-describedby.
 * Use an accessible label for icon-only buttons. Options/items need unique values
 * or ids; controlled values require callbacks to accept updates. Checkbox and
 * Switch form reset is managed by the owning application. Submenu radio grouping
 * and application shortcuts are consumer-owned. Only online presence is evidenced.
 */
import * as React from "react";

const cx = (...values: Array<string | false | null | undefined>) => values.filter(Boolean).join(" ");
const useLayout = typeof window === "undefined" ? React.useEffect : React.useLayoutEffect;
function useValue<T>(value: T | undefined, initial: T, notify?: (next: T) => void): [T, (next: T) => void] {
  const [own, setOwn] = React.useState(initial);
  const current = value === undefined ? own : value;
  const latest = React.useRef({ current, notify, controlled: value !== undefined });
  useLayout(() => { latest.current = { current, notify, controlled: value !== undefined }; });
  const set = React.useCallback((next: T) => {
    const state = latest.current;
    if (Object.is(next, state.current)) return;
    if (!state.controlled) setOwn(next);
    state.notify?.(next);
  }, []);
  return [current, set];
}
type CloseReason = "escape" | "outside" | "focus";
const layerStacks = new WeakMap<Document, symbol[]>();
function useDismiss(open: boolean, root: React.RefObject<HTMLElement | null>, close: (reason: CloseReason) => void) {
  const latest = React.useRef(close);
  useLayout(() => { latest.current = close; });
  React.useEffect(() => {
    const node = root.current;
    if (!open || !node) return;
    const doc = node.ownerDocument;
    const stack = layerStacks.get(doc) ?? [];
    layerStacks.set(doc, stack);
    const key = Symbol();
    stack.push(key);
    const top = () => stack[stack.length - 1] === key;
    const outside = (event: Event) => {
      if (top() && event.target instanceof Node && !node.contains(event.target))
        latest.current(event.type === "focusin" ? "focus" : "outside");
    };
    const keyboard = (event: KeyboardEvent) => {
      if (top() && event.key === "Escape" && !event.isComposing) {
        event.preventDefault(); event.stopPropagation(); latest.current("escape");
      }
    };
    doc.addEventListener("pointerdown", outside, true);
    doc.addEventListener("focusin", outside, true);
    doc.addEventListener("keydown", keyboard);
    return () => {
      const index = stack.indexOf(key);
      if (index >= 0) stack.splice(index, 1);
      doc.removeEventListener("pointerdown", outside, true);
      doc.removeEventListener("focusin", outside, true);
      doc.removeEventListener("keydown", keyboard);
    };
  }, [open, root]);
}
const canNavigate = (event: React.KeyboardEvent) => !event.defaultPrevented && !event.altKey &&
  !event.ctrlKey && !event.metaKey && !event.nativeEvent.isComposing && event.nativeEvent.keyCode !== 229;
function focusables(node: HTMLElement) {
  return Array.from(node.querySelectorAll<HTMLElement>('button:not(:disabled),input:not(:disabled):not([type="hidden"]),textarea:not(:disabled),select:not(:disabled),a[href],[tabindex]:not([tabindex="-1"])'))
    .filter(el => !el.closest('[hidden],[inert]') && el.getAttribute("aria-disabled") !== "true");
}
function CheckMark({ mixed = false }: { mixed?: boolean }) {
  return <svg aria-hidden="true" viewBox="0 0 16 16" className="hp-check-mark" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d={mixed ? "M4 8h8" : "m3 8 3 3 7-7"} />
  </svg>;
}
function Chevron({ right = false }: { right?: boolean }) {
  return <svg aria-hidden="true" viewBox="0 0 16 16" className="hp-chevron" fill="none" stroke="currentColor" strokeWidth="1.5"><path d={right ? "m6 4 4 4-4 4" : "m4 6 4 4 4-4"} /></svg>;
}
export type ButtonV2Variant = "default" | "destructive" | "outline" | "secondary" | "ghost" | "link" | "text";
/** Seven sizes are source-evidenced. The requested eighth size was not recovered. */
export type ButtonV2Size = "default" | "xs" | "sm" | "lg" | "icon" | "icon-sm" | "icon-lg";
export type ButtonV2Props = React.ButtonHTMLAttributes<HTMLButtonElement> & { variant?: ButtonV2Variant; size?: ButtonV2Size };
export const ButtonV2 = React.forwardRef<HTMLButtonElement, ButtonV2Props>(function ButtonV2({ variant = "default", size = "default", type = "button", className, ...props }, ref) {
  return <button {...props} ref={ref} type={type} className={cx("hp-button", className)} data-hp-variant={variant} data-hp-size={size} />;
});
export const InputV2 = React.forwardRef<HTMLInputElement, React.InputHTMLAttributes<HTMLInputElement>>(function InputV2({ className, ...props }, ref) {
  return <input {...props} ref={ref} className={cx("hp-input", className)} />;
});
export const LabelV2 = React.forwardRef<HTMLLabelElement, React.LabelHTMLAttributes<HTMLLabelElement>>(function LabelV2({ className, ...props }, ref) {
  return <label {...props} ref={ref} className={cx("hp-label", className)} />;
});
export const TextareaV2 = React.forwardRef<HTMLTextAreaElement, React.TextareaHTMLAttributes<HTMLTextAreaElement>>(function TextareaV2({ className, ...props }, ref) {
  return <textarea {...props} ref={ref} className={cx("hp-textarea", className)} />;
});
export type CheckboxState = boolean | "indeterminate";
export type CheckboxProps = Omit<React.InputHTMLAttributes<HTMLInputElement>, "type" | "checked" | "defaultChecked"> & {
  checked?: CheckboxState; defaultChecked?: CheckboxState; onCheckedChange?: (checked: boolean) => void;
};
export const Checkbox = React.forwardRef<HTMLInputElement, CheckboxProps>(function Checkbox({ checked, defaultChecked = false, onCheckedChange, onChange, className, disabled, ...props }, ref) {
  const [state, setState] = useValue<CheckboxState>(checked, defaultChecked, next => onCheckedChange?.(next === true));
  const local = React.useRef<HTMLInputElement>(null);
  React.useImperativeHandle(ref, () => local.current!, []);
  useLayout(() => { if (local.current) local.current.indeterminate = state === "indeterminate"; }, [state]);
  return <span className={cx("hp-check-wrap", className)} data-hp-disabled={disabled || undefined}>
    <input {...props} ref={local} className="hp-checkbox" type="checkbox" checked={state === true} aria-checked={state === "indeterminate" ? "mixed" : state}
      disabled={disabled} onChange={event => { onChange?.(event); if (!event.defaultPrevented) setState(event.currentTarget.checked); }} />
    <span aria-hidden="true" className="hp-check-face" data-hp-checked={state !== false}><CheckMark mixed={state === "indeterminate"} /></span>
  </span>;
});
export type SwitchProps = Omit<React.ButtonHTMLAttributes<HTMLButtonElement>, "onChange" | "value" | "defaultValue"> & {
  checked?: boolean; defaultChecked?: boolean; onCheckedChange?: (checked: boolean) => void;
  size?: "md" | "sm" | "xs"; value?: string; form?: string;
};
export const Switch = React.forwardRef<HTMLButtonElement, SwitchProps>(function Switch({ checked, defaultChecked = false, onCheckedChange, size = "md", name, value = "on", form, disabled, onClick, className, type: _type, ...props }, ref) {
  const [state, set] = useValue(checked, defaultChecked, onCheckedChange);
  return <><button {...props} ref={ref} type="button" disabled={disabled} role="switch" aria-checked={state} form={form}
    className={cx("hp-switch", className)} data-hp-size={size} onClick={event => { onClick?.(event); if (!event.defaultPrevented && !disabled) set(!state); }}><span className="hp-switch-thumb" /></button>
    {name && state && <input type="hidden" name={name} value={value} form={form} disabled={disabled} />}</>;
});
/** Native radio grouping and arrow keys are intentionally delegated to the browser. */
export const RadioControl = React.forwardRef<HTMLInputElement, Omit<React.InputHTMLAttributes<HTMLInputElement>, "type">>(function RadioControl({ className, ...props }, ref) {
  return <input {...props} ref={ref} type="radio" className={cx("hp-radio", className)} />;
});
export type AvatarProps = Omit<React.HTMLAttributes<HTMLSpanElement>, "children"> & {
  name: string; src?: string; initials?: string; size?: "xs" | "sm" | "md" | "lg" | "xl";
  showPresence?: boolean; online?: boolean; presenceLabel?: string;
};
export function Avatar({ name, src, initials, size = "md", showPresence = false, online = false, presenceLabel = "온라인", className, ...props }: AvatarProps) {
  const [failed, setFailed] = React.useState<string>();
  const letters = initials ?? name.trim().split(/\s+/u).filter(Boolean).slice(0, 2).map(word => Array.from(word)[0]).join("").toLocaleUpperCase();
  const presence = showPresence && online;
  return <span {...props} className={cx("hp-avatar-wrap", className)} data-hp-size={size} role="img" aria-label={presence ? `${name}, ${presenceLabel}` : name}>
    <span className="hp-avatar" aria-hidden="true">{src && failed !== src ? <img src={src} alt="" onError={() => setFailed(src)} /> : letters || "?"}</span>
    {presence && <span className="hp-presence" aria-hidden="true" />}
  </span>;
}
export type BadgeVariant = "default" | "secondary" | "destructive" | "outline" | "muted" | "success" | "warning" | "private";
export function Badge({ variant = "default", className, ...props }: React.HTMLAttributes<HTMLSpanElement> & { variant?: BadgeVariant }) {
  return <span {...props} className={cx("hp-badge", className)} data-hp-variant={variant} />;
}
export type SelectOption = Readonly<{ value: string; label: string; disabled?: boolean; icon?: React.ReactNode }>;
export type SelectProps = {
  label: string; options: readonly SelectOption[]; value?: string | null; defaultValue?: string | null;
  onValueChange?: (value: string) => void; searchable?: boolean; searchPlaceholder?: string;
  placeholder?: string; emptyLabel?: string; disabled?: boolean; name?: string; form?: string;
  id?: string; className?: string; triggerClassName?: string; "aria-describedby"?: string; "aria-invalid"?: React.AriaAttributes["aria-invalid"];
};
export function Select({ label, options, value, defaultValue = null, onValueChange, searchable = false, searchPlaceholder = "옵션 검색", placeholder = "선택", emptyLabel = "일치하는 항목이 없습니다", disabled = false, name, form, id, className, triggerClassName, "aria-describedby": description, "aria-invalid": invalid }: SelectProps) {
  const [selected, setSelected] = useValue<string | null>(value, defaultValue, next => { if (next !== null) onValueChange?.(next); });
  const [open, setOpen] = React.useState(false);
  const [query, setQuery] = React.useState("");
  const [active, setActive] = React.useState<string | null>(null);
  const root = React.useRef<HTMLDivElement>(null), trigger = React.useRef<HTMLButtonElement>(null), input = React.useRef<HTMLInputElement>(null);
  const base = React.useId(), listId = `${base}-list`, optionId = (index: number) => `${base}-option-${index}`;
  const shown = options.filter(option => !searchable || option.label.toLocaleLowerCase().includes(query.toLocaleLowerCase()));
  const enabled = shown.filter(option => !option.disabled);
  const activeIndex = shown.findIndex(option => option.value === active && !option.disabled);
  const isOpen = open && !disabled;
  const typeahead = React.useRef({ text: "", time: 0 });
  const close = React.useCallback((restore = false) => { setOpen(false); setQuery(""); if (restore) trigger.current?.focus(); }, []);
  useDismiss(isOpen, root, reason => close(reason === "escape"));
  React.useEffect(() => { if (disabled) close(); }, [disabled, close]);
  React.useEffect(() => {
    if (!isOpen) return;
    const frame = requestAnimationFrame(() => { if (searchable) input.current?.focus(); });
    return () => cancelAnimationFrame(frame);
  }, [isOpen, searchable]);
  React.useEffect(() => {
    if (isOpen && !enabled.some(option => option.value === active)) setActive(enabled[0]?.value ?? null);
  }, [isOpen, query, options, active]);
  React.useEffect(() => { if (isOpen && activeIndex >= 0) root.current?.ownerDocument.getElementById(optionId(activeIndex))?.scrollIntoView?.({ block: "nearest" }); }, [isOpen, activeIndex]);
  const start = (last = false) => { if (disabled) return; setQuery(""); setActive(options.find(option => !option.disabled && option.value === selected)?.value ?? (last ? options.filter(o => !o.disabled).at(-1)?.value : options.find(o => !o.disabled)?.value) ?? null); setOpen(true); };
  const choose = (option?: SelectOption) => { if (!option || disabled || option.disabled) return; setSelected(option.value); close(true); };
  const keyboard = (event: React.KeyboardEvent<HTMLElement>) => {
    if (!canNavigate(event)) return;
    if (event.key === "Escape") { if (isOpen) { event.preventDefault(); event.stopPropagation(); close(true); } return; }
    if (event.key === "Tab") { close(); return; }
    if (["ArrowDown", "ArrowUp", "Home", "End"].includes(event.key) && (!searchable || !["Home", "End"].includes(event.key))) {
      event.preventDefault();
      if (!isOpen) { start(event.key === "ArrowUp" || event.key === "End"); return; }
      const index = enabled.findIndex(option => option.value === active);
      const next = event.key === "Home" ? 0 : event.key === "End" ? enabled.length - 1 : (index + (event.key === "ArrowUp" ? -1 : 1) + enabled.length) % enabled.length;
      setActive(enabled[next]?.value ?? null); return;
    }
    if (event.key === "Enter" || (!searchable && event.key === " ")) {
      event.preventDefault(); if (isOpen) choose(enabled.find(option => option.value === active)); else start(); return;
    }
    if (!searchable && event.key.length === 1 && event.key.trim()) {
      event.preventDefault(); const now = Date.now();
      typeahead.current = { text: now - typeahead.current.time < 700 ? typeahead.current.text + event.key : event.key, time: now };
      const match = options.find(option => !option.disabled && option.label.toLocaleLowerCase().startsWith(typeahead.current.text.toLocaleLowerCase()));
      if (match) { if (isOpen) setActive(match.value); else setSelected(match.value); }
    }
  };
  return <div ref={root} className={cx("hp-anchor", "hp-select", className)}>
    <button id={id} ref={trigger} type="button" disabled={disabled} className={cx("hp-select-trigger", triggerClassName)} role={searchable ? undefined : "combobox"}
      aria-label={label} aria-haspopup="listbox" aria-expanded={isOpen} aria-controls={isOpen ? listId : undefined} aria-describedby={description} aria-invalid={invalid}
      aria-activedescendant={!searchable && isOpen && activeIndex >= 0 ? optionId(activeIndex) : undefined}
      onKeyDown={keyboard} onClick={() => isOpen ? close() : start()}>
      <span className="hp-truncate" data-hp-placeholder={selected === null || undefined}>{options.find(option => option.value === selected)?.label ?? placeholder}</span><Chevron />
    </button>
    {name && <input type="hidden" name={name} form={form} value={selected ?? ""} disabled={disabled} />}
    {isOpen && <div className="hp-select-popup">
      {searchable && <div className="hp-select-search"><input ref={input} className="hp-input" value={query} placeholder={searchPlaceholder} aria-label={searchPlaceholder}
        role="combobox" aria-expanded="true" aria-autocomplete="list" aria-controls={listId} aria-activedescendant={activeIndex >= 0 ? optionId(activeIndex) : undefined}
        onChange={event => { setQuery(event.target.value); setActive(null); }} onKeyDown={keyboard} /></div>}
      <ul id={listId} role="listbox" aria-label={label} className="hp-select-list">{shown.map((option, index) => <li key={option.value} id={optionId(index)} role="option" aria-selected={option.value === selected}
        aria-disabled={option.disabled || undefined} data-hp-active={option.value === active || undefined} className="hp-select-option"
        onPointerDown={event => { if (event.button === 0) event.preventDefault(); }} onPointerMove={() => { if (!option.disabled) setActive(option.value); }} onClick={() => choose(option)}>
        {option.icon}<span className="hp-truncate">{option.label}</span>{option.value === selected && <CheckMark />}</li>)}</ul>
      {!shown.length && <div className="hp-empty" role="status">{emptyLabel}</div>}
    </div>}
  </div>;
}

type MenuBase = { id: string; label: string; disabled?: boolean; icon?: React.ReactNode; shortcut?: string; destructive?: boolean };
export type DropdownMenuItem =
  | (MenuBase & { type?: "action"; onSelect?: () => void })
  | (MenuBase & { type: "checkbox"; checked: boolean; onCheckedChange: (checked: boolean) => void; closeOnSelect?: boolean })
  | (MenuBase & { type: "radio"; checked: boolean; onSelect: () => void; closeOnSelect?: boolean })
  | (MenuBase & { type: "submenu"; items: readonly DropdownMenuItem[] })
  | { id: string; type: "separator" }
  | { id: string; type: "label"; label: string };
export type DropdownMenuProps = {
  trigger: React.ReactNode; label: string; items: readonly DropdownMenuItem[]; disabled?: boolean;
  open?: boolean; defaultOpen?: boolean; onOpenChange?: (open: boolean) => void;
  align?: "start" | "end"; className?: string; triggerClassName?: string;
};
function MenuPanel({ items, label, id, autoFocus = true, last = false, finish, back }: {
  items: readonly DropdownMenuItem[]; label: string; id: string; autoFocus?: boolean; last?: boolean; finish: () => void; back?: () => void;
}) {
  const panel = React.useRef<HTMLDivElement>(null);
  const [submenu, setSubmenu] = React.useState<string | null>(null);
  const [subFocus, setSubFocus] = React.useState(false);
  const search = React.useRef({ text: "", time: 0 });
  const buttons = () => Array.from(panel.current?.querySelectorAll<HTMLButtonElement>(":scope > .hp-menu-row > .hp-menu-item:not(:disabled)") ?? []);
  React.useEffect(() => {
    if (!autoFocus) return;
    const frame = requestAnimationFrame(() => { const nodes = buttons(); (last ? nodes.at(-1) : nodes[0])?.focus(); });
    return () => cancelAnimationFrame(frame);
  }, [autoFocus, last]);
  return <div id={id} ref={panel} role="menu" aria-label={label} className="hp-menu" onKeyDown={event => {
    if (!canNavigate(event)) return;
    if (event.key === "Escape" && back) { event.preventDefault(); event.stopPropagation(); back(); return; }
    if (event.key === "ArrowLeft" && back) { event.preventDefault(); event.stopPropagation(); back(); return; }
    const nodes = buttons(); const index = nodes.indexOf(event.target as HTMLButtonElement);
    if (["ArrowDown", "ArrowUp", "Home", "End"].includes(event.key)) {
      event.preventDefault(); event.stopPropagation(); setSubmenu(null);
      const next = event.key === "Home" ? 0 : event.key === "End" ? nodes.length - 1 : (index + (event.key === "ArrowUp" ? -1 : 1) + nodes.length) % nodes.length;
      nodes[next]?.focus();
    } else if (event.key === "Tab") { event.stopPropagation(); setSubmenu(null); finish(); }
    else if (event.key.length === 1 && event.key.trim()) {
      event.stopPropagation(); const now = Date.now(); search.current = { text: now - search.current.time < 700 ? search.current.text + event.key : event.key, time: now };
      const match = [...nodes.slice(index + 1), ...nodes.slice(0, index + 1)].find(node => node.dataset.hpLabel?.toLocaleLowerCase().startsWith(search.current.text.toLocaleLowerCase()));
      match?.focus();
    }
  }}>
    {items.map(item => {
      if (item.type === "separator") return <div role="separator" className="hp-menu-separator" key={item.id} />;
      if (item.type === "label") return <div role="presentation" className="hp-menu-label" key={item.id}>{item.label}</div>;
      const subId = `${id}-sub-${encodeURIComponent(item.id)}`, isSub = item.type === "submenu", isChecked = item.type === "checkbox" || item.type === "radio";
      return <div key={item.id} className="hp-menu-row" role="none">
        <button type="button" role={item.type === "checkbox" ? "menuitemcheckbox" : item.type === "radio" ? "menuitemradio" : "menuitem"} tabIndex={-1} disabled={item.disabled}
          className="hp-menu-item" data-hp-label={item.label} data-hp-destructive={item.destructive || undefined} aria-checked={isChecked ? item.checked : undefined}
          aria-haspopup={isSub ? "menu" : undefined} aria-expanded={isSub ? submenu === item.id : undefined} aria-controls={isSub && submenu === item.id ? subId : undefined}
          onFocus={() => { if (submenu !== item.id) setSubmenu(null); }}
          onPointerMove={event => { if (event.pointerType === "mouse" && !item.disabled) event.currentTarget.focus(); }}
          onKeyDown={event => { if (isSub && event.key === "ArrowRight" && canNavigate(event)) { event.preventDefault(); event.stopPropagation(); setSubFocus(true); setSubmenu(item.id); } }}
          onClick={() => {
            if (item.disabled) return;
            if (item.type === "submenu") { setSubFocus(true); setSubmenu(submenu === item.id ? null : item.id); return; }
            if (item.type === "checkbox") { item.onCheckedChange(!item.checked); if (item.closeOnSelect) finish(); }
            else if (item.type === "radio") { item.onSelect(); if (item.closeOnSelect !== false) finish(); }
            else { item.onSelect?.(); finish(); }
          }}>
          {isChecked ? <span className="hp-menu-indicator">{item.checked && (item.type === "radio" ? <span className="hp-radio-dot" /> : <CheckMark />)}</span> : item.icon}
          <span className="hp-truncate">{item.label}</span>{item.shortcut && <span className="hp-menu-shortcut">{item.shortcut}</span>}{isSub && <Chevron right />}
        </button>
        {item.type === "submenu" && submenu === item.id && <div className="hp-submenu-position"><MenuPanel id={subId} label={item.label} items={item.items} autoFocus={subFocus} finish={finish}
          back={() => { setSubmenu(null); panel.current?.querySelectorAll<HTMLButtonElement>(":scope > .hp-menu-row > .hp-menu-item").forEach(node => { if (node.dataset.hpLabel === item.label) node.focus(); }); }} /></div>}
      </div>;
    })}
  </div>;
}
export function DropdownMenu({ trigger: content, label, items, disabled, open: controlled, defaultOpen = false, onOpenChange, align = "start", className, triggerClassName }: DropdownMenuProps) {
  const [open, set] = useValue(controlled, defaultOpen, onOpenChange);
  const [last, setLast] = React.useState(false);
  const root = React.useRef<HTMLDivElement>(null), trigger = React.useRef<HTMLButtonElement>(null), id = React.useId();
  const shown = open && !disabled;
  const finish = () => { set(false); trigger.current?.focus(); };
  useDismiss(shown, root, reason => { set(false); if (reason === "escape") trigger.current?.focus(); });
  React.useEffect(() => { if (disabled) set(false); }, [disabled, set]);
  return <div className={cx("hp-anchor", className)} ref={root}>
    <button ref={trigger} type="button" className={cx("hp-trigger", triggerClassName)} disabled={disabled} aria-label={label} aria-haspopup="menu" aria-expanded={shown} aria-controls={shown ? id : undefined}
      onClick={() => { setLast(false); set(!open); }} onKeyDown={event => { if (canNavigate(event) && ["ArrowDown", "ArrowUp"].includes(event.key)) { event.preventDefault(); setLast(event.key === "ArrowUp"); set(true); } }}>{content}</button>
    {shown && <div className="hp-menu-position" data-hp-align={align}><MenuPanel items={items} label={label} id={id} last={last} finish={finish} /></div>}
  </div>;
}

export type FloatingProps = {
  trigger: React.ReactNode; label: string; children: React.ReactNode;
  open?: boolean; defaultOpen?: boolean; onOpenChange?: (open: boolean) => void; disabled?: boolean;
  side?: "top" | "bottom" | "left" | "right"; align?: "start" | "center" | "end";
  className?: string; triggerClassName?: string; contentClassName?: string;
};
function Floating({ trigger: content, label, children, open: controlled, defaultOpen = false, onOpenChange, disabled, side = "bottom", align = "center", className, triggerClassName, contentClassName, hover = false, openDelay = 300, closeDelay = 150 }: FloatingProps & { hover?: boolean; openDelay?: number; closeDelay?: number }) {
  const [open, set] = useValue(controlled, defaultOpen, onOpenChange);
  const root = React.useRef<HTMLDivElement>(null), trigger = React.useRef<HTMLButtonElement>(null), panel = React.useRef<HTMLDivElement>(null), timer = React.useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  const id = React.useId(), shown = open && !disabled;
  const clear = () => { if (timer.current !== undefined) clearTimeout(timer.current); timer.current = undefined; };
  const schedule = (next: boolean, delay: number) => { clear(); if (!disabled) timer.current = setTimeout(() => set(next), Math.max(0, delay)); };
  useDismiss(shown, root, reason => { clear(); set(false); if (reason === "escape") trigger.current?.focus(); });
  React.useEffect(() => () => clear(), []);
  React.useEffect(() => { if (disabled) { clear(); set(false); } }, [disabled, set]);
  React.useEffect(() => {
    if (!shown || hover) return;
    const frame = requestAnimationFrame(() => { if (panel.current) (focusables(panel.current)[0] ?? panel.current).focus(); });
    return () => cancelAnimationFrame(frame);
  }, [shown, hover]);
  return <div ref={root} className={cx("hp-anchor", className)} onPointerEnter={hover ? () => schedule(true, openDelay) : undefined}
    onPointerLeave={hover ? () => { if (!root.current?.contains(root.current.ownerDocument.activeElement)) schedule(false, closeDelay); } : undefined}
    onFocusCapture={hover ? () => { clear(); if (!disabled) set(true); } : undefined}
    onBlurCapture={hover ? event => { if (!event.currentTarget.contains(event.relatedTarget)) schedule(false, closeDelay); } : undefined}>
    <button type="button" ref={trigger} disabled={disabled} className={cx("hp-trigger", triggerClassName)} aria-label={label} aria-haspopup="dialog" aria-expanded={shown} aria-controls={shown ? id : undefined}
      onClick={() => { clear(); set(!open); }}>{content}</button>
    {shown && <div ref={panel} id={id} role="dialog" aria-label={label} tabIndex={-1} data-hp-side={side} data-hp-align={align}
      className={cx("hp-float", hover ? "hp-hover-card" : "hp-popover", contentClassName)}>{children}</div>}
  </div>;
}
export function Popover(props: FloatingProps) { return <Floating {...props} />; }
export function HoverCard(props: FloatingProps & { openDelay?: number; closeDelay?: number }) { return <Floating {...props} hover />; }
export type TooltipProps = {
  children: React.ReactElement<React.HTMLAttributes<HTMLElement>>; content: React.ReactNode;
  side?: "top" | "bottom" | "left" | "right"; delay?: number; disabled?: boolean; className?: string;
};
export function Tooltip({ children, content, side = "top", delay = 300, disabled = false, className }: TooltipProps) {
  const [open, set] = React.useState(false);
  const root = React.useRef<HTMLSpanElement>(null), timer = React.useRef<ReturnType<typeof setTimeout> | undefined>(undefined), id = React.useId();
  const clear = () => { if (timer.current !== undefined) clearTimeout(timer.current); timer.current = undefined; };
  const close = () => { clear(); set(false); };
  useDismiss(open && !disabled, root, close);
  React.useEffect(() => () => clear(), []);
  React.useEffect(() => { if (disabled) close(); }, [disabled]);
  return <span ref={root} className="hp-anchor" onPointerEnter={() => { clear(); if (!disabled) timer.current = setTimeout(() => set(true), Math.max(0, delay)); }}
    onPointerLeave={close} onFocusCapture={() => { clear(); if (!disabled) set(true); }} onBlurCapture={event => { if (!event.currentTarget.contains(event.relatedTarget)) close(); }}>
    {React.cloneElement(children, { "aria-describedby": cx(children.props["aria-describedby"], open && !disabled && id) || undefined })}
    {open && !disabled && <span id={id} role="tooltip" className={cx("hp-float", "hp-tooltip", className)} data-hp-side={side} data-hp-align="center">{content}</span>}
  </span>;
}
export type TabItem = Readonly<{ value: string; label: string; content: React.ReactNode; disabled?: boolean }>;
export type TabsProps = {
  label: string; items: readonly TabItem[]; value?: string; defaultValue?: string; onValueChange?: (value: string) => void;
  variant?: "segmented" | "underline"; activation?: "automatic" | "manual"; className?: string;
};
export function Tabs({ label, items, value, defaultValue, onValueChange, variant = "segmented", activation = "automatic", className }: TabsProps) {
  const [selected, set] = useValue(value, defaultValue ?? items.find(item => !item.disabled)?.value ?? "", onValueChange);
  const [focused, setFocused] = React.useState(selected);
  const id = React.useId(), nodes = React.useRef(new Map<string, HTMLButtonElement>());
  const enabled = items.filter(item => !item.disabled);
  const tabValue = enabled.some(item => item.value === focused) ? focused : enabled.find(item => item.value === selected)?.value ?? enabled[0]?.value;
  const selectedIndex = items.findIndex(item => !item.disabled && item.value === selected);
  React.useEffect(() => { setFocused(selected); }, [selected]);
  return <div className={cx("hp-tabs", className)} data-hp-variant={variant}>
    <div role="tablist" aria-label={label} className="hp-tabs-list" onKeyDown={event => {
      if (!canNavigate(event) || !["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key) || !enabled.length) return;
      event.preventDefault(); const rtl = getComputedStyle(event.currentTarget).direction === "rtl";
      const index = enabled.findIndex(item => nodes.current.get(item.value) === event.target);
      const increment = (event.key === "ArrowLeft" ? -1 : 1) * (rtl ? -1 : 1);
      const next = enabled[event.key === "Home" ? 0 : event.key === "End" ? enabled.length - 1 : (Math.max(0, index) + increment + enabled.length) % enabled.length];
      if (next) { setFocused(next.value); nodes.current.get(next.value)?.focus(); if (activation === "automatic") set(next.value); }
    }}>{items.map((item, index) => <button key={item.value} ref={node => { if (node) nodes.current.set(item.value, node); else nodes.current.delete(item.value); }}
      id={`${id}-tab-${index}`} type="button" role="tab" className="hp-tab" disabled={item.disabled} aria-selected={selectedIndex === index} aria-controls={`${id}-panel-${index}`}
      tabIndex={item.value === tabValue ? 0 : -1} onFocus={() => setFocused(item.value)} onClick={() => set(item.value)}>{item.label}</button>)}</div>
    {items.map((item, index) => <div key={item.value} id={`${id}-panel-${index}`} role="tabpanel" tabIndex={0} aria-labelledby={`${id}-tab-${index}`} hidden={index !== selectedIndex} className="hp-tab-panel">{item.content}</div>)}
  </div>;
}
export type ScrollAreaProps = React.HTMLAttributes<HTMLDivElement> & { label: string; orientation?: "vertical" | "horizontal" | "both" };
export const ScrollArea = React.forwardRef<HTMLDivElement, ScrollAreaProps>(function ScrollArea({ label, orientation = "vertical", className, tabIndex = 0, ...props }, ref) {
  return <div {...props} ref={ref} role="region" aria-label={label} tabIndex={tabIndex} className={cx("hp-scroll-area", className)} data-hp-orientation={orientation} />;
});
export function Separator({ orientation = "horizontal", decorative = true, className, ...props }: React.HTMLAttributes<HTMLDivElement> & { orientation?: "horizontal" | "vertical"; decorative?: boolean }) {
  return <div {...props} className={cx("hp-separator", className)} data-hp-orientation={orientation} role={decorative ? "none" : "separator"} aria-hidden={decorative || undefined} aria-orientation={decorative ? undefined : orientation} />;
}
export function Skeleton({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) { return <div {...props} aria-hidden="true" className={cx("hp-skeleton", className)} />; }
export function Spinner({ size = 16, label = "불러오는 중", className, ...props }: Omit<React.HTMLAttributes<HTMLSpanElement>, "children"> & { size?: number; label?: string }) {
  return <span {...props} role="status" className={cx("hp-spinner", className)}><svg aria-hidden="true" width={size} height={size} viewBox="0 0 24 24" fill="none"><circle cx="12" cy="12" r="9" stroke="currentColor" strokeWidth="2" opacity=".2" /><path d="M12 3a9 9 0 0 1 9 9" stroke="currentColor" strokeWidth="2" strokeLinecap="round" /></svg><span className="hp-sr-only">{label}</span></span>;
}
