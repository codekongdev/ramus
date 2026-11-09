"""Project names must survive the HTTP boundary and PostgreSQL text storage."""

import pytest
from pydantic import ValidationError

from ramus_api.modules.projects.domain.project import validate_project_name
from ramus_api.modules.projects.presentation.dto import CreateProjectRequest


@pytest.mark.parametrize("name", ["", " \t\n", "a" * 101, "bad\x00name", "bad\ud800"])
def test_invalid_project_names_fail_in_the_domain_and_request_schema(name):
    with pytest.raises(ValueError):
        validate_project_name(name)
    with pytest.raises(ValidationError):
        CreateProjectRequest(name=name)


@pytest.mark.parametrize("name", ["a", "한" * 100, "  Ramus project  "])
def test_valid_names_preserve_the_submitted_text(name):
    assert validate_project_name(name) == name
    assert CreateProjectRequest(name=name).name == name
