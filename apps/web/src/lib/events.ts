/**
 * Project SSE events (contracts.md 4장). The single place for event types and boundary
 * validation. Adding or changing an event is a contract change (roadmap 6.3).
 *
 * Events carry identifiers and changed state only; features re-read resources as needed.
 */

export interface ConversationPayload {
  readonly id: string;
  readonly project_id: string;
  readonly parent_id: string | null;
  readonly task_id: string | null;
  readonly title: string;
  readonly path: readonly string[];
  readonly created_by: string;
  readonly created_at: string;
}

export type RunPurpose = 'work' | 'summary';
export type RunStatus = 'pending' | 'running' | 'succeeded' | 'failed' | 'cancelled';
export type TaskStatus = 'pending' | 'running' | 'ready' | 'failed' | 'cancelled';
export type ResultDraftStatus = 'generating' | 'ready' | 'failed';

interface EventDataMap {
  'member.joined': {
    readonly project_id: string;
    readonly account: { readonly id: string; readonly display_name: string };
  };
  'conversation.created': {
    readonly project_id: string;
    readonly conversation: ConversationPayload;
  };
  'message.created': {
    readonly conversation_id: string;
    readonly message_id: string;
    readonly seq: number;
  };
  'run.updated': {
    readonly conversation_id: string;
    readonly run: {
      readonly id: string;
      readonly purpose: RunPurpose;
      readonly status: RunStatus;
      readonly task_id: string | null;
      readonly requested_by: string;
    };
  };
  'task.updated': {
    readonly source_conversation_id: string;
    readonly task: {
      readonly id: string;
      readonly title: string;
      readonly status: TaskStatus;
      readonly child_conversation_id: string;
      readonly result_id: string | null;
    };
  };
  'resource.updated': {
    readonly project_id: string;
    readonly resource_id: string;
    readonly latest_revision_id: string;
    readonly latest_number: number;
  };
  'conversation_resources.updated': { readonly conversation_id: string };
  'result.updated': {
    readonly result_id: string;
    readonly task_id: string;
    readonly draft_status: ResultDraftStatus | null;
    readonly latest_version: number | null;
  };
  'conversation_inputs.updated': { readonly conversation_id: string };
}

export type ProjectEventType = keyof EventDataMap;

export type ProjectEventData<T extends ProjectEventType> = EventDataMap[T] & {
  readonly occurred_at: string;
};

export type ProjectEvent = {
  [T in ProjectEventType]: { readonly type: T; readonly data: ProjectEventData<T> };
}[ProjectEventType];

export type ProjectEventOf<T extends ProjectEventType> = Extract<ProjectEvent, { type: T }>;

// --- boundary validation -------------------------------------------------------------

export class EventDecodeError extends Error {
  constructor(
    readonly eventType: string,
    readonly path: string,
    reason: string,
  ) {
    super(`${eventType}: ${path} ${reason}`);
    this.name = 'EventDecodeError';
  }
}

type Reader = {
  readonly type: string;
  record(value: unknown, path: string): Record<string, unknown>;
  string(value: unknown, path: string): string;
  nullableString(value: unknown, path: string): string | null;
  integer(value: unknown, path: string): number;
  nullableInteger(value: unknown, path: string): number | null;
  oneOf<V extends string>(value: unknown, path: string, allowed: readonly V[]): V;
  nullableOneOf<V extends string>(value: unknown, path: string, allowed: readonly V[]): V | null;
  stringArray(value: unknown, path: string): string[];
};

function reader(type: string): Reader {
  const fail = (path: string, reason: string): never => {
    throw new EventDecodeError(type, path, reason);
  };
  const self: Reader = {
    type,
    record(value, path) {
      if (typeof value !== 'object' || value === null || Array.isArray(value)) fail(path, 'must be an object');
      return value as Record<string, unknown>;
    },
    string(value, path) {
      if (typeof value !== 'string') fail(path, 'must be a string');
      return value as string;
    },
    nullableString(value, path) {
      return value === null ? null : self.string(value, path);
    },
    integer(value, path) {
      if (typeof value !== 'number' || !Number.isInteger(value)) fail(path, 'must be an integer');
      return value as number;
    },
    nullableInteger(value, path) {
      return value === null ? null : self.integer(value, path);
    },
    oneOf(value, path, allowed) {
      if (typeof value !== 'string' || !(allowed as readonly string[]).includes(value)) {
        fail(path, `must be one of ${allowed.join(', ')}`);
      }
      return value as (typeof allowed)[number];
    },
    nullableOneOf(value, path, allowed) {
      return value === null ? null : self.oneOf(value, path, allowed);
    },
    stringArray(value, path) {
      if (!Array.isArray(value)) fail(path, 'must be an array');
      return (value as unknown[]).map((item, index) => self.string(item, `${path}[${index}]`));
    },
  };
  return self;
}

