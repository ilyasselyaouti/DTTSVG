"""Intégration DTTSVG - Text To Speech Video Generator.

Génère une vidéo d'onde sonore à partir de n'importe quel moteur TTS
configuré dans Home Assistant, puis la joue sur un écran (ex: Nest Hub
via cast) grâce à l'entité media_player « écran » exposée.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from pathlib import Path
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import (
    device_registry as dr,
    entity_registry as er,
)

from . import tts_compat, video
from .const import (
    CONF_DAY_VOLUME,
    CONF_LANGUAGE,
    CONF_MUTE_DURING_GENERATION,
    CONF_NIGHT_VOLUME,
    CONF_SCREEN,
    CONF_START_DELAY,
    CONF_TTS_ENGINE,
    CONF_VIDEO_HEIGHT,
    CONF_VIDEO_WIDTH,
    CONF_VOICE,
    CONF_VOLUME_MODE,
    CONF_WAVE_COLOR,
    CONF_WAVE_HEIGHT,
    DEFAULT_MUTE_DURING_GENERATION,
    DOMAIN,
    EVENT_VIDEO_GENERATED,
    MEDIA_DIR,
    SERVICE_SPEAK,
    VOLUME_MODE_DAY_NIGHT,
)
from .media_player import DttsvgScreen
from .view import DttsvgVideoView, ensure_token

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.MEDIA_PLAYER]


async def async_setup(hass: HomeAssistant, config: dict[str, Any]) -> bool:
    """Prépare l'intégration (endpoint vidéo une seule fois)."""
    token = ensure_token(hass)
    media_dir = _resolve_media_dir(hass)
    hass.http.register_view(DttsvgVideoView(str(media_dir), token))
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Configure DTTSVG à partir d'une entrée de configuration."""
    hub = DttsvgHub(hass, entry)
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = hub

    _register_device(hass, entry)

    await _forward_entry_setups(hass, entry, PLATFORMS)

    _register_services(hass, hub)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Décharge DTTSVG."""
    _unregister_services(hass)
    unload_ok = await _unload_platforms(hass, entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unload_ok


async def _forward_entry_setups(
    hass: HomeAssistant, entry: ConfigEntry, platforms: list[Platform]
) -> None:
    """Forward les plateformes (compat < 2023.8)."""
    forward = getattr(hass.config_entries, "async_forward_entry_setups", None)
    if forward is not None:
        await forward(entry, platforms)
        return
    for platform in platforms:
        await hass.config_entries.async_forward_entry_setup(entry, platform)


async def _unload_platforms(
    hass: HomeAssistant, entry: ConfigEntry, platforms: list[Platform]
) -> bool:
    """Décharge les plateformes (compat < 2023.8)."""
    unload = getattr(hass.config_entries, "async_unload_platforms", None)
    if unload is not None:
        return await unload(entry, platforms)
    results = []
    for platform in platforms:
        results.append(await hass.config_entries.async_unload_platform(entry, platform))
    return all(results)


def _resolve_media_dir(hass: HomeAssistant) -> Path:
    """Détermine le dossier de stockage des vidéos (media/ si possible, sinon storage/)."""
    media_path = hass.config.path("media", MEDIA_DIR)
    try:
        Path(media_path).mkdir(parents=True, exist_ok=True)
        return Path(media_path)
    except OSError:
        _LOGGER.warning("Dossier media indisponible, utilisation de storage/")
        storage_path = hass.config.path("storage", MEDIA_DIR)
        Path(storage_path).mkdir(parents=True, exist_ok=True)
        return Path(storage_path)


def _register_device(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Crée l'entrée de l'appareil dans le registre."""
    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, entry.entry_id)},
        manufacturer="DTTSVG",
        name="DTTSVG",
        model="Text To Speech Video Generator",
        sw_version="1.0.0",
    )


def _register_services(hass: HomeAssistant, hub: "DttsvgHub") -> None:
    """Enregistre les services DTTSVG."""

    async def _speak(call: ServiceCall) -> None:
        await hub.async_speak(call.data)

    hass.services.async_register(DOMAIN, SERVICE_SPEAK, _speak)


def _unregister_services(hass: HomeAssistant) -> None:
    hass.services.async_remove(DOMAIN, SERVICE_SPEAK)


