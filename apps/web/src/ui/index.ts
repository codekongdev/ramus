/**
 * UI adapter layer. Feature code imports ONLY from `src/ui`, never from
 * `@ramus/design-system` directly. Kit components are re-exported under our names here
 * so the kit can be swapped or patched in one place.
 */
export {
  // renamed v2 primitives
  ButtonV2 as Button,
  InputV2 as Input,
  LabelV2 as Label,
  TextareaV2 as Textarea,
  RadioControl as Radio,
  // primitives
  Checkbox, Switch, Avatar, Badge, Select, DropdownMenu, Popover, Tooltip, HoverCard,
  Tabs, ScrollArea, Separator, Skeleton, Spinner,
  // patterns
  UserChip, PrincipalCell, Chip, Toolbar, ToolbarGroup, ToolbarSeparator, Alert, InputOTP,
  MultiSelect, DataGridLite, Table, TableHeader, TableBody, TableFooter, TableRow, TableHead,
  TableCell, TableCaption, EmptyState, Breadcrumbs, ResizablePanels, MessageCard, FileCard,
  SearchCommand,
  // form field (kit "TextField" lives in RamusComponents)
  TextField,
  // advanced
  StructuredCard, OptionRow, OptionGroup, Hint, CardFooter, ActionRow, AlertDialog, Toast,
  Toaster, FileDropzone, Disclosure,
} from '@ramus/design-system';

export type {
  ButtonV2Props as ButtonProps,
  ButtonV2Variant as ButtonVariant,
  ButtonV2Size as ButtonSize,
  CheckboxProps, CheckboxState, SwitchProps, AvatarProps, BadgeVariant, SelectProps,
  SingleSelectOption as SelectOption, MultiSelectOption, DropdownMenuItem, DropdownMenuProps,
  TooltipProps, TabItem, TabsProps, ScrollAreaProps, Principal, UserChipProps,
  PrincipalCellProps, ChipProps, ToolbarProps, AlertProps, InputOTPProps, MultiSelectProps,
  GridColumn, DataGridLiteProps, EmptyStateProps, BreadcrumbItem, ResizablePanelsProps,
  MessageCardProps, FileCardProps, CommandItem, SearchCommandProps, TextFieldProps,
  StructuredCardProps, OptionRowProps, ActionRowProps, ActionItem, AlertDialogProps,
  ToastItem, ToastProps, ToasterProps, FileDropzoneProps, DisclosureProps,
} from '@ramus/design-system';

export { UiProvider } from './UiProvider';
export { Dialog, DialogVisibilityProvider } from './Dialog';
export type { DialogProps } from './Dialog';
export { TaskStatusBadge } from './TaskStatusBadge';
