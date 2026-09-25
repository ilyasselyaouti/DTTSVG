from __future__ import annotations

import logging
from http import HTTPStatus

from aiohttp import web
from homeassistant.components.http import HomeAssistantView

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class DttsvgPhoneView(HomeAssistantView):

    url = "/api/dttsvg/phone/active"
    name = "api:dttsvg:phone:active"
    requires_auth = True

    async def post(self, request: web.Request) -> web.Response:
        try:
            payload = await request.json()
        except Exception:  # noqa: BLE001 - JSON invalide
            return web.Response(status=HTTPStatus.BAD_REQUEST, text="Invalid JSON")

        device_id = payload.get("device_id")
        active = payload.get("active")
        if not isinstance(device_id, str) or not device_id or not isinstance(active, bool):
            return web.Response(
                status=HTTPStatus.BAD_REQUEST,
                text="Fields 'device_id' (str) and 'active' (bool) are required",
            )

        hass = request.app["hass"]
        hubs = hass.data.get(DOMAIN) or {}
        for hub in hubs.values():
            hub.async_update_phone(device_id, active)
        _LOGGER.debug("Heartbeat téléphone %s -> active=%s", device_id, active)
        return web.Response(status=HTTPStatus.OK, text="ok")


__all__ = ["DttsvgPhoneView"]
