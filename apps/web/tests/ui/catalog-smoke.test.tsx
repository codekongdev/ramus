import { createElement } from 'react';
import { renderToString } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import RamusCatalog from '@ramus/design-system/catalog';
import { UiProvider } from '../../src/ui';

describe('design system catalog', () => {
  it('renders inside UiProvider without throwing', () => {
    const html = renderToString(
      createElement(UiProvider, null, createElement(RamusCatalog)),
    );
    expect(html).toContain('class="ramus');
    expect(html).toContain('data-theme="light"');
    expect(html).toContain('data-contrast="enhanced"');
  });
});
