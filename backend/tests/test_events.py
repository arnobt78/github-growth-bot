import asyncio

from app.events import EventBroadcaster


def test_publish_delivers_to_subscriber():
    async def scenario():
        broadcaster = EventBroadcaster()
        queue = broadcaster.subscribe()
        broadcaster.publish("recommendation_dismissed", {"id": 1})
        event = await asyncio.wait_for(queue.get(), timeout=1)
        assert event["type"] == "recommendation_dismissed"
        assert event["payload"] == {"id": 1}

    asyncio.run(scenario())


def test_events_endpoint_requires_api_key(client_without_auth):
    resp = client_without_auth.get("/events")
    assert resp.status_code == 401
