/**
 * README: independent reconstruction. Only React is required. No imports from
 * the other kits. Load ramus.css for .ramus tokens, then ramus-advanced.css.
 * Wrap in the existing RamusProvider or another .ramus token scope.
 *
 * SOURCE-CONFIRMED RECIPES (not copied modules or official vendor APIs):
 * request-card-DRvRhM9x: StructuredCard, OptionRow/Group, Hint, CardFooter.
 * entity-menu-D70clu3c: ActionRow/Sheet and point-context-menu composition.
 * reload-screen-BSKiqJk2 + measure24: icon search, eight-column 36px icon cells,
 * 20px color swatches, 304px popover; measure60: status composition.
 * move-menu-item-g_rcZJ-z + measure33: search/listbox/category symbol surface.
 * tooltip-DgbuciXR + measure54: descriptive destructive alert dialog.
 * import-deck-dialog-D_HulIDs: centered gap12/py16 import summary layout.
 * measure17/23: card/field/button visual vocabulary. measure58: disclosure
 * trigger recipe. Its content panel is a RECOMMENDED composition, not observed.
 * toast-computed.json: actual Ramus custom group radius16/p16/gap12/width356,
 * title14/20 and description14/20, CTA24/radius8. Generic Sonner package
 * p16/font13/gap6 is NOT the recovered custom-card recipe; height is content-led.
 *
 * ACCESSIBILITY / UNOBSERVED BEHAVIOR RECONSTRUCTION:
 * Native dialog focus containment, initial cancel focus and return focus;
 * Escape, outside dismissal, roving grid/menu focus, typeahead, viewport clamp,
 * timer pause/cleanup and live announcements are independent implementations.
 * Icon/symbol/preset data is supplied by callers. No original registry, account
 * data, uploads, storage, expiry scheduling, business action or network is built in.
 * FileDropzone is an import-inspired UI assembly, not a recovered exact dropzone.
 *
 * LIMITS: showModal() is required for modal components. ContextMenu is local
 * fixed positioning, NOT a portal/vendor collision engine; transformed ancestors
 * can change its containing block. No long-press, subviews, vendor API, rich
 * menus, swipe toast dismissal or vendor stack animation. Pickers stay inside
 * their token scope and can be clipped by overflow ancestors. Toast viewport
 * placement/timing and disclosure panel layout are additions. Accept is only a
 * file-picker hint; the caller must validate dropped files. Controlled callbacks
 * must accept state changes. Items/category ids must be unique and nonempty. Async confirmation/save closes on resolved success;
 * rejection keeps the dialog open with a caller-configurable generic error.
 */
