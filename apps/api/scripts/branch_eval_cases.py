"""Pure core of the F-02 auto-branch evaluation: case data, classification and aggregation.

No I/O and no provider access here; the imperative shell lives in ``eval_auto_branch.py``.
"""

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from ramus_api.modules.conversations.domain.views import mentions_ai
from ramus_api.modules.execution.domain.models import ConversationContext, ResourceInput
from ramus_api.modules.seed.domain.content import RESOURCES, SampleResource, sample_id

OUTCOMES = ("pass", "unnecessary_branch", "missing_branch", "scope_mismatch", "held_for_clarify", "error")
NO_TASKS, EXECUTE, SPLIT = "no_tasks", "execute", "split"
SCOPE_ALIASES: Mapping[str, tuple[str, ...]] = {"가입": ("가입",), "혜택": ("혜택",), "해지": ("해지", "탈퇴")}
BENCH_SCOPES = ("가입", "혜택", "해지")
CONTEXTS = ("none", "service-brief")

# --------------------------------------------------------------------------- evaluation set


@dataclass(frozen=True)
class Variant:
    case_id: str
    variant_id: str
    messages: tuple[str, ...]
    expectation: str
    scopes: tuple[str, ...] = ()
    gate: bool = False


CASE_LABELS: Mapping[str, str] = {
    "F02-1": "사람 간 논의", "F02-2": "작업 목록 작성", "F02-3": "사람 간 배정",
    "F02-4": "방법 질문", "F02-5": "조사 실행", "F02-6": "명시 범위 분할",
}


def _v(case: str, vid: str, *messages: str, expect: str = NO_TASKS, scopes: tuple[str, ...] = (),
       gate: bool = False) -> Variant:
    return Variant(case, vid, tuple(messages), expect, scopes, gate)


VARIANTS: tuple[Variant, ...] = (
    _v("F02-1", "g1", "멤버십 도입에 필요한 일을 정해봅시다", gate=True),
    _v("F02-1", "m1", "@AI 멤버십 도입에 필요한 일을 같이 정해봅시다"),
    _v("F02-1", "m2", "멤버십 도입에 필요한 일을 정해봅시다", "좋아요. 저는 가입 쪽부터 생각해볼게요. @AI도 의견 있으면 보태줘"),
    _v("F02-2", "g1", "가입·혜택·해지를 각각 살펴보죠", gate=True),
    _v("F02-2", "m1", "@AI 가입·혜택·해지를 각각 살펴볼 항목으로 목록만 정리해줘"),
    _v("F02-2", "m2", "가입·혜택·해지를 각각 살펴보죠", "@AI 방금 정한 할 일을 목록으로 정리해줘"),
    _v("F02-3", "g1", "지훈님은 배송비 정책을 확인해주세요", gate=True),
    _v("F02-3", "m1", "지훈님은 배송비 정책을, 서연님은 해지 절차를 확인해주세요. @AI 이 배정 내용 기록해둬"),
    _v("F02-3", "m2", "지훈님은 배송비 정책을 확인해주세요", "@AI 지훈님이 배송비 정책을 맡기로 했어요. 참고만 해주세요"),
    _v("F02-4", "m1", "@AI 멤버십을 어떻게 기획하면 좋을까?"),
    _v("F02-4", "m2", "@AI 멤버십 기획은 어떤 순서로 진행하면 좋을까?"),
    _v("F02-4", "m3", "@AI 가입·혜택·해지 벤치마킹은 어떻게 나눠서 하면 좋을까?"),
    _v("F02-5", "m1", "@AI 멤버십 도입을 위해 타사를 조사해줘", expect=EXECUTE),
    _v("F02-5", "m2", "@AI 멤버십 도입 검토용으로 경쟁사 멤버십 사례를 조사해줘", expect=EXECUTE),
    _v("F02-6", "m1", "@AI 가입·혜택·해지로 벤치마킹을 나눠 진행해줘", expect=SPLIT, scopes=BENCH_SCOPES),
    _v("F02-6", "m2", "@AI 경쟁사 멤버십 벤치마킹을 가입, 혜택, 해지 세 범위로 나눠서 진행해줘",
       expect=SPLIT, scopes=BENCH_SCOPES),
    _v("F02-6", "m3", "멤버십 도입에 필요한 일을 정해봅시다", "가입·혜택·해지를 각각 살펴보죠",
       "@AI 그럼 이 세 범위로 벤치마킹을 나눠 진행해줘", expect=SPLIT, scopes=BENCH_SCOPES),
)


def validate_variants(variants: Sequence[Variant]) -> None:
    """Fixture integrity: gate bodies must not mention the AI, model bodies must; ids and bodies unique."""
    seen_ids: set[tuple[str, str]] = set()
    model_bodies: set[str] = set()
    for item in variants:
        key = (item.case_id, item.variant_id)
        if key in seen_ids or item.case_id not in CASE_LABELS or not item.messages:
            raise ValueError(f"invalid or duplicate variant {key}")
        seen_ids.add(key)
        if mentions_ai(item.messages[-1]) == item.gate:
            raise ValueError(f"variant {key} contradicts its gate flag")
        if item.gate and any(mentions_ai(body) for body in item.messages):
            raise ValueError(f"gate variant {key} mentions the AI")
        if (item.expectation == SPLIT) != bool(item.scopes):
            raise ValueError(f"variant {key}: scopes belong to split expectations only")
        if not item.gate:
            if item.messages[-1] in model_bodies:
                raise ValueError(f"variant {key} repeats another request body")
            model_bodies.add(item.messages[-1])


