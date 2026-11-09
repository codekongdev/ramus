import { describe, expect, it } from 'vitest';
import * as ui from '../../src/ui';

const EXPECTED_NAMES = [
  'Button', 'Input', 'Label', 'Textarea', 'Radio',
  'Checkbox', 'Switch', 'Avatar', 'Badge', 'Select', 'DropdownMenu', 'Popover', 'Tooltip',
  'HoverCard', 'Tabs', 'ScrollArea', 'Separator', 'Skeleton', 'Spinner', 'UserChip',
  'PrincipalCell', 'Chip', 'Toolbar', 'ToolbarGroup', 'ToolbarSeparator', 'Alert', 'InputOTP',
  'MultiSelect', 'DataGridLite', 'Table', 'TableHeader', 'TableBody', 'TableFooter', 'TableRow',
  'TableHead', 'TableCell', 'TableCaption', 'EmptyState', 'Breadcrumbs', 'ResizablePanels',
  'MessageCard', 'FileCard', 'SearchCommand', 'TextField', 'StructuredCard', 'OptionRow',
  'OptionGroup', 'Hint', 'CardFooter', 'ActionRow', 'AlertDialog', 'Toast', 'Toaster',
  'FileDropzone', 'Disclosure', 'UiProvider', 'Dialog',
] as const;

describe('src/ui adapter exports', () => {
  it.each(EXPECTED_NAMES)('exports %s', (name) => {
    expect((ui as Record<string, unknown>)[name]).toBeDefined();
  });

  it('has no undefined export', () => {
    const undefinedNames = Object.entries(ui)
      .filter(([, value]) => value === undefined)
      .map(([name]) => name);
    expect(undefinedNames).toEqual([]);
  });

  it('does not leak the v1 onboarding components', () => {
    const exported = ui as Record<string, unknown>;
    for (const name of ['CatalogDialog', 'Demo', 'ButtonV2', 'InputV2', 'LabelV2', 'TextareaV2', 'RadioControl']) {
      expect(exported[name], name).toBeUndefined();
    }
  });

  it('Button is the v2 button (hp-button class)', async () => {
    const { renderToStaticMarkup } = await import('react-dom/server');
    const { createElement } = await import('react');
    const html = renderToStaticMarkup(createElement(ui.Button, null, '확인'));
    expect(html).toContain('hp-button');
  });
});
