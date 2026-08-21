import reflex as rx
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import FileResponse, Response
from starlette.routing import Route

from src import context
from src.constants import (
    APP_TITLE,
    AUDIO_MEDIA_TYPE,
    AUDIO_ROUTE,
    ROUTE_CALL,
    ROUTE_CALLS,
    ROUTE_DASHBOARD,
    ROUTE_LOGIN,
    ROUTE_MANAGER,
    ROUTE_MANAGERS,
    SESSION_COOKIE_NAME,
)
from src.pages.call import call_page
from src.pages.calls import calls_page
from src.pages.dashboard import dashboard_page
from src.pages.login import login_page
from src.pages.manager import manager_page
from src.pages.managers import managers_page

PARAM_AGENT_ID = "agent_id"
PARAM_CALL_ID = "call_id"
NOT_FOUND_STATUS = 404
UNAUTHORIZED_STATUS = 401

async def serve_audio(request: Request) -> Response:
    database = context.database()
    token = request.cookies.get(SESSION_COOKIE_NAME, "")
    if database.session_user(token) is None:
        return Response(status_code=UNAUTHORIZED_STATUS)

    details = database.call_details(int(request.path_params[PARAM_CALL_ID]))
    path = context.audio().locate(details["audio_path"]) if details else None
    if path is None:
        return Response(status_code=NOT_FOUND_STATUS)
    return FileResponse(path, media_type=AUDIO_MEDIA_TYPE)


api = Starlette(
    routes=[Route(f"{AUDIO_ROUTE}/{{{PARAM_CALL_ID}:int}}", serve_audio)]
)

app = rx.App(api_transformer=api)

app.add_page(login_page, route=ROUTE_LOGIN, title=APP_TITLE)
app.add_page(dashboard_page, route=ROUTE_DASHBOARD, title=APP_TITLE)
app.add_page(calls_page, route=ROUTE_CALLS, title=APP_TITLE)
app.add_page(managers_page, route=ROUTE_MANAGERS, title=APP_TITLE)
app.add_page(
    manager_page, route=f"{ROUTE_MANAGER}/[{PARAM_AGENT_ID}]", title=APP_TITLE
)
app.add_page(call_page, route=f"{ROUTE_CALL}/[{PARAM_CALL_ID}]", title=APP_TITLE)
