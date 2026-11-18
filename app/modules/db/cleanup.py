import logging
from importlib import import_module
from importlib.util import find_spec

from app.config import config
from app.core.modules import resolve_enabled
from app.modules.db.database import standalone_session

logger = logging.getLogger(__name__)


def _jobs() -> dict[str, str]:
    """The ``cleanup`` modules of the enabled modules (e.g. app/modules/auth/cleanup.py)."""
    jobs = {}
    for spec in resolve_enabled(config):
        path = f"{spec.path}.cleanup"
        if spec.path != __package__ and find_spec(path):
            jobs[spec.name] = path
    return jobs


async def run_cleanup() -> dict[str, int]:
    """Run every job; one that fails is logged and does not stop the others."""
    enabled = {spec.name for spec in resolve_enabled(config)}
    removed: dict[str, int] = {}
    async with standalone_session() as session:
        if "settings" in enabled:
            from app.modules.settings.service import load_settings

            await load_settings(session)
        for name, path in _jobs().items():
            try:
                removed[name] = await import_module(path).cleanup(session)
                await session.commit()
            except Exception:
                await session.rollback()
                logger.exception("Cleanup of %s failed", name)
    logger.info("Cleanup removed: %s", removed)
    return removed
