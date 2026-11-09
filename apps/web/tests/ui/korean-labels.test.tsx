import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import { AlertDialog, MultiSelect, SearchCommand, Spinner, UiProvider } from '../../src/ui';

const render = (node: React.ReactElement) =>
  renderToStaticMarkup(createElement(UiProvider, null, node));

describe('Korean default labels', () => {
  it('SearchCommand uses Korean placeholder, label and empty label', () => {
    const html = render(createElement(SearchCommand, { items: [], onSelect: () => {} }));
    expect(html).toContain('명령 검색');
    expect(html).toContain('placeholder="검색"');
    expect(html).toContain('결과가 없습니다');
    expect(html).not.toContain('No results');
    expect(html).not.toContain('Search commands');
  });

  it('AlertDialog default labels are Korean', () => {
    const html = render(
      createElement(AlertDialog, {
        open: false,
        onOpenChange: () => {},
        title: '삭제',
        description: '정말 삭제할까요?',
        onConfirm: () => {},
      }),
    );
    expect(html).toContain('>확인<');
    expect(html).toContain('>취소<');
    expect(html).not.toContain('Confirm');
    expect(html).not.toContain('Cancel');
  });

  it('MultiSelect and Spinner defaults are Korean', () => {
    const multi = render(
      createElement(MultiSelect, { options: [], value: [], onValueChange: () => {} }),
    );
    expect(multi).toContain('항목 선택');
    expect(multi).toContain('옵션 검색');
    expect(multi).toContain('옵션 열기');
    expect(multi).not.toMatch(/Select items|Search options|Open options/);
    expect(render(createElement(Spinner))).toContain('불러오는 중');
  });
});
