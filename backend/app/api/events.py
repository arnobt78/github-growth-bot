import json

from fastapi import APIRouter, Depends
from sse_starlette.sse import EventSourceResponse

from app.deps import require_api_key, require_user
from app.events import broadcaster
from app.models import User

router = APIRouter(tags=["events"], dependencies=[Depends(require_api_key)])


@router.get("/events")
async def stream_events(current_user: User = Depends(require_user)):
    queue = broadcaster.subscribe(user_id=current_user.id)

    async def event_generator():
        try:
            while True:
                event = await queue.get()
                yield {"event": event["type"], "data": json.dumps(event["payload"])}
        finally:
            broadcaster.unsubscribe(queue)

    return EventSourceResponse(event_generator())