validate_variants(VARIANTS)


def select_variants(case_ids: Sequence[str] | None) -> tuple[tuple[Variant, ...], tuple[Variant, ...]]:
    """Returns (gate variants, model variants) for the chosen cases (all cases when None)."""
    chosen = [item for item in VARIANTS if case_ids is None or item.case_id in case_ids]
    return tuple(i for i in chosen if i.gate), tuple(i for i in chosen if not i.gate)


# --------------------------------------------------------------------------- pure classification


@dataclass(frozen=True)
class TaskView:
    title: str
    goal: str
    start_input: str


@dataclass(frozen=True)
class Observation:
    mode: str | None
    reply: str
    tasks: tuple[TaskView, ...]
    parent_message: str | None = None
    error_code: str | None = None


@dataclass(frozen=True)
class Verdict:
    outcome: str
    matched_scopes: tuple[str, ...] = ()
    missing_scopes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.outcome not in OUTCOMES:
            raise ValueError(f"unknown outcome {self.outcome!r}")


def scopes_in(text: str, scopes: Sequence[str]) -> frozenset[str]:
    return frozenset(s for s in scopes if any(alias in text for alias in SCOPE_ALIASES.get(s, (s,))))


def task_scopes(task: TaskView, scopes: Sequence[str]) -> frozenset[str]:
    """Scopes named by the title; the goal is consulted only when the title names none."""
    return scopes_in(task.title, scopes) or scopes_in(task.goal, scopes)


def _classify_split(variant: Variant, tasks: Sequence[TaskView]) -> Verdict:
    if not tasks:
        return Verdict("missing_branch", (), variant.scopes)
    per_task = [task_scopes(task, variant.scopes) for task in tasks]
    matched = tuple(s for s in variant.scopes if any(s in found for found in per_task))
    missing = tuple(s for s in variant.scopes if s not in matched)
    picked = [next(iter(found)) for found in per_task if len(found) == 1]
    exact = len(picked) == len(per_task) and len(set(picked)) == len(picked) and set(picked) == set(variant.scopes)
    return Verdict("pass" if exact else "scope_mismatch", matched, missing)


def classify(variant: Variant, observation: Observation) -> Verdict:
    if observation.error_code:
        return Verdict("error")
    count = len(observation.tasks)
    if variant.expectation == NO_TASKS:
        return Verdict("unnecessary_branch" if count else "pass")
    if variant.expectation == EXECUTE:
        return Verdict("held_for_clarify" if observation.mode == "clarify" else "pass")
    return _classify_split(variant, observation.tasks)


@dataclass(frozen=True)
class GateResult:
    case_id: str
    variant_id: str
    messages: tuple[str, ...]
    no_run: bool


def evaluate_gate(variant: Variant) -> GateResult:
    """Production creates a run only when the last message mentions the AI; no run means no task."""
    return GateResult(variant.case_id, variant.variant_id, variant.messages, not mentions_ai(variant.messages[-1]))


@dataclass(frozen=True)
class TrialRecord:
    case_id: str
    variant_id: str
    trial: int
    context: str
    messages: tuple[str, ...]
    expectation: str
    scopes: tuple[str, ...]
    mode: str | None
    reply: str
    parent_message: str | None
    tasks: tuple[TaskView, ...]
    task_count: int
    matched_scopes: tuple[str, ...]
    missing_scopes: tuple[str, ...]
    outcome: str
    error_code: str | None
    elapsed_s: float


def make_record(variant: Variant, trial: int, context: str, observation: Observation,
                elapsed_s: float) -> TrialRecord:
    verdict = classify(variant, observation)
    return TrialRecord(
        variant.case_id, variant.variant_id, trial, context, variant.messages, variant.expectation, variant.scopes,
        observation.mode, observation.reply, observation.parent_message, observation.tasks, len(observation.tasks),
        verdict.matched_scopes, verdict.missing_scopes, verdict.outcome, observation.error_code, round(elapsed_s, 2),
    )


@dataclass(frozen=True)
class Stats:
    attempts: int
    outcomes: Mapping[str, int]
    modes: Mapping[str, int]

    @property
    def passes(self) -> int:
        return self.outcomes.get("pass", 0)


def aggregate(records: Sequence[TrialRecord]) -> Stats:
    return Stats(len(records), Counter(r.outcome for r in records), Counter(r.mode for r in records if r.mode))


# --------------------------------------------------------------------------- seeded context


def resource_input(item: SampleResource) -> ResourceInput:
    """Maps a seeded resource the way production pins it: text -> content, skill -> instructions."""
    is_skill = item.kind == "skill"
    return ResourceInput(
        resource_id=sample_id(f"resource:{item.key}"), revision_id=sample_id(f"resource:{item.key}:v1"),
        kind=item.kind, name=item.name,  # type: ignore[arg-type]
        instructions=item.body if is_skill else None, content=None if is_skill else item.body,
    )


def build_context(name: str) -> ConversationContext:
    """``none`` is a new conversation with nothing applied; otherwise the named seeded resource is pinned."""
    if name == "none":
        return ConversationContext()
    if name not in CONTEXTS:
        raise ValueError(f"unknown context {name!r}")
    return ConversationContext(resources=(resource_input(next(r for r in RESOURCES if r.key == name)),))