import * as React from "react";
const join = (...values: Array<string | false | null | undefined>) => values.filter(Boolean).join(" ");
const useLayout = typeof window === "undefined" ? React.useEffect : React.useLayoutEffect;
function useLatest<T>(value: T) { const ref = React.useRef(value); useLayout(() => { ref.current = value; }); return ref; }
function useValue<T>(value: T | undefined, initial: T, onChange?: (next: T) => void): [T, (next: T) => void] {
  const [own, update] = React.useState(initial);
  const current = value === undefined ? own : value;
  const latest = useLatest({ current, controlled: value !== undefined, onChange });
  const set = React.useCallback((next: T) => { const state = latest.current; if (Object.is(state.current, next)) return; if (!state.controlled) update(next); state.onChange?.(next); }, [latest]);
  return [current, set];
}
const navigable = (e: React.KeyboardEvent) => !e.defaultPrevented && !e.altKey && !e.ctrlKey && !e.metaKey && !e.nativeEvent.isComposing && e.nativeEvent.keyCode !== 229;
function Arrow({ down = false }: { down?: boolean }) { return <svg className="ha-arrow" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true"><path d={down ? "m4 6 4 4 4-4" : "m6 4 4 4-4 4"} /></svg>; }
function useNativeDialog(open: boolean, dialog: React.RefObject<HTMLDialogElement | null>, initial: React.RefObject<HTMLElement | null>) {
  const previous = React.useRef<HTMLElement | null>(null);
  const restore = React.useCallback(() => { const node = previous.current; previous.current = null; if (node?.isConnected) node.focus(); }, []);
  useLayout(() => {
    const node = dialog.current;
    if (!node) return;
    let frame = 0;
    if (open && !node.open && typeof node.showModal === "function") {
      const active = node.ownerDocument.activeElement;
      previous.current = active instanceof HTMLElement ? active : null;
      node.showModal();
      frame = requestAnimationFrame(() => { const target = initial.current; if (target && !(target instanceof HTMLButtonElement && target.disabled)) target.focus(); else node.focus(); });
    } else if (!open) { if (node.open) node.close(); restore(); }
    return () => { if (frame) cancelAnimationFrame(frame); };
  }, [open, dialog, initial, restore]);
  React.useEffect(() => { const node = dialog.current; return () => { if (node?.open) node.close(); restore(); }; }, [dialog, restore]);
}
function useAsyncAction() {
  const [pending, setPending] = React.useState(false), [failed, setFailed] = React.useState(false);
  const mounted = React.useRef(true), locked = React.useRef(false);
  React.useEffect(() => { mounted.current = true; return () => { mounted.current = false; }; }, []);
  const run = async (action: () => void | Promise<void>, success: () => void) => {
    if (locked.current) return;
    locked.current = true; setPending(true); setFailed(false);
    try { await action(); if (mounted.current) success(); }
    catch { if (mounted.current) setFailed(true); }
    finally { locked.current = false; if (mounted.current) setPending(false); }
  };
  return { pending, failed, run, clear: () => setFailed(false) };
}
export type StructuredCardProps = Omit<React.HTMLAttributes<HTMLDivElement>, "title"> & {
  title: React.ReactNode; icon?: React.ReactNode; accessory?: React.ReactNode; eyebrow?: React.ReactNode; description?: React.ReactNode;
};
export function StructuredCard({ title, icon, accessory, eyebrow, description, children, className, ...props }: StructuredCardProps) {
  return <div {...props} className={join("ha-card", className)}>{eyebrow && <div className="ha-card-eyebrow" data-ha-icon={!!icon}>{eyebrow}</div>}
    <div className="ha-card-heading" data-ha-icon={!!icon} data-ha-eyebrow={!!eyebrow}>
      {icon && <span className="ha-card-icon" aria-hidden="true">{icon}</span>}
      <div className="ha-card-title">{title}</div>{accessory && <div className="ha-card-accessory">{accessory}</div>}
      {description && <div className="ha-card-description">{description}</div>}
    </div>{children}</div>;
}
export type OptionRowProps = Omit<React.ButtonHTMLAttributes<HTMLButtonElement>, "children"> & {
  label: React.ReactNode; icon?: React.ReactNode; trailing?: React.ReactNode; gloss?: React.ReactNode;
  pressed?: boolean; current?: React.AriaAttributes["aria-current"];
};
export const OptionRow = React.forwardRef<HTMLButtonElement, OptionRowProps>(function OptionRow({ label, icon, trailing, gloss, pressed, current, className, "aria-describedby": external, ...props }, ref) {
  const id = React.useId();
  return <button {...props} ref={ref} type="button" className={join("ha-option-row", className)} data-ha-gloss={!!gloss}
    aria-pressed={pressed} aria-current={current} aria-describedby={join(external, !!gloss && id) || undefined}>
    {icon && <span className="ha-option-icon" aria-hidden="true">{icon}</span>}
    <span className="ha-option-copy"><span>{label}</span>{gloss && <span id={id} className="ha-option-gloss">{gloss}</span>}</span>
    {trailing && <span className="ha-option-trailing" aria-hidden="true">{trailing}</span>}</button>;
});
export function OptionGroup({ label, className, ...props }: React.HTMLAttributes<HTMLDivElement> & { label?: string }) { return <div {...props} role={label ? "group" : undefined} aria-label={label} className={join("ha-option-group", className)} />; }
export function Hint({ className, ...props }: React.HTMLAttributes<HTMLParagraphElement>) { return <p {...props} className={join("ha-hint", className)} />; }
export function CardFooter({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) { return <div {...props} className={join("ha-card-footer", className)} />; }
export type ActionRowProps = Omit<React.ButtonHTMLAttributes<HTMLButtonElement>, "children"> & { label: React.ReactNode; icon?: React.ReactNode; trailing?: React.ReactNode; destructive?: boolean; multiline?: boolean; checked?: boolean };
export const ActionRow = React.forwardRef<HTMLButtonElement, ActionRowProps>(function ActionRow({ label, icon, trailing, destructive = false, multiline = false, checked, className, ...props }, ref) {
  return <button {...props} ref={ref} type="button" role={checked === undefined ? undefined : "switch"} aria-checked={checked}
    className={join("ha-action-row", className)} data-ha-destructive={destructive} data-ha-multiline={multiline}>
    {icon && <span className="ha-action-icon" aria-hidden="true">{icon}</span>}<span className="ha-action-label">{label}</span>
    {trailing && <span className="ha-action-trailing" aria-hidden="true">{trailing}</span>}</button>;
});
export type ActionItem = Readonly<{ id: string; label: string; icon?: React.ReactNode; trailing?: React.ReactNode; disabled?: boolean; destructive?: boolean; onSelect?: () => void; closeOnSelect?: boolean }>;
export type ContextMenuProps = Omit<React.HTMLAttributes<HTMLDivElement>, "children"> & { children: React.ReactNode; label: string; items: readonly ActionItem[]; disabled?: boolean };
export function ContextMenu({ children, label, items, disabled = false, className, onContextMenu, onKeyDown, ...props }: ContextMenuProps) {
  const [point, setPoint] = React.useState<{ x: number; y: number } | null>(null), [position, setPosition] = React.useState({ x: 0, y: 0 });
  const root = React.useRef<HTMLDivElement>(null), menu = React.useRef<HTMLDivElement>(null), previous = React.useRef<HTMLElement | null>(null);
  const search = React.useRef({ text: "", time: 0 }), id = React.useId();
  const close = React.useCallback((restore: boolean) => { setPoint(null); if (restore && previous.current?.isConnected) previous.current.focus(); }, []);
  const buttons = () => Array.from(menu.current?.querySelectorAll<HTMLButtonElement>("button:not(:disabled)") ?? []);
  const start = (x: number, y: number, origin: EventTarget | null) => { if (disabled) return; previous.current = origin instanceof HTMLElement ? origin : root.current; setPosition({ x, y }); setPoint({ x, y }); };
  useLayout(() => {
    const node = menu.current;
    if (!point || !node) return;
    const clamp = () => { const rect = node.getBoundingClientRect(); const doc = node.ownerDocument.documentElement;
      setPosition({ x: Math.max(8, Math.min(point.x, doc.clientWidth - rect.width - 8)), y: Math.max(8, Math.min(point.y, doc.clientHeight - rect.height - 8)) }); };
    clamp(); const observer = typeof ResizeObserver === "undefined" ? null : new ResizeObserver(clamp); observer?.observe(node);
    const frame = requestAnimationFrame(() => buttons()[0]?.focus());
    window.addEventListener("resize", clamp);
    return () => { observer?.disconnect(); cancelAnimationFrame(frame); window.removeEventListener("resize", clamp); };
  }, [point]);
  React.useEffect(() => {
    if (!point) return;
    const doc = menu.current?.ownerDocument ?? document;
    const outside = (event: Event) => { if (event.target instanceof Node && !menu.current?.contains(event.target)) close(false); };
    const escape = (event: KeyboardEvent) => { if (event.key === "Escape" && !event.isComposing) { event.preventDefault(); event.stopPropagation(); close(true); } };
    const scroll = (event: Event) => { if (event.target instanceof Node && !menu.current?.contains(event.target)) close(false); };
    doc.addEventListener("pointerdown", outside, true); doc.addEventListener("focusin", outside, true); doc.addEventListener("keydown", escape); doc.addEventListener("scroll", scroll, true);
    return () => { doc.removeEventListener("pointerdown", outside, true); doc.removeEventListener("focusin", outside, true); doc.removeEventListener("keydown", escape); doc.removeEventListener("scroll", scroll, true); };
  }, [point, close]);
  React.useEffect(() => { if (disabled) close(false); }, [disabled, close]);
  React.useEffect(() => () => { if (menu.current?.contains(document.activeElement) && previous.current?.isConnected) previous.current.focus(); }, []);
  return <div {...props} ref={root} className={join("ha-context-root", className)} tabIndex={props.tabIndex ?? 0} onContextMenu={event => {
    onContextMenu?.(event); if (event.defaultPrevented || disabled || (event.target instanceof Element && event.target.closest('input,textarea,select,[contenteditable="true"]'))) return;
    event.preventDefault(); const active = event.currentTarget.ownerDocument.activeElement; start(event.clientX, event.clientY, active instanceof HTMLElement && event.currentTarget.contains(active) ? active : event.currentTarget);
  }} onKeyDown={event => {
    onKeyDown?.(event); if (event.defaultPrevented || disabled || (event.target instanceof Node && menu.current?.contains(event.target))) return;
    if ((event.shiftKey && event.key === "F10") || event.key === "ContextMenu") { event.preventDefault(); const target = event.target instanceof HTMLElement ? event.target : event.currentTarget; const rect = target.getBoundingClientRect(); start(rect.left, rect.bottom, target); }
  }}>{children}{point && <div ref={menu} id={id} role="menu" aria-label={label} className="ha-context-menu" style={{ left: position.x, top: position.y }} onContextMenu={event => event.preventDefault()} onKeyDown={event => {
    if (!navigable(event)) return;
    const nodes = buttons(), index = nodes.indexOf(event.target as HTMLButtonElement);
    if (["ArrowDown", "ArrowUp", "Home", "End"].includes(event.key)) { event.preventDefault(); event.stopPropagation(); const next = event.key === "Home" ? 0 : event.key === "End" ? nodes.length - 1 : (index + (event.key === "ArrowUp" ? -1 : 1) + nodes.length) % nodes.length; nodes[next]?.focus(); }
    else if (event.key === "Tab") { close(true); }
    else if (event.key.length === 1 && event.key.trim()) { event.preventDefault(); const now = Date.now(); search.current = { text: now - search.current.time < 700 ? search.current.text + event.key : event.key, time: now }; [...nodes.slice(index + 1), ...nodes.slice(0, index + 1)].find(node => node.dataset.haLabel?.toLocaleLowerCase().startsWith(search.current.text.toLocaleLowerCase()))?.focus(); }
  }}>{items.map(item => <button type="button" key={item.id} role="menuitem" tabIndex={-1} disabled={item.disabled} data-ha-label={item.label} data-ha-destructive={item.destructive || undefined} className="ha-context-item" onClick={() => { if (!item.disabled) { item.onSelect?.(); if (item.closeOnSelect !== false) close(true); } }}>{item.icon}<span>{item.label}</span>{item.trailing && <span className="ha-context-trailing">{item.trailing}</span>}</button>)}</div>}</div>;
}
export type ActionSheetProps = { open: boolean; onOpenChange: (open: boolean) => void; title: string; items: readonly ActionItem[]; cancelLabel?: string; className?: string };
export function ActionSheet({ open, onOpenChange, title, items, cancelLabel = "취소", className }: ActionSheetProps) {
  const dialog = React.useRef<HTMLDialogElement>(null), cancel = React.useRef<HTMLButtonElement>(null), id = React.useId();
  useNativeDialog(open, dialog, cancel);
  return <dialog ref={dialog} className={join("ha-dialog", "ha-sheet", className)} aria-labelledby={id} onCancel={event => { event.preventDefault(); onOpenChange(false); }} onClose={() => { if (open) onOpenChange(false); }} onClick={event => { if (event.target === event.currentTarget) { const rect = event.currentTarget.getBoundingClientRect(); if (event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom) onOpenChange(false); } }}>
    <h2 id={id} className="ha-sheet-title">{title}</h2><div className="ha-sheet-actions">{items.map(item => <ActionRow key={item.id} icon={item.icon} trailing={item.trailing} label={item.label} disabled={item.disabled} destructive={item.destructive} onClick={() => { item.onSelect?.(); if (item.closeOnSelect !== false) onOpenChange(false); }} />)}</div>
    <div className="ha-sheet-cancel"><button ref={cancel} type="button" className="ha-button ha-button-outline" onClick={() => onOpenChange(false)}>{cancelLabel}</button></div></dialog>;
}
function usePopup(open: boolean, root: React.RefObject<HTMLDivElement | null>, trigger: React.RefObject<HTMLButtonElement | null>, close: () => void) {
  const closeRef = useLatest(close);
  React.useEffect(() => {
    if (!open || !root.current) return;
    const doc = root.current.ownerDocument;
    const outside = (event: Event) => { if (event.target instanceof Node && !root.current?.contains(event.target)) closeRef.current(); };
    const escape = (event: KeyboardEvent) => { if (event.key === "Escape" && !event.isComposing) { event.preventDefault(); event.stopPropagation(); closeRef.current(); trigger.current?.focus(); } };
    doc.addEventListener("pointerdown", outside, true); doc.addEventListener("focusin", outside, true); doc.addEventListener("keydown", escape);
    const frame = requestAnimationFrame(() => root.current?.querySelector<HTMLInputElement>('.ha-popup input[type="search"]')?.focus());
    return () => { cancelAnimationFrame(frame); doc.removeEventListener("pointerdown", outside, true); doc.removeEventListener("focusin", outside, true); doc.removeEventListener("keydown", escape); };
  }, [open, root, trigger, closeRef]);
}
function gridKey(event: React.KeyboardEvent<HTMLDivElement>, columns: number) {
  if (!navigable(event) || !["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown", "Home", "End"].includes(event.key)) return;
  const nodes = Array.from(event.currentTarget.querySelectorAll<HTMLButtonElement>("button:not(:disabled)"));
  if (!nodes.length) return; event.preventDefault();
  const index = Math.max(0, nodes.indexOf(event.target as HTMLButtonElement)), rtl = getComputedStyle(event.currentTarget).direction === "rtl";
  const step = event.key === "ArrowUp" ? -columns : event.key === "ArrowDown" ? columns : (event.key === "ArrowLeft" ? -1 : 1) * (rtl ? -1 : 1);
  const next = event.key === "Home" ? 0 : event.key === "End" ? nodes.length - 1 : Math.max(0, Math.min(nodes.length - 1, index + step)); nodes[next]?.focus();
}
export type IconChoice = Readonly<{ value: string; label: string; icon: React.ReactNode; keywords?: readonly string[]; disabled?: boolean }>;
export type ColorChoice = Readonly<{ value: string; label: string; color: string; disabled?: boolean }>;
export type IconColorValue = Readonly<{ icon: string | null; color: string | null }>;
export type IconColorPickerProps = { label: string; options: readonly IconChoice[]; colors: readonly ColorChoice[]; value: IconColorValue; onChange: (value: IconColorValue) => void; disabled?: boolean; searchLabel?: string; emptyLabel?: string; className?: string };
export function IconColorPicker({ label, options, colors, value, onChange, disabled, searchLabel = "아이콘 검색", emptyLabel = "아이콘이 없습니다", className }: IconColorPickerProps) {
  const [open, setOpen] = React.useState(false), [query, setQuery] = React.useState(""), [focus, setFocus] = React.useState(0);
  const root = React.useRef<HTMLDivElement>(null), trigger = React.useRef<HTMLButtonElement>(null), id = React.useId();
  const shown = options.filter(option => `${option.label} ${option.keywords?.join(" ") ?? ""}`.toLocaleLowerCase().includes(query.toLocaleLowerCase()));
  usePopup(open && !disabled, root, trigger, () => setOpen(false));
  React.useEffect(() => { if (disabled) setOpen(false); }, [disabled]);
  const chosen = options.find(option => option.value === value.icon), color = colors.find(item => item.value === value.color);
  return <div ref={root} className={join("ha-picker-root", className)}><button ref={trigger} type="button" className="ha-picker-trigger" aria-label={label} aria-haspopup="dialog" aria-expanded={open && !disabled} aria-controls={open ? id : undefined} disabled={disabled} onClick={() => { setQuery(""); setFocus(0); setOpen(!open); }} style={{ color: color?.color }}>{chosen?.icon ?? <span>{label}</span>}</button>
    {open && !disabled && <div id={id} role="dialog" aria-label={label} className="ha-popup ha-icon-popup"><div className="ha-picker-search"><input type="search" className="ha-input" aria-label={searchLabel} placeholder={searchLabel} value={query} onChange={event => { setQuery(event.target.value); setFocus(0); }} /></div>
      <div className="ha-color-row" role="radiogroup" aria-label="아이콘 색상" onKeyDown={event => { if (!navigable(event)) return; gridKey(event, 1); if (event.defaultPrevented) { const target = event.currentTarget.ownerDocument.activeElement; const next = target instanceof HTMLElement ? colors.find(c => c.value === target.dataset.haColor && !c.disabled) : undefined; if (next) onChange({ ...value, color: next.value }); } }}>{colors.map((item, index) => <button key={item.value} type="button" role="radio" aria-label={item.label} title={item.label} aria-checked={value.color === item.value} data-ha-color={item.value} disabled={item.disabled} className="ha-swatch" style={{ backgroundColor: item.color }} tabIndex={value.color === item.value || (!colors.some(c => c.value === value.color) && index === colors.findIndex(c => !c.disabled)) ? 0 : -1} onClick={() => onChange({ ...value, color: item.value })} />)}</div>
      <div className="ha-icon-viewport"><div className="ha-icon-grid" role="group" aria-label={label} onKeyDown={event => gridKey(event, 8)}>{shown.map((option, index) => <button key={option.value} type="button" className="ha-icon-cell" disabled={option.disabled} aria-label={option.label} title={option.label} aria-pressed={value.icon === option.value} tabIndex={index === (shown[focus] && !shown[focus].disabled ? focus : shown.findIndex(o => !o.disabled)) ? 0 : -1} style={{ color: color?.color }} onFocus={() => setFocus(index)} onClick={() => { onChange({ ...value, icon: option.value }); setOpen(false); trigger.current?.focus(); }}>{option.icon}</button>)}</div>{!shown.length && <p className="ha-picker-empty" role="status">{emptyLabel}</p>}</div></div>}
  </div>;
}
export type SymbolChoice = Readonly<{ id: string; label: string; symbol: React.ReactNode; category: string; keywords?: readonly string[]; disabled?: boolean }>;
export type SymbolCategory = Readonly<{ id: string; label: string }>;
export type SymbolPickerProps = { label: string; searchLabel: string; emptyLabel: string; allLabel: string; options: readonly SymbolChoice[]; categories: readonly SymbolCategory[]; value: string | null; onChange: (id: string) => void; disabled?: boolean; className?: string };
/** Caller-supplied data only. There are no embedded symbol lists or tone variants. */
export function SymbolPicker({ label, searchLabel, emptyLabel, allLabel, options, categories, value, onChange, disabled, className }: SymbolPickerProps) {
  const [open, setOpen] = React.useState(false), [query, setQuery] = React.useState(""), [category, setCategory] = React.useState<string | null>(null), [focus, setFocus] = React.useState(0);
  const root = React.useRef<HTMLDivElement>(null), trigger = React.useRef<HTMLButtonElement>(null), id = React.useId();
  usePopup(open && !disabled, root, trigger, () => setOpen(false)); React.useEffect(() => { if (disabled) setOpen(false); }, [disabled]);
  const shown = options.filter(option => (category === null || category === option.category) && `${option.label} ${option.keywords?.join(" ") ?? ""}`.toLocaleLowerCase().includes(query.toLocaleLowerCase()));
  const allCategories = [{ id: "", label: allLabel }, ...categories];
  return <div ref={root} className={join("ha-picker-root", className)}><button ref={trigger} type="button" className="ha-picker-trigger" disabled={disabled} aria-label={label} aria-haspopup="dialog" aria-expanded={open && !disabled} aria-controls={open ? id : undefined} onClick={() => { setQuery(""); setFocus(0); setOpen(!open); }}>{options.find(option => option.id === value)?.symbol ?? label}</button>
    {open && !disabled && <div id={id} role="dialog" aria-label={label} className="ha-popup ha-symbol-popup"><div className="ha-picker-search"><input className="ha-input" type="search" aria-label={searchLabel} placeholder={searchLabel} value={query} onChange={event => { setQuery(event.target.value); setFocus(0); }} /></div>
      <div id={`${id}-results`} role="group" aria-label={label} className="ha-symbol-grid" onKeyDown={event => gridKey(event, 8)}>{shown.map((option, index) => <button key={option.id} type="button" disabled={option.disabled} className="ha-symbol-cell" aria-label={option.label} title={option.label} aria-pressed={value === option.id} tabIndex={index === (shown[focus] && !shown[focus].disabled ? focus : shown.findIndex(o => !o.disabled)) ? 0 : -1} onFocus={() => setFocus(index)} onClick={() => { onChange(option.id); setOpen(false); trigger.current?.focus(); }}>{option.symbol}</button>)}{!shown.length && <p className="ha-picker-empty" role="status">{emptyLabel}</p>}</div>
      <div className="ha-symbol-categories" role="group" aria-label={label} onKeyDown={event => gridKey(event, 1)}>{allCategories.map(item => <button key={item.id} type="button" className="ha-category" aria-pressed={(category ?? "") === item.id} onClick={() => { setCategory(item.id || null); setFocus(0); }}>{item.label}</button>)}</div></div>}
  </div>;
}
export type AlertDialogProps = { open: boolean; onOpenChange: (open: boolean) => void; title: string; description: React.ReactNode; confirmLabel?: string; cancelLabel?: string; errorLabel?: string; busy?: boolean; onConfirm: () => void | Promise<void>; className?: string };
export function AlertDialog({ open, onOpenChange, title, description, confirmLabel = "확인", cancelLabel = "취소", errorLabel = "작업을 완료하지 못했습니다.", busy = false, onConfirm, className }: AlertDialogProps) {
  const dialog = React.useRef<HTMLDialogElement>(null), cancel = React.useRef<HTMLButtonElement>(null), id = React.useId(), task = useAsyncAction();
  const blocked = busy || task.pending; useNativeDialog(open, dialog, cancel);
  React.useEffect(() => { if (open) task.clear(); }, [open]);
  return <dialog ref={dialog} role="alertdialog" className={join("ha-dialog", "ha-alert", className)} aria-labelledby={`${id}-title`} aria-describedby={`${id}-description`} aria-busy={blocked} onCancel={event => { event.preventDefault(); if (!blocked) onOpenChange(false); }} onClose={() => { if (open && !blocked) onOpenChange(false); }}>
    <div className="ha-alert-header"><h2 id={`${id}-title`} className="ha-dialog-title">{title}</h2><div id={`${id}-description`} className="ha-dialog-description">{description}</div></div>
    {task.failed && <p role="alert" className="ha-error">{errorLabel}</p>}<div className="ha-dialog-actions"><button ref={cancel} type="button" className="ha-button ha-button-outline" disabled={blocked} onClick={() => onOpenChange(false)}>{cancelLabel}</button><button type="button" className="ha-button ha-button-destructive" disabled={blocked} onClick={() => { if (!blocked) void task.run(onConfirm, () => onOpenChange(false)); }}>{confirmLabel}</button></div></dialog>;
}
export type StatusDraft = Readonly<{ text: string; preset: string | null; expiry: string }>;
export type StatusPreset = Readonly<{ id: string; label: string; symbol?: React.ReactNode; text?: string }>;
export type StatusDialogProps = { open: boolean; onOpenChange: (open: boolean) => void; value: StatusDraft; presets: readonly StatusPreset[]; expiryOptions: readonly { value: string; label: string }[]; onSave: (value: StatusDraft) => void | Promise<void>; onClear?: () => void | Promise<void>; title?: string; textLabel?: string; expiryLabel?: string; saveLabel?: string; cancelLabel?: string; clearLabel?: string; errorLabel?: string; busy?: boolean };
export function StatusDialog({ open, onOpenChange, value, presets, expiryOptions, onSave, onClear, title = "상태 설정", textLabel = "상태", expiryLabel = "지울 시점", saveLabel = "저장", cancelLabel = "취소", clearLabel = "상태 지우기", errorLabel = "상태를 업데이트하지 못했습니다.", busy = false }: StatusDialogProps) {
  const [draft, setDraft] = React.useState(value), current = useLatest(value), dialog = React.useRef<HTMLDialogElement>(null), cancel = React.useRef<HTMLButtonElement>(null), id = React.useId(), task = useAsyncAction();
  const blocked = busy || task.pending; useNativeDialog(open, dialog, cancel);
  useLayout(() => { if (open) { setDraft(current.current); task.clear(); } }, [open, current]);
  return <dialog ref={dialog} className="ha-dialog ha-status" aria-labelledby={`${id}-title`} aria-busy={blocked} onCancel={event => { event.preventDefault(); if (!blocked) onOpenChange(false); }} onClose={() => { if (open && !blocked) onOpenChange(false); }}>
    <form onSubmit={event => { event.preventDefault(); if (!blocked) void task.run(() => onSave(draft), () => onOpenChange(false)); }}>
      <header className="ha-status-header"><h2 id={`${id}-title`} className="ha-dialog-title">{title}</h2></header><div className="ha-status-body">
        <label className="ha-field-label" htmlFor={`${id}-text`}>{textLabel}</label><input id={`${id}-text`} className="ha-input" value={draft.text} disabled={blocked} onChange={event => setDraft({ ...draft, text: event.target.value })} />
        <div className="ha-status-presets" role="group" aria-label={textLabel}>{presets.map(preset => <button type="button" key={preset.id} className="ha-status-preset" disabled={blocked} aria-pressed={draft.preset === preset.id} onClick={() => setDraft({ ...draft, preset: preset.id, text: preset.text ?? draft.text })}>{preset.symbol && <span aria-hidden="true">{preset.symbol}</span>}{preset.label}</button>)}</div>
        <label className="ha-field-label" htmlFor={`${id}-expiry`}>{expiryLabel}</label><select id={`${id}-expiry`} className="ha-input" value={draft.expiry} disabled={blocked} onChange={event => setDraft({ ...draft, expiry: event.target.value })}>{expiryOptions.map(option => <option key={option.value} value={option.value}>{option.label}</option>)}</select>
        {task.failed && <p className="ha-error" role="alert">{errorLabel}</p>}</div><footer className="ha-status-footer">{onClear && <button type="button" className="ha-button ha-button-ghost" disabled={blocked} onClick={() => { if (!blocked) void task.run(onClear, () => onOpenChange(false)); }}>{clearLabel}</button>}<span className="ha-spacer" /><button ref={cancel} type="button" className="ha-button ha-button-outline" disabled={blocked} onClick={() => onOpenChange(false)}>{cancelLabel}</button><button type="submit" className="ha-button ha-button-primary" disabled={blocked}>{saveLabel}</button></footer>
    </form></dialog>;
}
export type ToastItem = Readonly<{ id: string; announcement: string; title?: React.ReactNode; description?: React.ReactNode; duration?: number | null; action?: Readonly<{ label: string; onClick: () => void; dismissOnAction?: boolean }> }>;
export type ToastProps = { item: ToastItem; onDismiss: (id: string) => void; dismissLabel?: string; className?: string };
export function Toast({ item, onDismiss, dismissLabel = "닫기", className }: ToastProps) {
  const [hover, setHover] = React.useState(false), [focus, setFocus] = React.useState(false), [hidden, setHidden] = React.useState(false);
  const duration = item.duration === undefined ? 5000 : item.duration, remaining = React.useRef(duration ?? 0), dismiss = useLatest(onDismiss);
  React.useEffect(() => { remaining.current = duration ?? 0; }, [item.id, duration]);
  React.useEffect(() => { const update = () => setHidden(document.hidden); update(); document.addEventListener("visibilitychange", update); return () => document.removeEventListener("visibilitychange", update); }, []);
  React.useEffect(() => {
    if (duration === null || duration <= 0 || hover || focus || hidden) return;
    const start = Date.now(), timer = setTimeout(() => dismiss.current(item.id), Math.max(0, remaining.current));
    return () => { clearTimeout(timer); remaining.current = Math.max(0, remaining.current - (Date.now() - start)); };
  }, [item.id, duration, hover, focus, hidden, dismiss]);
  return <div role="group" aria-label={item.announcement} className={join("ha-toast", className)} onPointerEnter={() => setHover(true)} onPointerLeave={() => setHover(false)} onFocusCapture={() => setFocus(true)} onBlurCapture={event => { if (!event.currentTarget.contains(event.relatedTarget)) setFocus(false); }}>
    <div className="ha-toast-copy">{item.title && <p className="ha-toast-title">{item.title}</p>}{item.description && <div className="ha-toast-description">{item.description}</div>}</div>
    <div className="ha-toast-actions">{item.action && <button type="button" className="ha-button ha-button-primary ha-button-small" onClick={() => { item.action?.onClick(); if (item.action?.dismissOnAction !== false) onDismiss(item.id); }}>{item.action.label}</button>}<button type="button" className="ha-button ha-button-secondary ha-button-small" onClick={() => onDismiss(item.id)}>{dismissLabel}</button></div></div>;
}
export type ToasterProps = { items: readonly ToastItem[]; onDismiss: (id: string) => void; label?: string; dismissLabel?: string; className?: string };
export function Toaster({ items, onDismiss, label = "알림", dismissLabel, className }: ToasterProps) {
  const seen = React.useRef(new Set<string>()), [announcement, setAnnouncement] = React.useState("");
  React.useEffect(() => { const added = items.filter(item => !seen.current.has(item.id)); seen.current = new Set(items.map(item => item.id)); if (added.length) setAnnouncement(added.map(item => item.announcement).join(". ")); }, [items]);
  return <><div role="status" aria-live="polite" aria-atomic="true" className="ha-sr-only">{announcement}</div><ol className={join("ha-toaster", className)} aria-label={label}>{items.map(item => <li key={item.id}><Toast item={item} onDismiss={onDismiss} dismissLabel={dismissLabel} /></li>)}</ol></>;
}
export type FileDropzoneProps = { label: string; description?: React.ReactNode; chooseLabel?: string; accept?: string; multiple?: boolean; disabled?: boolean; onFiles: (files: readonly File[]) => void; className?: string };
export function FileDropzone({ label, description, chooseLabel = "파일 선택", accept, multiple = false, disabled = false, onFiles, className }: FileDropzoneProps) {
  const input = React.useRef<HTMLInputElement>(null), depth = React.useRef(0), [dragging, setDragging] = React.useState(false), id = React.useId();
  const isFiles = (event: React.DragEvent) => Array.from(event.dataTransfer.types).includes("Files");
  const deliver = (files: FileList | readonly File[]) => { if (!disabled) { const list = Array.from(files); if (list.length) onFiles(multiple ? list : list.slice(0, 1)); } };
  React.useEffect(() => { if (disabled) { depth.current = 0; setDragging(false); } }, [disabled]);
  return <div className={join("ha-file-dropzone", className)} role="group" aria-labelledby={`${id}-label`} aria-describedby={description ? `${id}-description` : undefined} aria-disabled={disabled || undefined} data-ha-dragging={dragging || undefined}
    onDragEnter={event => { if (isFiles(event)) { event.preventDefault(); if (!disabled) { depth.current++; setDragging(true); } } }} onDragOver={event => { if (isFiles(event)) { event.preventDefault(); event.dataTransfer.dropEffect = disabled ? "none" : "copy"; } }} onDragLeave={event => { if (isFiles(event)) { event.preventDefault(); depth.current = Math.max(0, depth.current - 1); if (!depth.current) setDragging(false); } }} onDrop={event => { if (isFiles(event)) { event.preventDefault(); depth.current = 0; setDragging(false); deliver(event.dataTransfer.files); } }}>
    <div id={`${id}-label`} className="ha-file-label">{label}</div>{description && <div id={`${id}-description`} className="ha-file-description">{description}</div>}
    <input ref={input} type="file" hidden accept={accept} multiple={multiple} disabled={disabled} aria-label={label} onChange={event => { if (event.currentTarget.files) deliver(event.currentTarget.files); event.currentTarget.value = ""; }} /><button type="button" className="ha-button ha-button-outline" disabled={disabled} onClick={() => input.current?.click()}>{chooseLabel}</button></div>;
}
export type DisclosureProps = { label: React.ReactNode; children: React.ReactNode; open?: boolean; defaultOpen?: boolean; onOpenChange?: (open: boolean) => void; disabled?: boolean; className?: string };
export function Disclosure({ label, children, open, defaultOpen = false, onOpenChange, disabled, className }: DisclosureProps) {
  const [expanded, set] = useValue(open, defaultOpen, onOpenChange), id = React.useId();
  return <div className={join("ha-disclosure", className)}><button type="button" className="ha-disclosure-trigger" aria-expanded={expanded} aria-controls={id} disabled={disabled} onClick={() => set(!expanded)}><Arrow down={expanded} />{label}</button><div id={id} hidden={!expanded} className="ha-disclosure-panel">{children}</div></div>;
}
