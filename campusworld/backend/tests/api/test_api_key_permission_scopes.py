import sys
from pathlib import Path

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from app.api.v1.dependencies import APIPrincipal


def test_api_key_scope_blocks_permission_not_in_scope():
    principal = APIPrincipal(
        subject="42",
        auth_type="api_key",
        roles=["admin"],
        permissions=["graph.read", "graph.write"],
        user_attrs={},
        scopes=["graph.read"],
        api_key_kid="kid01",
    )
    assert principal.has_permission("graph.read") is True
    assert principal.has_permission("graph.write") is False


def test_api_key_scope_star_allows_all():
    principal = APIPrincipal(
        subject="42",
        auth_type="api_key",
        roles=[],
        permissions=[],
        user_attrs={},
        scopes=["*"],
        api_key_kid="kid02",
    )
    assert principal.has_permission("ontology.write") is True
