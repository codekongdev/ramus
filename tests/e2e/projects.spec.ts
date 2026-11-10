import { randomUUID } from 'node:crypto';
import type { Page } from '@playwright/test';
import { test, expect, registerAccount } from './fixtures';

const conversation = (page: Page) => page.locator('[data-slot="conversation"]');
const projectTrigger = (page: Page) => page.getByRole('button', { name: /^프로젝트 전환:/ });
const switcher = (page: Page) => page.getByRole('dialog', { name: '프로젝트 전환', exact: true });
const creation = (page: Page) => page.getByRole('dialog', { name: '새 프로젝트', exact: true });

async function startProject(page: Page, name: string) {
  await projectTrigger(page).click();
  await switcher(page).getByRole('button', { name: '새 프로젝트', exact: true }).click();
  await creation(page).getByLabel('프로젝트 이름', { exact: true }).fill(name);
}

async function selectProject(page: Page, name: string) {
  await projectTrigger(page).click();
  await switcher(page).getByRole('button', { name: `프로젝트 열기: ${name}`, exact: true }).click();
  await expect(switcher(page)).not.toBeVisible();
  await expect(projectTrigger(page)).toHaveAccessibleName(`프로젝트 전환: ${name}`);
}

test('new projects select their own workspace and remain isolated while switching, reloading, and navigating history', async ({ browser, testServer }) => {
  const contexts = await Promise.all(Array.from({ length: 2 }, () => browser.newContext({
    baseURL: testServer.url, viewport: { width: 1440, height: 1000 },
  })));
  try {
    const pages = await Promise.all(contexts.map(context => context.newPage()));
    const [author, teammate] = pages;
    await Promise.all(pages.map(async (page, index) => {
      const email = `a8-${index}-${randomUUID().slice(0, 8)}@example.test`;
      await registerAccount(page, email);
    }));
    const profiles = await Promise.all(pages.map(async page => {
      const response = await page.request.get('/api/me');
      expect(response.ok()).toBe(true);
      return response.json();
    }));
    expect(profiles[0].default_project_id).toBe(profiles[1].default_project_id);
    const initialProjects = await author.request.get('/api/projects');
    expect(initialProjects.ok()).toBe(true);
    const shared = (await initialProjects.json()).items.find((project: { id: string }) => project.id === profiles[0].default_project_id);
    expect(shared.is_shared_sample).toBe(true);

    const name = `A8 작업 공간 ${randomUUID().slice(0, 8)}`;
    const projectPosts: string[] = [];
    author.on('request', request => {
      if (request.method() === 'POST' && new URL(request.url()).pathname === '/api/projects') projectPosts.push(request.url());
    });
    await startProject(author, '취소할 프로젝트');
    await expect(creation(author).getByLabel('프로젝트 이름', { exact: true })).toBeFocused();
    await creation(author).getByRole('button', { name: '취소', exact: true }).click();
    await expect(switcher(author).getByLabel('프로젝트 검색', { exact: true })).toBeFocused();
    await switcher(author).getByRole('button', { name: '닫기', exact: true }).click();
    await expect(projectTrigger(author)).toBeFocused();
    expect(projectPosts).toHaveLength(0);
    await startProject(author, '   ');
    await creation(author).getByRole('button', { name: '만들기', exact: true }).click();
    await expect(creation(author).getByLabel('프로젝트 이름', { exact: true })).toHaveAttribute('aria-invalid', 'true');
    await expect(creation(author)).toContainText('프로젝트 이름을 1~100자로 입력해 주세요.');
    expect(projectPosts).toHaveLength(0);
    await creation(author).getByLabel('프로젝트 이름', { exact: true }).fill(name);
    await expect(creation(author).getByLabel('프로젝트 이름', { exact: true })).toHaveAttribute('aria-invalid', 'false');
    await author.screenshot({ path: 'artifacts/a8-project-create.png', fullPage: true });
    await creation(author).getByRole('button', { name: '만들기', exact: true }).click();
    await expect(creation(author)).not.toBeVisible();
    expect(projectPosts).toHaveLength(1);
    await expect(projectTrigger(author)).toHaveAccessibleName(`프로젝트 전환: ${name}`);
    const projectPath = new URL(author.url()).pathname;
    expect(projectPath).toMatch(/^\/projects\/[^/]+$/);
    const projectId = projectPath.split('/').at(-1)!;
    expect(projectId).not.toBe(shared.id);
    await expect(author.getByLabel('프로젝트 참여자', { exact: true }).first()).toHaveText('참여자 1명');
    const participants = await author.request.get(`/api/projects/${projectId}/participants`);
    expect(participants.ok()).toBe(true);
    expect((await participants.json()).items.map((person: { id: string }) => person.id)).toEqual([profiles[0].account.id]);

    await author.getByRole('button', { name: '새 대화', exact: true }).click();
    const title = '새 프로젝트의 도입 논의';
    await author.getByLabel('대화 제목', { exact: true }).fill(title);
    await author.getByRole('button', { name: '만들기', exact: true }).click();
    await expect(conversation(author).getByRole('heading', { name: title, exact: true })).toBeVisible();
    const conversationPath = new URL(author.url()).pathname;
    expect(conversationPath).toMatch(new RegExp(`^${projectPath}/conversations/[^/]+$`));
    const body = '이 프로젝트에서만 확인하는 논의입니다.';
    await conversation(author).getByLabel('메시지', { exact: true }).fill(body);
    await conversation(author).getByRole('button', { name: '보내기', exact: true }).click();
    await expect(conversation(author).getByRole('log', { name: '대화 메시지' })).toContainText(body);

    await projectTrigger(teammate).click();
    await expect(switcher(teammate).getByRole('button', { name: `프로젝트 열기: ${shared.name}`, exact: true })).toBeVisible();
    await expect(switcher(teammate).getByRole('button', { name: `프로젝트 열기: ${name}`, exact: true })).toHaveCount(0);
    const otherProjects = await teammate.request.get('/api/projects');
    expect(otherProjects.ok()).toBe(true);
    expect((await otherProjects.json()).items.some((project: { id: string }) => project.id === projectId)).toBe(false);
    expect((await teammate.request.get(`/api/projects/${projectId}/participants`)).status()).toBe(404);
    expect((await teammate.request.get(`/api/projects/${projectId}/conversations`)).status()).toBe(404);
    await switcher(teammate).getByRole('button', { name: '닫기', exact: true }).click();

    await author.bringToFront();
    await projectTrigger(author).click();
    await expect(switcher(author).getByRole('button', { name: `프로젝트 열기: ${name}`, exact: true })).toHaveAttribute('aria-current', 'true');
    const search = switcher(author).getByLabel('프로젝트 검색', { exact: true });
    await expect(search).toBeFocused();
    await search.fill(name);
    await expect(switcher(author).getByRole('button', { name: `프로젝트 열기: ${name}`, exact: true })).toBeVisible();
    await expect(switcher(author).getByRole('button', { name: `프로젝트 열기: ${shared.name}`, exact: true })).toHaveCount(0);
    await search.fill(`no-project-${randomUUID()}`);
    await expect(switcher(author).getByRole('status')).toHaveText('검색 결과가 없습니다.');
    await expect(switcher(author).getByRole('button', { name: /^프로젝트 열기:/ })).toHaveCount(0);
    await search.fill('');
    await expect(switcher(author).getByRole('button', { name: `프로젝트 열기: ${shared.name}`, exact: true })).toBeVisible();
    await search.press('Escape');
    await expect(switcher(author)).not.toBeVisible();
    await expect(projectTrigger(author)).toBeFocused();
    await projectTrigger(author).press('Enter');
    await expect(switcher(author).getByLabel('프로젝트 검색', { exact: true })).toBeFocused();
    await expect(switcher(author).getByRole('status')).toHaveCount(0);
    const dialogBounds = await switcher(author).boundingBox();
    expect(dialogBounds!.width).toBeLessThanOrEqual(480);
    for (const projectName of [shared.name, name]) {
      const row = switcher(author).getByRole('button', { name: `프로젝트 열기: ${projectName}`, exact: true });
      const rowBounds = (await row.boundingBox())!;
      const nameBounds = (await row.locator('.projects-option-name').boundingBox())!;
      const metaBounds = (await row.locator('.projects-option-meta').boundingBox())!;
      expect(nameBounds.x - rowBounds.x).toBeLessThanOrEqual(24);
      expect(rowBounds.x + rowBounds.width - metaBounds.x - metaBounds.width).toBeLessThanOrEqual(24);
      expect(nameBounds.x + nameBounds.width).toBeLessThanOrEqual(metaBounds.x);
    }
    await author.screenshot({ path: 'artifacts/a8-project-switcher.png', fullPage: true });
    await switcher(author).getByRole('button', { name: `프로젝트 열기: ${shared.name}`, exact: true }).click();
    await expect(projectTrigger(author)).toHaveAccessibleName(`프로젝트 전환: ${shared.name}`);
    await expect(author.locator('[data-slot="conversation-tree"]').getByRole('button', { name: title, exact: true })).toHaveCount(0);
    await expect(conversation(author)).not.toContainText(body);

    await author.goBack();
    await expect(author).toHaveURL(new URL(conversationPath, testServer.url).href);
    await expect(projectTrigger(author)).toHaveAccessibleName(`프로젝트 전환: ${name}`);
    await expect(conversation(author).getByRole('log', { name: '대화 메시지' })).toContainText(body);
    await author.goForward();
    await expect(projectTrigger(author)).toHaveAccessibleName(`프로젝트 전환: ${shared.name}`);
    await selectProject(author, name);
    await expect(author).toHaveURL(new URL(conversationPath, testServer.url).href);
    await author.reload();
    await expect(projectTrigger(author)).toHaveAccessibleName(`프로젝트 전환: ${name}`);
    await expect(conversation(author).getByRole('heading', { name: title, exact: true })).toBeVisible();
    await expect(conversation(author).getByRole('log', { name: '대화 메시지' })).toContainText(body);
  } finally {
    await Promise.all(contexts.map(context => context.close()));
  }
});

