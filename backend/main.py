import re
import sys

import alembic.config
import uvicorn
from config import (
    DEV_HOST,
    DEV_PORT,
    ENABLE_RESCAN_ON_FILESYSTEM_CHANGE,
    ENABLE_SCHEDULED_RESCAN,
    ENABLE_SCHEDULED_UPDATE_MAME_XML,
    ENABLE_SCHEDULED_UPDATE_SWITCH_TITLEDB,
    RESCAN_ON_FILESYSTEM_CHANGE_DELAY,
    ROMM_AUTH_ENABLED,
    ROMM_AUTH_SECRET_KEY,
    SCHEDULED_RESCAN_CRON,
    SCHEDULED_UPDATE_MAME_XML_CRON,
    SCHEDULED_UPDATE_SWITCH_TITLEDB_CRON,
)
from config.config_loader import ConfigDict, config
from endpoints import (
    assets,
    identity,
    oauth,
    platform,
    rom,
    scan,  # noqa
    search,
    tasks,
    webrcade,
)
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi_pagination import add_pagination
from handler import dbh
from starlette.middleware.authentication import AuthenticationMiddleware
from starlette.middleware.sessions import SessionMiddleware
from typing_extensions import TypedDict
from utils import check_new_version, get_version
from utils.auth import (
    CustomCSRFMiddleware,
    HybridAuthBackend,
    create_default_admin_user,
)
from utils.socket import socket_app

app = FastAPI(title="RomM API", version=get_version())

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if ROMM_AUTH_ENABLED and "pytest" not in sys.modules:
    # CSRF protection (except endpoints listed in exempt_urls)
    app.add_middleware(
        CustomCSRFMiddleware,
        secret=ROMM_AUTH_SECRET_KEY,
        exempt_urls=[re.compile(r"^/token.*"), re.compile(r"^/ws")],
    )

# Handles both basic and oauth authentication
app.add_middleware(
    AuthenticationMiddleware,
    backend=HybridAuthBackend(),
)

# Enables support for sessions on requests
app.add_middleware(
    SessionMiddleware,
    secret_key=ROMM_AUTH_SECRET_KEY,
    same_site="strict",
    https_only=False,
)

app.include_router(oauth.router)
app.include_router(identity.router)
app.include_router(platform.router)
app.include_router(rom.router)
app.include_router(search.router)
app.include_router(assets.router)
app.include_router(tasks.router)
app.include_router(webrcade.router)

add_pagination(app)
app.mount("/ws", socket_app)


class WatcherDict(TypedDict):
    ENABLED: bool
    TITLE: str
    MESSAGE: str


class TaskDict(WatcherDict):
    CRON: str


class SchedulerDict(TypedDict):
    RESCAN: TaskDict
    SWITCH_TITLEDB: TaskDict
    MAME_XML: TaskDict


class HeartbeatReturn(TypedDict):
    VERSION: str
    NEW_VERSION: str
    ROMM_AUTH_ENABLED: bool
    WATCHER: WatcherDict
    SCHEDULER: SchedulerDict
    CONFIG: ConfigDict


@app.get("/heartbeat")
def heartbeat() -> HeartbeatReturn:
    """Endpoint to set the CSFR token in cache and return all the basic RomM config

    Returns:
        HeartbeatReturn: TypedDict structure with all the defined values in the HeartbeatReturn class.
    """

    return {
        "VERSION": get_version(),
        "NEW_VERSION": check_new_version(),
        "ROMM_AUTH_ENABLED": ROMM_AUTH_ENABLED,
        "WATCHER": {
            "ENABLED": ENABLE_RESCAN_ON_FILESYSTEM_CHANGE,
            "TITLE": "Rescan on filesystem change",
            "MESSAGE": f"Runs a scan when a change is detected in the library path, with a {RESCAN_ON_FILESYSTEM_CHANGE_DELAY} minute delay",
        },
        "SCHEDULER": {
            "RESCAN": {
                "ENABLED": ENABLE_SCHEDULED_RESCAN,
                "CRON": SCHEDULED_RESCAN_CRON,
                "TITLE": "Scheduled rescan",
                "MESSAGE": "Rescans the entire library",
            },
            "SWITCH_TITLEDB": {
                "ENABLED": ENABLE_SCHEDULED_UPDATE_SWITCH_TITLEDB,  # noqa
                "CRON": SCHEDULED_UPDATE_SWITCH_TITLEDB_CRON,
                "TITLE": "Scheduled Switch TitleDB update",
                "MESSAGE": "Updates the Nintedo Switch TitleDB file",
            },
            "MAME_XML": {
                "ENABLED": ENABLE_SCHEDULED_UPDATE_MAME_XML,
                "CRON": SCHEDULED_UPDATE_MAME_XML_CRON,
                "TITLE": "Scheduled MAME XML update",
                "MESSAGE": "Updates the MAME XML file",
            },
        },
        "CONFIG": config.__dict__,
    }


@app.on_event("startup")
def startup() -> None:
    """Event to handle RomM startup logic."""

    # Create default admin user if no admin user exists
    if len(dbh.get_admin_users()) == 0 and "pytest" not in sys.modules:
        create_default_admin_user()


if __name__ == "__main__":
    # Run migrations
    alembic.config.main(argv=["upgrade", "head"])

    # Run application
    uvicorn.run("main:app", host=DEV_HOST, port=DEV_PORT, reload=True)
