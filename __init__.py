"""Intégration DTTSVG - Text To Speech Video Generator.

Génère une vidéo d'onde sonore à partir de n'importe quel moteur TTS
configuré dans Home Assistant, puis la joue sur un écran (ex: Nest Hub
via cast) grâce à l'entité media_player « écran » exposée.

v1.1 :
- Écran/enceinte de backup (fallback si le principal est hors ligne)
- Annonces prioritaires : jouées immédiatement, avec baisse (ducking) du
  volume du média en cours puis restauration automatique
- Annonces non prioritaires : file d'attente jusqu'à ce que l'enceinte soit libre
- Routage vers l'app mobile Android (overlay façon Gemini Live) si le
  téléphone est actif
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import (
    device_registry as dr,
)
from homeassistant.helpers import (
    entity_registry as er,
)
from homeassistant.helpers.event import async_track_state_change_event

from . import tts_compat, video
from .const import (
    CONF_BACKUP_SCREEN,
    CONF_DAY_VOLUME,
    CONF_DUCK_VOLUME,
    CONF_LANGUAGE,
    CONF_MUTE_DURING_GENERATION,
    CONF_NIGHT_VOLUME,
    CONF_PHONE_ROUTING,
    CONF_PRIORITY_DEFAULT,
    CONF_SCREEN,
    CONF_START_DELAY,
    CONF_TTS_ENGINE,
    CONF_VIDEO_HEIGHT,
    CONF_VIDEO_WIDTH,
    CONF_VOICE,
    CONF_VOLUME_MODE,
    CONF_WAVE_COLOR,
    CONF_WAVE_HEIGHT,
    DEFAULT_DUCK_VOLUME,
    DEFAULT_MUTE_DURING_GENERATION,
    DEFAULT_PHONE_ROUTING,
    DEFAULT_PRIORITY_DEFAULT,
    DOMAIN,
    EVENT_PHONE_ANNOUNCEMENT,
    EVENT_VIDEO_GENERATED,
    MAX_QUEUE,
    MEDIA_DIR,
    PHONE_ACTIVE_EXPIRY,
    SERVICE_SPEAK,
    VOLUME_MODE_DAY_NIGHT,
)
from .media_player import DttsvgScreen
from .phone import DttsvgPhoneView
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
    _register_phone_view(hass)

    entry.async_on_unload(entry.add_update_listener(_options_updated))
    hub.async_start()

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Décharge DTTSVG."""
    _unregister_services(hass)
    unload_ok = await _unload_platforms(hass, entry, PLATFORMS)
    if unload_ok:
        hub = hass.data[DOMAIN].pop(entry.entry_id, None)
        if hub is not None:
            hub.async_stop()
    return unload_ok


