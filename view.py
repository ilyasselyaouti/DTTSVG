"""Endpoint aiohttp interne pour servir les vidéos générées.

Le Chromecast (ou autre lecteur) doit pouvoir récupérer la vidéo sans
authentification : l'URL contient donc un jeton aléatoire qui rend le fichier
impossible à deviner.
"""

from __future__ import annotations

import os
from http import HTTPStatus
from pathlib import Path

from aiohttp import web
from homeassistant.components.http import HomeAssistantView

VIDEO_CONTENT_TYPES = {".mp4": "video/mp4", ".webm": "video/webm", ".m4a": "audio/mp4"}


class DttsvgVideoView(HomeAssistantView):
    """Sert les vidéos générées par DTTSVG."""

    url = "/api/dttsvg/video/{filename}"
    name = "api:dttsvg:video"
    requires_auth = False

    def __init__(self, media_dir: str, token: str) -> None:
        """Initialise la vue avec le dossier média et le jeton d'accès."""
        self._media_dir = media_dir
        self._token = token

    async def get(self, request: web.Request, filename: str) -> web.Response:
        """Répond avec la vidéo demandée si le jeton est valide."""
        if not filename.startswith(f"{self._token}."):
            return web.Response(status=HTTPStatus.NOT_FOUND, text="Not found")

        file_path = Path(self._media_dir) / filename[len(self._token) + 1 :]
        if not file_path.is_file():
            return web.Response(status=HTTPStatus.NOT_FOUND, text="Not found")

        content_type = VIDEO_CONTENT_TYPES.get(file_path.suffix.lower(), "application/octet-stream")
        return web.FileResponse(
            file_path,
            headers={
                "Cache-Control": "no-store",
                "Content-Type": content_type,
            },
        )


def ensure_token(hass) -> str:
    """Génère ou récupère le jeton aléatoire de l'endpoint vidéo."""
    token = hass.data.get("dttsvg_video_token")
    if not token:
        token = os.urandom(16).hex()
        hass.data["dttsvg_video_token"] = token
    return token


__all__ = ["DttsvgVideoView", "ensure_token"]