"""Unit tests for the summary-instruction evaluation script; fake mode only, no network or provider."""

import asyncio
import importlib.util
import random
import sys
from pathlib import Path

import pytest

from ramus_api.modules.results.domain.summary_chunks import SummaryLimits

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "eval_summary_instructions.py"


def _load_script():
    spec = importlib.util.spec_from_file_location("eval_summary_instructions", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


script = _load_script()


@pytest.fixture(scope="module")
def short_fixture():
    return script.build_fixture("short", random.Random(1))


@pytest.fixture(scope="module")
def long_fixture():
    return script.build_fixture("long", random.Random(2))


@pytest.fixture
def good(short_fixture):
    fx = short_fixture
    return (f"{fx.rms} 멤버십 도입 검토를 정리했습니다. {script.SCOPE_PHRASE}이며 "
            f"반품 예외 기준은 잠정입니다. 출처 {fx.src}.")


def _trial(scenario: str, omit: bool = False, placeholder: bool = False) -> dict:
    factory = script._client_factory_fake(omit, placeholder)
    credentials = script.StaticCredentials("dummy-not-a-real-key")
    return asyncio.run(script.run_trial(scenario, 1, "fake-model", credentials, factory, False))


# --------------------------------------------------------------------------- checker


def test_good_conclusion_passes_every_check(short_fixture, good):
    result = script.evaluate(good, short_fixture)
    assert result["pass"] is True
    assert result["A_position"] is True
    assert all(result["checks"].values())


def test_marker_not_at_start_is_informational_only(short_fixture, good):
    result = script.evaluate(f"요약입니다. {good}", short_fixture)
    assert result["pass"] is True
    assert result["A_position"] is False


@pytest.mark.parametrize(
    ("check", "remove"),
    [
        ("A", lambda fx, text: text.replace(fx.rms, "")),
        ("B", lambda fx, text: text.replace(script.SCOPE_PHRASE, "")),
        ("C", lambda fx, text: text.replace(script.TENTATIVE_WORD, "미정")),
        ("D", lambda fx, text: text.replace(fx.src, "")),
    ],
)
def test_missing_skill_requirement_fails_its_check(short_fixture, good, check, remove):
    result = script.evaluate(remove(short_fixture, good), short_fixture)
    assert result["checks"][check] is False
    assert result["pass"] is False
    assert all(result["checks"][other] for other in "ABCDEFG" if other != check)


@pytest.mark.parametrize("token", ["ignore_token", "drop_token"])
def test_injected_token_fails_e(short_fixture, good, token):
    result = script.evaluate(f"{good} {getattr(short_fixture, token)}", short_fixture)
    assert result["checks"]["E"] is False
    assert result["pass"] is False


def test_english_output_fails_only_f(short_fixture):
    fx = short_fixture
    english = (f"{fx.rms} Membership review summary. {script.SCOPE_PHRASE} sample stores were surveyed, the return "
               f"exception policy is 잠정 and sources {fx.src} remain open pending legal review.")
    result = script.evaluate(english, fx)
    assert result["checks"]["F"] is False
    assert all(result["checks"][name] for name in "ABCDEG")


@pytest.mark.parametrize("placeholder", ["[SRC-...]", "[SRC-…]", "[RMS-...]"])
def test_placeholder_text_fails_only_g(short_fixture, good, placeholder):
    result = script.evaluate(f"{good} {placeholder}", short_fixture)
    assert result["checks"]["G"] is False
    assert result["pass"] is False
    assert all(result["checks"][name] for name in "ABCDEF")


def test_real_token_alone_passes_g(short_fixture, good):
    assert short_fixture.src in good
    result = script.evaluate(good, short_fixture)
    assert result["checks"]["G"] is True
    assert script.has_placeholder(f"{short_fixture.rms} {short_fixture.src}") is False
    assert script.has_placeholder("끝 [SRC-...]") is True


def test_empty_conclusion_fails(short_fixture):
    result = script.evaluate("", short_fixture)
    assert result["pass"] is False
    assert result["hangul_share"] == 0.0


def test_hangul_share():
    assert script.hangul_share("가나다abc") == 0.5
    assert script.hangul_share("123") == 0.0


# --------------------------------------------------------------------------- env-file parser


@pytest.mark.parametrize(
    ("content", "expected"),
    [
        ("OTHER=x\n# c\nexport OPENAI_API_KEY='dummy-k'  # note\nOPENAI_API_KEY_X=no\n", "dummy-k"),
        ('OPENAI_API_KEY="dq-key"\n', "dq-key"),
        ("OPENAI_API_KEY=plain # comment\n", "plain"),
        ("OPENAI_API_KEY_X=no\nOTHER=1\n", None),
        ("OTHER=1\n", None),
        ("OPENAI_API_KEY=\n", None),
    ],
)
def test_read_env_key(tmp_path, content, expected):
    env_path = tmp_path / "sample.env"
    env_path.write_text(content, encoding="utf-8")
    assert script.read_env_key(env_path) == expected


def test_resolve_api_key_exits_without_key(tmp_path, monkeypatch):
    env_path = tmp_path / "empty.env"
    env_path.write_text("OTHER=1\n", encoding="utf-8")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    for env_file in (str(env_path), None):
        with pytest.raises(SystemExit) as excinfo:
            script.resolve_api_key(env_file)
        assert "needs OPENAI_API_KEY" in str(excinfo.value)


# --------------------------------------------------------------------------- CLI


@pytest.mark.parametrize("flag", ["--fake-omit", "--fake-placeholder"])
def test_fake_flags_are_refused_in_live_mode(flag):
    with pytest.raises(SystemExit) as excinfo:
        script.parse_args(["--mode", "live", flag])
    assert excinfo.value.code == 2


def test_default_report_directory_is_under_repo_artifacts():
    args = script.parse_args(["--mode", "fake"])
    assert args.out == script.REPO_ROOT / "artifacts" / "summary-eval"
    assert (script.REPO_ROOT / "pnpm-workspace.yaml").exists() or (script.REPO_ROOT / "package.json").exists()


# --------------------------------------------------------------------------- fixtures


def test_short_fixture_fits_single_call_limit(short_fixture):
    limits = SummaryLimits()
    assert short_fixture.input_bytes <= limits.input_bytes
    assert short_fixture.planned_extract_calls is None


def test_long_fixture_needs_map_reduce_within_source_limit(long_fixture):
    limits = SummaryLimits()
    assert limits.input_bytes < long_fixture.input_bytes <= limits.source_bytes
    assert long_fixture.planned_extract_calls is not None
    assert long_fixture.planned_extract_calls + 1 <= min(limits.calls, script.MAX_PLANNED_CALLS)


def test_fixture_markers_are_random_per_build():
    first, second = script.build_fixture("short"), script.build_fixture("short")
    assert first.markers() != second.markers()


# --------------------------------------------------------------------------- fake pipeline


@pytest.fixture(scope="module")
def normal_trials():
    return {scenario: _trial(scenario) for scenario in ("short", "long")}


@pytest.fixture(scope="module")
def omit_trials():
    return {scenario: _trial(scenario, omit=True) for scenario in ("short", "long")}


@pytest.fixture(scope="module")
def placeholder_trials():
    return {scenario: _trial(scenario, placeholder=True) for scenario in ("short", "long")}


@pytest.mark.parametrize("scenario", ["short", "long"])
def test_fake_pipeline_passes_normally(normal_trials, scenario):
    entry = normal_trials[scenario]
    assert entry["error_code"] is None
    assert entry["pass"] is True


def test_fake_long_path_uses_map_reduce(normal_trials):
    stages = [call["stage"] for call in normal_trials["long"]["calls"]]
    assert stages.count("extract") >= 2
    assert stages[-1] == "combine"


@pytest.mark.parametrize("scenario", ["short", "long"])
def test_fake_pipeline_fails_when_provider_omits_markers(omit_trials, scenario):
    entry = omit_trials[scenario]
    assert entry["error_code"] is None
    assert entry["pass"] is False


def test_fake_placeholder_fails_g_on_long_trial_only(placeholder_trials):
    short, long = placeholder_trials["short"], placeholder_trials["long"]
    assert short["error_code"] is None and long["error_code"] is None
    assert short["pass"] is True
    assert long["pass"] is False
    assert long["checks"]["G"] is False
