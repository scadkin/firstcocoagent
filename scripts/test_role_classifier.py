"""
Unit tests for tools/role_classifier.py.

Uses a small mock Anthropic client so tests don't hit the live API.
Run from repo root:
    .venv/bin/python scripts/test_role_classifier.py
"""
from __future__ import annotations

import sys
import tempfile
import traceback
from pathlib import Path
from types import SimpleNamespace

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

import tools.role_classifier as rc  # noqa: E402


class MockClient:
    """Canned-response Anthropic client. Tracks call count + last title."""

    def __init__(self, answers: dict[str, str]):
        self.answers = answers
        self.calls = 0
        self.last_prompt = ""
        self.messages = self  # mock the .messages.create nesting

    def create(self, *, model: str, max_tokens: int, temperature: float, messages: list) -> object:
        self.calls += 1
        self.last_prompt = messages[0]["content"]
        # Extract the title from the prompt
        title_line = [l for l in self.last_prompt.splitlines() if l.startswith("Job title:")]
        title = title_line[0].replace("Job title:", "").strip() if title_line else ""
        answer = self.answers.get(title.lower(), "other")
        return SimpleNamespace(content=[SimpleNamespace(text=answer)])


def _check(name: str, condition: bool, detail: str = "") -> None:
    if not condition:
        raise AssertionError(f"{name} failed: {detail}")


def _tmp_cache() -> Path:
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".json")
    tmp.close()
    p = Path(tmp.name)
    p.unlink(missing_ok=True)
    return p


def test_admin_buckets() -> None:
    answers = {
        "superintendent": "admin",
        "principal": "admin",
        "assistant principal": "admin",
        "head of school": "admin",
    }
    client = MockClient(answers)
    cache = _tmp_cache()
    for title in answers:
        result = rc.classify_contact_role(
            {"title": title}, client=client, cache_path=cache
        )
        _check(f"admin title {title}", result == "admin", f"got {result}")


def test_teacher_buckets() -> None:
    answers = {
        "cs teacher": "teacher",
        "math teacher": "teacher",
        "algebra teacher": "teacher",
        "robotics teacher": "teacher",
    }
    client = MockClient(answers)
    cache = _tmp_cache()
    for title in answers:
        result = rc.classify_contact_role(
            {"title": title}, client=client, cache_path=cache
        )
        _check(f"teacher title {title}", result == "teacher", f"got {result}")


def test_it_and_curriculum_buckets() -> None:
    answers = {
        "director of technology": "it",
        "cio": "it",
        "edtech coordinator": "it",
        "curriculum director": "curriculum",
        "instructional coach": "curriculum",
        "c&i coordinator": "curriculum",
    }
    client = MockClient(answers)
    cache = _tmp_cache()
    for title, expected in answers.items():
        result = rc.classify_contact_role(
            {"title": title}, client=client, cache_path=cache
        )
        _check(f"{expected} title {title}", result == expected, f"got {result}")


def test_coach_bucket() -> None:
    answers = {
        "robotics coach": "coach",
        "esports coach": "coach",
    }
    client = MockClient(answers)
    cache = _tmp_cache()
    for title in answers:
        result = rc.classify_contact_role(
            {"title": title}, client=client, cache_path=cache
        )
        _check(f"coach title {title}", result == "coach", f"got {result}")


def test_empty_title_returns_other() -> None:
    client = MockClient({})
    cache = _tmp_cache()
    result = rc.classify_contact_role(
        {"title": ""}, client=client, cache_path=cache
    )
    _check("empty title → other", result == "other")
    _check("empty title skipped Claude", client.calls == 0)


def test_it_infra_prefiltered_to_other() -> None:
    # "Network Administrator" hits IT_INFRA_KEYWORDS without education
    # qualifier — is_relevant_role() returns False, classifier short-
    # circuits to "other" without calling Claude.
    client = MockClient({})
    cache = _tmp_cache()
    result = rc.classify_contact_role(
        {"title": "Network Administrator"}, client=client, cache_path=cache
    )
    _check(
        "network admin pre-filtered to other", result == "other", f"got {result}"
    )
    _check("network admin skipped Claude", client.calls == 0)


def test_cache_prevents_second_call() -> None:
    client = MockClient({"curriculum director": "curriculum"})
    cache = _tmp_cache()
    rc.classify_contact_role(
        {"title": "Curriculum Director"}, client=client, cache_path=cache
    )
    _check("first call hit Claude", client.calls == 1)
    rc.classify_contact_role(
        {"title": "Curriculum Director"}, client=client, cache_path=cache
    )
    _check("second call hit cache, not Claude", client.calls == 1)


def test_cache_key_normalizes_whitespace_and_case() -> None:
    client = MockClient({"principal": "admin"})
    cache = _tmp_cache()
    rc.classify_contact_role(
        {"title": "Principal"}, client=client, cache_path=cache
    )
    rc.classify_contact_role(
        {"title": "  PRINCIPAL  "}, client=client, cache_path=cache
    )
    _check("one Claude call despite case/whitespace", client.calls == 1)


def test_unknown_haiku_response_falls_to_other() -> None:
    client = MockClient({"mystery title": "potato"})
    cache = _tmp_cache()
    result = rc.classify_contact_role(
        {"title": "mystery title"}, client=client, cache_path=cache
    )
    _check("unknown response → other", result == "other")


def test_pass_through_mode() -> None:
    original = rc.ROLE_CLASSIFIER_MODE
    rc.ROLE_CLASSIFIER_MODE = "pass_through"
    try:
        client = MockClient({"superintendent": "admin"})
        cache = _tmp_cache()
        result = rc.classify_contact_role(
            {"title": "Superintendent"}, client=client, cache_path=cache
        )
        _check("pass_through → other", result == "other")
        _check("pass_through skipped Claude", client.calls == 0)
    finally:
        rc.ROLE_CLASSIFIER_MODE = original


def test_ambiguous_title_relies_on_haiku_answer() -> None:
    # "Director" alone is ambiguous — rule-based wouldn't know. The
    # classifier trusts Haiku's answer.
    client = MockClient({"director": "admin"})
    cache = _tmp_cache()
    result = rc.classify_contact_role(
        {"title": "Director"}, client=client, cache_path=cache
    )
    _check("ambiguous director → haiku answer", result == "admin")


TESTS = [
    test_admin_buckets,
    test_teacher_buckets,
    test_it_and_curriculum_buckets,
    test_coach_bucket,
    test_empty_title_returns_other,
    test_it_infra_prefiltered_to_other,
    test_cache_prevents_second_call,
    test_cache_key_normalizes_whitespace_and_case,
    test_unknown_haiku_response_falls_to_other,
    test_pass_through_mode,
    test_ambiguous_title_relies_on_haiku_answer,
]


def main() -> int:
    failures: list[str] = []
    for fn in TESTS:
        try:
            fn()
            print(f"ok    {fn.__name__}")
        except Exception as e:
            failures.append(f"{fn.__name__}: {e}")
            print(f"FAIL  {fn.__name__}: {e}")
            traceback.print_exc()

    print()
    print(f"{len(TESTS) - len(failures)}/{len(TESTS)} passed")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
