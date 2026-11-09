import { parseResourceDetail, ResourceDecodeError } from './contract';
import type { ResourceDetail, ResourceKind } from './model';
import type { ResourceRevision, RevisionAttempt, SavedResourceRevision } from './revisionModel';
import { validateRevisionDraft } from './revisionReducer';

const invalid = (): never => { throw new ResourceDecodeError(); };

function checkRevision(revision: ResourceRevision, resourceId: string, kind: ResourceKind) {
  if (revision.resource_id !== resourceId || !revision.id || !revision.created_by || !Number.isFinite(Date.parse(revision.created_at))) invalid();
  if (kind === 'skill' ? revision.instructions === null || revision.content !== null || revision.file_name !== null
    : revision.content === null || revision.instructions !== null || (kind === 'text' ? revision.file_name !== null : revision.file_name === null)) invalid();
  const problems = validateRevisionDraft({
    kind, baseId: revision.id, baseNumber: revision.number,
    name: revision.name, description: revision.description,
    body: (kind === 'skill' ? revision.instructions : revision.content) ?? '', fileName: revision.file_name ?? '',
  });
  if (Object.keys(problems).length) invalid();
}

/** Check associations as well as the generated DTO's runtime shape before rendering it. */
export function parseRevisionDetail(value: unknown, resourceId: string, revisionId: string | null): ResourceDetail {
  const detail = parseResourceDetail(value);
  if (detail.id !== resourceId || detail.revision.id !== (revisionId ?? detail.latest_revision_id)) invalid();
  checkRevision(detail.revision, resourceId, detail.kind);
  if (!detail.revisions.length || new Set(detail.revisions.map(item => item.id)).size !== detail.revisions.length ||
    new Set(detail.revisions.map(item => item.number)).size !== detail.revisions.length) invalid();
  for (const entry of detail.revisions) {
    if (!entry.id || !entry.created_by || !Number.isFinite(Date.parse(entry.created_at))) invalid();
  }
  const selected = detail.revisions.find(entry => entry.id === detail.revision.id);
  const latest = detail.revisions.find(entry => entry.id === detail.latest_revision_id);
  if (!selected || !latest || latest.number !== Math.max(...detail.revisions.map(entry => entry.number)) ||
    selected.number !== detail.revision.number || selected.name !== detail.revision.name ||
    selected.created_by !== detail.revision.created_by || selected.created_at !== detail.revision.created_at) invalid();
  return detail;
}

export function parseSavedRevision(
  value: unknown, resourceId: string, kind: ResourceKind, baseNumber: number, attempt: RevisionAttempt,
): SavedResourceRevision {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return invalid();
  const raw = value as Record<string, unknown>;
  if (typeof raw.created !== 'boolean') return invalid();
  // Reuse the generated-DTO decoder without maintaining a second copy of ResourceRevision fields.
  const revision = parseResourceDetail({ id: resourceId, kind, latest_revision_id: '', revisions: [], revision: raw.revision }).revision;
  checkRevision(revision, resourceId, kind);
  const { body } = attempt;
  if (revision.number !== baseNumber + (raw.created ? 1 : 0) ||
    (raw.created ? revision.id === body.base_revision_id : revision.id !== body.base_revision_id) ||
    revision.name !== body.name || revision.description !== body.description ||
    revision.instructions !== (body.instructions ?? null) || revision.content !== (body.content ?? null) || revision.file_name !== (body.file_name ?? null)) invalid();
  return { created: raw.created, revision };
}