test('retrying after a lost creation response preserves the name and reuses the committed project', async ({ page, testServer }) => {
  const email = `a8-retry-${randomUUID().slice(0, 8)}@example.test`;
  await registerAccount(page, email);
  const name = `A8 응답 복구 ${randomUUID().slice(0, 8)}`;
  const keys: string[] = [];
  let committedProjectId: string | undefined;
  await page.route('**/api/projects', async route => {
    if (route.request().method() !== 'POST') return route.continue();
    keys.push(route.request().headers()['idempotency-key']);
    if (keys.length > 1) return route.continue();
    // The real transaction commits, but the browser never receives its response.
    const response = await route.fetch();
    expect(response.ok()).toBe(true);
    committedProjectId = (await response.json()).id;
    await route.abort('connectionreset');
  });
  await startProject(page, name);
  await creation(page).getByRole('button', { name: '만들기', exact: true }).click();
  await expect(creation(page).getByRole('alert')).toBeVisible();
  await expect(creation(page).getByLabel('프로젝트 이름', { exact: true })).toHaveValue(name);
  expect(keys).toHaveLength(1);
  expect(keys[0]).toBeTruthy();
  expect(committedProjectId).toBeTruthy();

  await creation(page).getByRole('button', { name: '만들기', exact: true }).click();
  await expect(creation(page)).not.toBeVisible();
  await expect(projectTrigger(page)).toHaveAccessibleName(`프로젝트 전환: ${name}`);
  await expect(page).toHaveURL(new URL(`/projects/${committedProjectId}`, testServer.url).href);
  expect(keys).toHaveLength(2);
  expect(keys[1]).toBe(keys[0]);
  const response = await page.request.get('/api/projects');
  expect(response.ok()).toBe(true);
  const matching = (await response.json()).items.filter((project: { name: string }) => project.name === name);
  expect(matching).toHaveLength(1);
  expect(matching[0].id).toBe(committedProjectId);
});