async def _options_updated(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reconfigure le hub quand les options changent (sans recharger)."""
    hub = hass.data.get(DOMAIN, {}).get(entry.entry_id)
    if hub is not None:
        hub.async_reconfigure()


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
        sw_version="1.1.0",
    )


def _register_services(hass: HomeAssistant, hub: DttsvgHub) -> None:
    """Enregistre les services DTTSVG."""

    async def _speak(call: ServiceCall) -> None:
        await hub.async_speak(call.data)

    hass.services.async_register(DOMAIN, SERVICE_SPEAK, _speak)


def _unregister_services(hass: HomeAssistant) -> None:
    hass.services.async_remove(DOMAIN, SERVICE_SPEAK)


def _register_phone_view(hass: HomeAssistant) -> None:
    """Enregistre l'endpoint heartbeat de l'app mobile (une seule fois)."""
    if hass.data.get("dttsvg_phone_view_registered"):
        return
    hass.data["dttsvg_phone_view_registered"] = True
    hass.http.register_view(DttsvgPhoneView())


class DttsvgHub:
    """Orchestration : TTS → vidéo → téléphone / écran / backup / file d'attente."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialise le hub."""
        self.hass = hass
        self._entry = entry
        self._media_dir = _resolve_media_dir(hass)
        self._background_path = Path(__file__).parent / "background.png"
        self._queue: list[dict[str, Any]] = []
        self._speak_lock = asyncio.Lock()
        #: entity qui joue l'annonce -> {duck, volume} à restaurer quand elle se termine
        self._pending_duck: dict[str, dict[str, Any]] = {}
        #: device_id -> {"active": bool, "last_seen": timestamp}
        self._phones: dict[str, dict[str, Any]] = {}
        self._unsub_track: Callable[[], None] | None = None

    @property
    def options(self) -> dict[str, Any]:
        """Options de l'entrée."""
        return self._entry.options

    # ------------------------------------------------------------------
    # Cycle de vie
    # ------------------------------------------------------------------

    def async_start(self) -> None:
        """Démarre le suivi d'état des écrans (restauration duck + flush file)."""
        entities = self._tracked_entities
        if not entities:
            return
        self._unsub_track = async_track_state_change_event(
            self.hass, entities, self._handle_target_state_change
        )

    def async_reconfigure(self) -> None:
        """Re-enregistre le suivi quand les options changent."""
        if self._unsub_track is not None:
            self._unsub_track()
            self._unsub_track = None
        self.async_start()

    def async_stop(self) -> None:
        """Arrête le suivi, restaure les volumes et vide la file."""
        if self._unsub_track is not None:
            self._unsub_track()
            self._unsub_track = None
        for entity_id in list(self._pending_duck):
            self._restore_duck(entity_id)
        self._queue.clear()

    @property
    def _tracked_entities(self) -> list[str]:
        main = self.options.get(CONF_SCREEN)
        backup = self.options.get(CONF_BACKUP_SCREEN)
        return [entity for entity in (main, backup) if entity]

    @callback
    def _handle_target_state_change(self, event) -> None:
        """Fin de lecture : restaure le volume ducké et vide la file d'attente."""
        old_state = event.data.get("old_state")
        new_state = event.data.get("new_state")
        entity_id = event.data.get("entity_id")
        if old_state is None or new_state is None:
            return
        if old_state.state == "playing" and new_state.state != "playing":
            if entity_id in self._pending_duck:
                self._restore_duck(entity_id)
            if self._queue:
                self.hass.async_create_task(self._flush_queue())

    # ------------------------------------------------------------------
    # État du téléphone (heartbeat de l'app)
    # ------------------------------------------------------------------

    def async_update_phone(self, device_id: str, active: bool) -> None:
        """Met à jour l'activité signalée par l'app mobile."""
        self._phones[device_id] = {"active": active, "last_seen": time.time()}

    def _phone_is_active(self) -> bool:
        now = time.time()
        return any(
            info.get("active") and now - info.get("last_seen", 0) < PHONE_ACTIVE_EXPIRY
            for info in self._phones.values()
        )

    # ------------------------------------------------------------------
    # Service speak
    # ------------------------------------------------------------------

    async def async_speak(self, data: dict[str, Any]) -> None:
        """Génère la vidéo depuis le texte et la joue (téléphone, écran, backup ou file)."""
        text = (data.get("text") or "").strip()
        if not text:
            raise HomeAssistantError("Le champ 'text' est requis")

        options = self.options
        engine_id = options.get(CONF_TTS_ENGINE)
        if not engine_id:
            raise HomeAssistantError("Aucun moteur TTS configuré")

        priority = bool(
            data.get("priority", options.get(CONF_PRIORITY_DEFAULT, DEFAULT_PRIORITY_DEFAULT))
        )

        # Chemin téléphone : pas de lecture sur les enceintes
        if options.get(CONF_PHONE_ROUTING, DEFAULT_PHONE_ROUTING) and self._phone_is_active():
            try:
                await self._announce_to_phone(text, options)
            except (video.VideoGenerationError, ValueError) as err:
                raise HomeAssistantError(str(err)) from err
            return

        async with self._speak_lock:
            await self._route_speaker(data, text, options, priority)

    async def _route_speaker(
        self, data: dict[str, Any], text: str, options: dict[str, Any], priority: bool
    ) -> None:
        """Choisit la cible (principal / backup / file) et lance l'annonce."""
        main = data.get("target") or options.get(CONF_SCREEN)
        backup = None if data.get("target") else options.get(CONF_BACKUP_SCREEN)
        if not main:
            raise HomeAssistantError("Aucun écran configuré")

        announce: str | None = None
        busy: str | None = None
        if self._is_available(main):
            announce = main
            if self._is_playing(main):
                busy = main
        elif backup and self._is_available(backup):
            announce = backup
            if self._is_playing(backup):
                busy = backup

        if announce is None:
            _LOGGER.warning(
                "Aucun écran disponible (principal et backup), annonce mise en file d'attente"
            )
            self._enqueue(data, priority)
            return

        if busy is None:
            await self._speak_now(announce, options, data)
            return

        if not priority:
            _LOGGER.info("Média en cours de lecture, annonce mise en file d'attente")
            self._enqueue(data, priority)
            return

        # Prioritaire : jouer sur le second appareil et baisser le volume du média
        other = backup if busy == main else main
        if other and other != busy and self._is_available(other) and not self._is_playing(other):
            await self._speak_priority(announce_on=other, duck=busy, options=options, data=data)
            return

        # Pas de second appareil disponible : jouer quand même (remplace le média)
        await self._speak_now(busy, options, data)

    # ------------------------------------------------------------------
    # File d'attente
    # ------------------------------------------------------------------

    def _enqueue(self, data: dict[str, Any], priority: bool) -> None:
        """Met une annonce en file d'attente (les prioritaires passent devant)."""
        if len(self._queue) >= MAX_QUEUE:
            _LOGGER.warning(
                "File d'attente pleine (%s annonces), annonce ignorée : %s",
                MAX_QUEUE,
                (data.get("text") or "")[:50],
            )
            return
        item = {"data": dict(data), "priority": priority}
        if priority:
            index = next(
                (i for i, queued in enumerate(self._queue) if not queued["priority"]),
                len(self._queue),
            )
            self._queue.insert(index, item)
        else:
            self._queue.append(item)
        _LOGGER.info("Annonce en file d'attente (%s en attente)", len(self._queue))

    async def _flush_queue(self) -> None:
        """Joue les annonces en attente dès que l'enceinte est libre."""
        if not self._queue:
            return
        async with self._speak_lock:
            while self._queue:
                item = self._queue[0]
                data = item["data"]
                priority = item["priority"]
                text = (data.get("text") or "").strip()
                if not text:
                    self._queue.pop(0)
                    continue

                options = self.options

                # Re-route vers le téléphone s'il est devenu actif entre-temps
                if options.get(CONF_PHONE_ROUTING, DEFAULT_PHONE_ROUTING) and self._phone_is_active():
                    self._queue.pop(0)
                    try:
                        await self._announce_to_phone(text, options)
                    except (video.VideoGenerationError, ValueError):
                        _LOGGER.exception("Échec de génération téléphone (file d'attente)")
                    continue

                main = data.get("target") or options.get(CONF_SCREEN)
                backup = None if data.get("target") else options.get(CONF_BACKUP_SCREEN)
                if not main:
                    self._queue.pop(0)
                    continue

                announce: str | None = None
                busy: str | None = None
                if self._is_available(main):
                    announce = main
                    if self._is_playing(main):
                        busy = main
                elif backup and self._is_available(backup):
                    announce = backup
                    if self._is_playing(backup):
                        busy = backup

                if announce is None:
                    return  # toujours aucun écran disponible : on attend

                if busy is not None:
                    if not priority:
                        return  # l'enceinte est occupée : on attend
                    other = backup if busy == main else main
                    if (
                        other
                        and other != busy
                        and self._is_available(other)
                        and not self._is_playing(other)
                    ):
                        self._queue.pop(0)
                        await self._speak_priority(
                            announce_on=other, duck=busy, options=options, data=data
                        )
                        return
                    return  # prioritaire mais pas de second appareil : on attend

                self._queue.pop(0)
                try:
                    await self._speak_now(announce, options, data)
                except Exception:
                    _LOGGER.exception("Échec d'une annonce depuis la file d'attente")
                return  # l'enceinte rejoue un média : prochain flush à la fin

    # ------------------------------------------------------------------
    # Lecture
    # ------------------------------------------------------------------

    async def _speak_now(
        self, target: str, options: dict[str, Any], data: dict[str, Any]
    ) -> None:
        """Génère la vidéo et la joue immédiatement sur la cible libre."""
        text = (data.get("text") or "").strip()
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
            await self._play_video(path, url, screen_entity, target, options)
            await asyncio.sleep(0.2)
        finally:
            await self._apply_volume(target, "mute", False, options)

        self.hass.bus.async_fire(
            EVENT_VIDEO_GENERATED,
            {"text": text, "url": url, "path": str(path)},
        )

    async def _speak_priority(
        self,
        announce_on: str,
        duck: str,
        options: dict[str, Any],
        data: dict[str, Any],
    ) -> None:
        """Joue l'annonce sur `announce_on` en baissant le volume du média sur `duck`."""
        if announce_on in self._pending_duck:
            self._restore_duck(announce_on)
        duck_state = self.hass.states.get(duck)
        restore: float | None = None
        if duck_state and duck_state.attributes.get("volume_level") is not None:
            restore = float(duck_state.attributes["volume_level"])
        if restore is None:
            restore = self._fallback_restore_volume(duck, options)
        self._pending_duck[announce_on] = {"duck": duck, "volume": restore}
        try:
            await self._set_volume(
                duck, float(options.get(CONF_DUCK_VOLUME, DEFAULT_DUCK_VOLUME))
            )
            await self._speak_now(announce_on, options, data)
        except Exception:
            self._restore_duck(announce_on)
            raise
        # Sécurité : restaure aussi si la lecture n'a finalement jamais démarré
        self.hass.async_create_task(self._duck_watchdog(announce_on))

    async def _duck_watchdog(self, announce_on: str, delay: float = 10.0) -> None:
        """Restaure le volume ducké si l'annonce n'a jamais démarré."""
        await asyncio.sleep(delay)
        if announce_on in self._pending_duck and not self._is_playing(announce_on):
            _LOGGER.warning(
                "Annonce prioritaire jamais démarrée sur %s, volume restauré", announce_on
            )
            self._restore_duck(announce_on)

    def _restore_duck(self, announce_on: str) -> None:
        """Restaure le volume du média qui avait été baissé (ducking)."""
        info = self._pending_duck.pop(announce_on, None)
        if info is None:
            return
        duck = info["duck"]
        volume = info["volume"]
        _LOGGER.info("Restauration du volume de %s à %s", duck, volume)
        self.hass.async_create_task(self._set_volume(duck, volume))

    async def _announce_to_phone(self, text: str, options: dict[str, Any]) -> None:
        """Génère la vidéo et la notifie à l'app mobile (overlay)."""
        audio_bytes = await self._generate_audio(text, options)
        path, url = await self._generate_video(audio_bytes, options)
        self.hass.bus.async_fire(
            EVENT_VIDEO_GENERATED,
            {"text": text, "url": url, "path": str(path)},
        )
        self.hass.bus.async_fire(
            EVENT_PHONE_ANNOUNCEMENT,
            {"text": text, "url": url, "path": str(path)},
        )
        _LOGGER.info("Annonce envoyée au téléphone (overlay) : %s", url)

    async def _play_video(
        self,
        path: Path,
        url: str,
        screen_entity: DttsvgScreen | None,
        target: str,
        options: dict[str, Any],
    ) -> None:
        """Lance la vidéo sur l'écran réel (via l'entité virtuelle ou directement)."""
        # L'entité virtuelle ne relaie que vers l'écran principal configuré
        if screen_entity is not None and target == options.get(CONF_SCREEN):
            await screen_entity.async_play_generated_video(str(path), url)
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

        _, audio_bytes = await tts_compat.async_get_tts_audio(
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

    # ------------------------------------------------------------------
    # Volume
    # ------------------------------------------------------------------

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

    async def _set_volume(self, target: str, volume: float) -> None:
        """Applique un volume précis sur un media player."""
        if not target:
            return
        await self.hass.services.async_call(
            "media_player",
            "volume_set",
            {"entity_id": target, "volume_level": float(volume)},
            blocking=True,
        )

    def _fallback_restore_volume(self, target: str, options: dict[str, Any]) -> float:
        """Volume de secours à restaurer si l'entité n'expose pas de volume."""
        mode = options.get(CONF_VOLUME_MODE)
        if mode == VOLUME_MODE_DAY_NIGHT:
            sun_state = self.hass.states.get("sun.sun")
            is_day = sun_state is not None and sun_state.state == "above_horizon"
            volume = options.get(CONF_DAY_VOLUME, 0.5) if is_day else options.get(CONF_NIGHT_VOLUME, 0.2)
        else:
            volume = options.get(CONF_DAY_VOLUME, 0.5)
        return float(volume)

    def _is_available(self, entity_id: str) -> bool:
        state = self.hass.states.get(entity_id)
        return state is not None and state.state != "unavailable"

    def _is_playing(self, entity_id: str) -> bool:
        state = self.hass.states.get(entity_id)
        return state is not None and state.state == "playing"
