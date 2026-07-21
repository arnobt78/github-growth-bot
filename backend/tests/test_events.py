import asyncio

from app.events import EventBroadcaster


def test_publish_delivers_to_subscriber():
    async def scenario():
        broadcaster = EventBroadcaster()
        queue = broadcaster.subscribe(user_id=1)
        broadcaster.publish("recommendation_dismissed", {"id": 1}, user_id=1)
        event = await asyncio.wait_for(queue.get(), timeout=1)
        assert event["type"] == "recommendation_dismissed"
        assert event["payload"] == {"id": 1}

    asyncio.run(scenario())


def test_events_endpoint_requires_api_key(client_without_auth):
    resp = client_without_auth.get("/events")
    assert resp.status_code == 401


def test_publish_only_delivers_to_matching_user():
    broadcaster = EventBroadcaster()
    queue_a = broadcaster.subscribe(user_id=1)
    queue_b = broadcaster.subscribe(user_id=2)

    broadcaster.publish("repo_added", {"id": 42}, user_id=1)

    assert queue_a.get_nowait() == {"type": "repo_added", "payload": {"id": 42}}
    assert queue_b.empty()
