import uuid
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def test_route_to_singularity_when_no_world_state():
    from app.ssh.entry_router import EntryRouter

    user_node = type("UserNode", (), {})()
    user_node.id = 1
    user_node.attributes = {}

    decision = EntryRouter().resolve_post_auth_destination(user_node)

    assert decision.target_kind == "singularity"
    assert decision.world_name is None


def test_route_to_world_with_resume_location():
    from app.ssh.entry_router import EntryRouter

    router = EntryRouter()
    router._is_world_available = lambda _name: True

    user_node = type("UserNode", (), {})()
    user_node.id = uuid.uuid4()
    user_node.attributes = {
        "active_world": "campus_life",
        "last_world_location": "library",
    }

    decision = router.resolve_post_auth_destination(user_node)

    assert decision.target_kind == "world"
    assert decision.world_name == "campus_life"
    assert decision.world_spawn_key == "library"