const RUN_PURPOSES = ['work', 'summary'] as const;
const RUN_STATUSES = ['pending', 'running', 'succeeded', 'failed', 'cancelled'] as const;
const TASK_STATUSES = ['pending', 'running', 'ready', 'failed', 'cancelled'] as const;
const DRAFT_STATUSES = ['generating', 'ready', 'failed'] as const;

type Decoders = {
  [T in ProjectEventType]: (r: Reader, data: Record<string, unknown>) => EventDataMap[T];
};

const decoders: Decoders = {
  'member.joined': (r, d) => {
    const account = r.record(d.account, 'account');
    return {
      project_id: r.string(d.project_id, 'project_id'),
      account: {
        id: r.string(account.id, 'account.id'),
        display_name: r.string(account.display_name, 'account.display_name'),
      },
    };
  },
  'conversation.created': (r, d) => {
    const c = r.record(d.conversation, 'conversation');
    return {
      project_id: r.string(d.project_id, 'project_id'),
      conversation: {
        id: r.string(c.id, 'conversation.id'),
        project_id: r.string(c.project_id, 'conversation.project_id'),
        parent_id: r.nullableString(c.parent_id, 'conversation.parent_id'),
        task_id: r.nullableString(c.task_id, 'conversation.task_id'),
        title: r.string(c.title, 'conversation.title'),
        path: r.stringArray(c.path, 'conversation.path'),
        created_by: r.string(c.created_by, 'conversation.created_by'),
        created_at: r.string(c.created_at, 'conversation.created_at'),
      },
    };
  },
  'message.created': (r, d) => ({
    conversation_id: r.string(d.conversation_id, 'conversation_id'),
    message_id: r.string(d.message_id, 'message_id'),
    seq: r.integer(d.seq, 'seq'),
  }),
  'run.updated': (r, d) => {
    const run = r.record(d.run, 'run');
    return {
      conversation_id: r.string(d.conversation_id, 'conversation_id'),
      run: {
        id: r.string(run.id, 'run.id'),
        purpose: r.oneOf(run.purpose, 'run.purpose', RUN_PURPOSES),
        status: r.oneOf(run.status, 'run.status', RUN_STATUSES),
        task_id: r.nullableString(run.task_id, 'run.task_id'),
        requested_by: r.string(run.requested_by, 'run.requested_by'),
      },
    };
  },
  'task.updated': (r, d) => {
    const task = r.record(d.task, 'task');
    return {
      source_conversation_id: r.string(d.source_conversation_id, 'source_conversation_id'),
      task: {
        id: r.string(task.id, 'task.id'),
        title: r.string(task.title, 'task.title'),
        status: r.oneOf(task.status, 'task.status', TASK_STATUSES),
        child_conversation_id: r.string(task.child_conversation_id, 'task.child_conversation_id'),
        result_id: r.nullableString(task.result_id, 'task.result_id'),
      },
    };
  },
  'resource.updated': (r, d) => ({
    project_id: r.string(d.project_id, 'project_id'),
    resource_id: r.string(d.resource_id, 'resource_id'),
    latest_revision_id: r.string(d.latest_revision_id, 'latest_revision_id'),
    latest_number: r.integer(d.latest_number, 'latest_number'),
  }),
  'conversation_resources.updated': (r, d) => ({
    conversation_id: r.string(d.conversation_id, 'conversation_id'),
  }),
  'result.updated': (r, d) => ({
    result_id: r.string(d.result_id, 'result_id'),
    task_id: r.string(d.task_id, 'task_id'),
    draft_status: r.nullableOneOf(d.draft_status, 'draft_status', DRAFT_STATUSES),
    latest_version: r.nullableInteger(d.latest_version, 'latest_version'),
  }),
  'conversation_inputs.updated': (r, d) => ({
    conversation_id: r.string(d.conversation_id, 'conversation_id'),
  }),
};

export const PROJECT_EVENT_TYPES = Object.keys(decoders) as readonly ProjectEventType[];

const isProjectEventType = (type: string): type is ProjectEventType =>
  Object.prototype.hasOwnProperty.call(decoders, type);

/**
 * Parses and validates one SSE message. Unknown fields are dropped; a missing or mistyped
 * field throws `EventDecodeError`. Plugs into `connectProjectEvents({ decode })`.
 */
export function decodeProjectEvent(type: string, raw: string): ProjectEvent {
  if (!isProjectEventType(type)) throw new EventDecodeError(type, '(type)', 'is not a known event');
  let parsed: unknown;
  try {
    parsed = JSON.parse(raw);
  } catch {
    throw new EventDecodeError(type, '(data)', 'is not valid JSON');
  }
  const r = reader(type);
  const data = r.record(parsed, '(data)');
  const decode = decoders[type] as (r: Reader, d: Record<string, unknown>) => object;
  return {
    type,
    data: { ...decode(r, data), occurred_at: r.string(data.occurred_at, 'occurred_at') },
  } as ProjectEvent;
}
