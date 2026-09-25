"""Entité media_player « écran » virtuelle de DTTSVG.

Son état reflète l'écran réel (ex: media_player.nest_hub) et toutes les
commandes (play_media, play, pause, stop, volume...) sont relayées à cet écran
via le composant media_player de Home Assistant (cast natif).
"""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components import media_player
from homeassistant.components.media_player import (
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    STATE_IDLE,
    STATE_OFF,
    STATE_ON,
    STATE_PAUSED,
    STATE_PLAYING,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_platform
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import (
    ATTR_LAST_VIDEO_PATH,
    ATTR_LAST_VIDEO_URL,
    ATTR_TARGET_ENTITY,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

_MIRRORED_ATTRIBUTES = (
    "media_title",
    "media_content_id",
    "media_content_type",
    "volume_level",
    "is_volume_muted",
    "media_duration",
    "media_position",
    "media_position_updated_at",
    "media_artist",
    "media_album_name",
)

#: Correspondance état écran réel -> état entité virtuelle
_STATE_MAP = {
    "playing": STATE_PLAYING,
    "paused": STATE_PAUSED,
    "idle": STATE_IDLE,
    "off": STATE_OFF,
    "standby": STATE_IDLE,
    "unavailable": "unavailable",
    "on": STATE_ON,
}


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: entity_platform.AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Setup de la plateforme (entrée via config flow)."""
    entries = hass.config_entries.async_entries(DOMAIN)
    async_add_entities([DttsvgScreen(entry) for entry in entries], update_before_add=False)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: entity_platform.AddEntitiesCallback,
) -> None:
    """Crée l'entité écran pour une entrée de configuration."""
    async_add_entities([DttsvgScreen(entry)], update_before_add=False)


class DttsvgScreen(MediaPlayerEntity):
    """Écran virtuel qui relaie les commandes vers l'écran réel."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, entry: ConfigEntry) -> None:
        """Initialise l'entité."""
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_screen"
        self._attr_supported_features = (
            MediaPlayerEntityFeature.PLAY_MEDIA
            | MediaPlayerEntityFeature.PLAY
            | MediaPlayerEntityFeature.PAUSE
            | MediaPlayerEntityFeature.STOP
            | MediaPlayerEntityFeature.TURN_ON
            | MediaPlayerEntityFeature.TURN_OFF
            | MediaPlayerEntityFeature.VOLUME_SET
            | MediaPlayerEntityFeature.VOLUME_MUTE
        )
        self._target: str = ""
        self._unsub = None
        self._last_video_url: str | None = None
        self._last_video_path: str | None = None

    @property
    def target_entity(self) -> str:
        """Entité écran réelle configurée."""
        return self._target

    async def async_added_to_hass(self) -> None:
        """Enregistre le suivi de l'écran réel."""
        await super().async_added_to_hass()
        self._entry.async_on_unload(self._entry.add_update_listener(self._handle_options_change))
        self._target = self._entry.options.get("screen") or ""
        if not self._target:
            self._attr_state = "unavailable"
            return
        self._sync_from_target(self.hass.states.get(self._target))
        self._unsub = async_track_state_change_event(
            self.hass, [self._target], self._handle_target_change
        )

    async def _handle_options_change(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Met à jour l'écran cible quand les options changent."""
        new_target = entry.options.get("screen") or ""
        if new_target == self._target:
            return
        if self._unsub is not None:
            self._unsub()
            self._unsub = None
        self._target = new_target
        if new_target:
            self._unsub = async_track_state_change_event(
                hass, [new_target], self._handle_target_change
            )
        self._sync_from_target(hass.states.get(new_target))
        self.async_write_ha_state()

    async def async_will_remove_from_hass(self) -> None:
        """Désenregistre le suivi."""
        if self._unsub is not None:
            self._unsub()
            self._unsub = None
        await super().async_will_remove_from_hass()

    @callback
    def _handle_target_change(self, event) -> None:
        self._sync_from_target(self.hass.states.get(self._target))
        self.async_write_ha_state()

    @callback
    def _sync_from_target(self, state) -> None:
        if state is None:
            self._attr_state = "unavailable"
            self._attr_available = False
            return
        self._attr_available = state.state != "unavailable"
        self._attr_state = _STATE_MAP.get(state.state, state.state)
        for attr in _MIRRORED_ATTRIBUTES:
            value = state.attributes.get(attr)
            if value is None:
                continue
            setattr(self, f"_attr_{attr}", value)

    async def async_play_media(
        self,
        media_type: str,
        media_id: str,
        enqueue: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Joue un média sur l'écran réel (ou parle si le type est text)."""
        if media_type == "text":
            hubs = self.hass.data.get(DOMAIN, {})
            if hubs:
                await next(iter(hubs.values())).async_speak(media_id)
            return
        if not self._target:
            _LOGGER.warning("Aucun écran cible configuré")
            return
        data = {
            "entity_id": self._target,
            "media_content_type": media_type,
            "media_content_id": media_id,
        }
        if enqueue is not None:
            data["enqueue"] = enqueue
        await self.hass.services.async_call(
            media_player.DOMAIN, media_player.SERVICE_PLAY_MEDIA, data, blocking=True
        )

    async def _forward(self, service: str, data: dict[str, Any] | None = None) -> None:
        if not self._target:
            return
        payload = {"entity_id": self._target}
        if data:
            payload.update(data)
        await self.hass.services.async_call(
            media_player.DOMAIN, service, payload, blocking=True
        )

    async def async_media_play(self) -> None:
        await self._forward(media_player.SERVICE_MEDIA_PLAY)

    async def async_media_pause(self) -> None:
        await self._forward(media_player.SERVICE_MEDIA_PAUSE)

    async def async_media_stop(self) -> None:
        await self._forward(media_player.SERVICE_MEDIA_STOP)

    async def async_turn_on(self) -> None:
        await self._forward(media_player.SERVICE_TURN_ON)

    async def async_turn_off(self) -> None:
        await self._forward(media_player.SERVICE_TURN_OFF)

    async def async_set_volume_level(self, volume: float) -> None:
        await self._forward(media_player.SERVICE_VOLUME_SET, {"volume_level": volume})

    async def async_mute_volume(self, mute: bool) -> None:
        await self._forward(media_player.SERVICE_VOLUME_MUTE, {"is_volume_muted": mute})

    async def async_play_generated_video(self, path: str, url: str) -> None:
        """Joue la vidéo générée sur l'écran réel."""
        self._last_video_path = path
        self._last_video_url = url
        self.async_write_ha_state()
        if not self._target:
            _LOGGER.warning("Aucun écran cible configuré, vidéo non jouée")
            return
        await self._forward(media_player.SERVICE_PLAY_MEDIA, {
            "media_content_type": "video/mp4",
            "media_content_id": url,
        })

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Attributs supplémentaires."""
        attrs: dict[str, Any] = {}
        if self._last_video_url:
            attrs[ATTR_LAST_VIDEO_URL] = self._last_video_url
        if self._last_video_path:
            attrs[ATTR_LAST_VIDEO_PATH] = self._last_video_path
        if self._target:
            attrs[ATTR_TARGET_ENTITY] = self._target
        return attrs