class DttsvgHub:
    """Orchestration : TTS → vidéo → cast sur l'écran."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialise le hub."""
        self.hass = hass
        self._entry = entry
        self._media_dir = _resolve_media_dir(hass)
        self._background_path = Path(__file__).parent / "background.png"

    @property
    def options(self) -> dict[str, Any]:
        """Options de l'entrée."""
        return self._entry.options

    async def async_speak(self, data: dict[str, Any]) -> None:
        """Génère la vidéo depuis le texte et la joue sur l'écran."""
        text = (data.get("text") or "").strip()
        if not text:
            raise HomeAssistantError("Le champ 'text' est requis")

        options = self.options
        engine_id = options.get(CONF_TTS_ENGINE)
        if not engine_id:
            raise HomeAssistantError("Aucun moteur TTS configuré")

        target = data.get("target") or options.get(CONF_SCREEN)
        screen_entity = self._get_screen_entity()

        try:
            await self._apply_volume(target, "mute", True, options)
            audio_bytes = await self._generate_audio(text, options)
            path, url = await self._generate_video(audio_bytes, options)
        except (video.VideoGenerationError, ValueError) as err:
            await self._apply_volume(target, "mute", False, options)
            raise HomeAssistantError(str(err)) from err

        await self._apply_volume_mode(target, options)

        try:
            await self._play_video(path, url, screen_entity, target)
            await asyncio.sleep(0.2)
        finally:
            await self._apply_volume(target, "mute", False, options)

        self.hass.bus.async_fire(
            EVENT_VIDEO_GENERATED,
            {"text": text, "url": url, "path": str(path)},
        )

    async def _play_video(
        self,
        path: Path,
        url: str,
        screen_entity: "DttsvgScreen | None",
        target: str | None,
    ) -> None:
        """Lance la vidéo sur l'écran réel (via l'entité virtuelle ou directement)."""
        if screen_entity is not None:
            await screen_entity.async_play_generated_video(str(path), url)
            return
        if not target:
            return
        state = self.hass.states.get(target)
        if state is None or state.state == "unavailable":
            _LOGGER.warning("Écran cible introuvable ou indisponible : %s", target)
            return
        await self.hass.services.async_call(
            "media_player",
            "play_media",
            {
                "entity_id": target,
                "media_content_type": "video/mp4",
                "media_content_id": url,
            },
            blocking=True,
        )
        _LOGGER.info("Vidéo DTTSVG générée et envoyée : %s", url)

    async def _generate_audio(self, text: str, options: dict[str, Any]) -> bytes:
        """Génère l'audio via le moteur TTS sélectionné."""
        engine_id = options[CONF_TTS_ENGINE]
        language = options.get(CONF_LANGUAGE)
        voice = options.get(CONF_VOICE)

        tts_options: dict[str, Any] = {}
        if voice:
            tts_options["voice"] = voice

        engine = tts_compat.async_get_engine(self.hass, engine_id)
        if engine is None:
            raise HomeAssistantError(f"Moteur TTS introuvable : {engine_id}")

        extension, audio_bytes = await tts_compat.async_get_tts_audio(
            self.hass, engine_id, text, language=language, options=tts_options
        )
        if not audio_bytes:
            raise HomeAssistantError("Le moteur TTS n'a retourné aucune donnée audio")
        return audio_bytes

    async def _generate_video(
        self, audio_bytes: bytes, options: dict[str, Any]
    ) -> tuple[Path, str]:
        """Génère le MP4 d'onde sonore dans le dossier média."""
        filename = f"{uuid.uuid4().hex}.mp4"
        path = self._media_dir / filename

        await self.hass.async_add_executor_job(
            video.generate_video,
            audio_bytes,
            str(path),
            str(self._background_path),
            int(options.get(CONF_VIDEO_WIDTH, 1024)),
            int(options.get(CONF_VIDEO_HEIGHT, 600)),
            int(options.get(CONF_WAVE_HEIGHT, 240)),
            options.get(CONF_WAVE_COLOR, "#00ccff"),
            float(options.get(CONF_START_DELAY, 2.0)),
        )

        token = ensure_token(self.hass)
        base_url = (
            self.hass.config.external_url
            or self.hass.config.internal_url
            or f"http://{self.hass.config.api.local_ip}:{self.hass.config.api.port}"
        )
        url = f"{base_url}/api/dttsvg/video/{token}.{filename}"
        return path, url

    def _get_screen_entity(self) -> DttsvgScreen | None:
        """Retourne l'entité écran virtuelle de cette entrée."""
        entity_registry = er.async_get(self.hass)
        entity_id = entity_registry.async_get_entity_id(
            "media_player", DOMAIN, f"{self._entry.entry_id}_screen"
        )
        if not entity_id:
            return None
        media_player_data = self.hass.data.get("media_player", {})
        get_entity = getattr(media_player_data, "get_entity", None)
        if get_entity is not None:
            return get_entity(entity_id)
        entities = getattr(media_player_data, "entities", None) or (
            media_player_data.get("entities", {}) if isinstance(media_player_data, dict) else {}
        )
        if isinstance(entities, dict):
            return entities.get(entity_id)
        for entity in entities:
            if entity.entity_id == entity_id:
                return entity
        return None

    async def _apply_volume(
        self, target: str | None, mode: str, value: bool, options: dict[str, Any]
    ) -> None:
        """Mute / unmute l'écran réel."""
        if not target:
            return
        state = self.hass.states.get(target)
        if state is None or state.state == "unavailable":
            _LOGGER.warning("Écran cible introuvable ou indisponible : %s", target)
            return
        if mode == "mute" and not options.get(
            CONF_MUTE_DURING_GENERATION, DEFAULT_MUTE_DURING_GENERATION
        ):
            return
        await self.hass.services.async_call(
            "media_player",
            "volume_mute",
            {"entity_id": target, "is_volume_muted": value},
            blocking=True,
        )

    async def _apply_volume_mode(self, target: str | None, options: dict[str, Any]) -> None:
        """Applique le volume jour/nuit ou fixe sur l'écran réel."""
        if not target:
            return
        state = self.hass.states.get(target)
        if state is None or state.state == "unavailable":
            return
        mode = options.get(CONF_VOLUME_MODE)
        if mode == VOLUME_MODE_DAY_NIGHT:
            sun_state = self.hass.states.get("sun.sun")
            is_day = sun_state is not None and sun_state.state == "above_horizon"
            volume = options.get(CONF_DAY_VOLUME, 0.5) if is_day else options.get(CONF_NIGHT_VOLUME, 0.2)
        else:
            volume = options.get(CONF_DAY_VOLUME, 0.5)

        await self.hass.services.async_call(
            "media_player",
            "volume_set",
            {"entity_id": target, "volume_level": volume},
            blocking=True,
        )