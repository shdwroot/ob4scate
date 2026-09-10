import pytest
from pydantic import ValidationError

from .main import RouteRequest, _select_model


def test_selects_explicit_and_content_routed_models():
    assert _select_model(RouteRequest(prompt="hello", model="llama3")) == "llama3"
    request = RouteRequest(
        prompt="Review this finance report",
        routing_rules={"contains": {"finance": "finance-model"}},
    )
    assert _select_model(request) == "finance-model"


def test_rejects_unknown_generation_options():
    with pytest.raises(ValidationError, match="Unsupported options"):
        RouteRequest(prompt="hello", options={"unsafe_option": True})
