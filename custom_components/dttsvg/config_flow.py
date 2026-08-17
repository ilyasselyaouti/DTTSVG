"""Config flow et options flow (GUI) pour DTTSVG.

Parcours :
1. Choix du moteur TTS (liste dynamique de tous les moteurs configurés dans HA)
2. Choix de la langue (supportée par le moteur)
3. Choix de la voix (si le moteur en gère)
4. Choix de l'écran cible (media_player réel, ex. Nest Hub) + options avancées
"""

from __future__ import annotations

import inspect
import re
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, OptionsFlow
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector

from . import tts_compat
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
    DEFAULT_DAY_VOLUME,
    DEFAULT_MUTE_DURING_GENERATION,
    DEFAULT_NIGHT_VOLUME,
    DEFAULT_START_DELAY,
    DEFAULT_VIDEO_HEIGHT,
    DEFAULT_VIDEO_WIDTH,
    DEFAULT_VOLUME_MODE,
    DEFAULT_WAVE_COLOR,
    DEFAULT_WAVE_HEIGHT,
    DOMAIN,
    VOLUME_MODE_DAY_NIGHT,
    VOLUME_MODE_FIXED,
)


_SUPPORTS_DATA_SCHEMA = "data_schema" in inspect.signature(
    ConfigFlow.async_show_form
).parameters


def _async_show_form(
    flow: ConfigFlow | OptionsFlow,
    step_id: str,
    schema: vol.Schema | None = None,
    errors: dict[str, str] | None = None,
) -> FlowResult:
    """Affiche un formulaire (compat schema / data_schema selon la version de HA)."""
    kwargs: dict[str, Any] = {"step_id": step_id, "errors": errors}
    if schema is not None:
        if _SUPPORTS_DATA_SCHEMA:
            kwargs["data_schema"] = schema
        else:
            kwargs["schema"] = schema
    return flow.async_show_form(**kwargs)


def _screen_schema(defaults: dict[str, Any]) -> vol.Schema:
    """Schéma écran cible + options de lecture."""
    return vol.Schema(
        {
            vol.Required(CONF_SCREEN, default=defaults.get(CONF_SCREEN, vol.UNDEFINED)): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="media_player")
            ),
            vol.Required(
                CONF_VOLUME_MODE, default=defaults.get(CONF_VOLUME_MODE, DEFAULT_VOLUME_MODE)
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[
                        selector.SelectOptionDict(value=VOLUME_MODE_FIXED, label="Fixe"),
                        selector.SelectOptionDict(
                            value=VOLUME_MODE_DAY_NIGHT, label="Jour / Nuit"
                        ),
                    ],
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            ),
            vol.Required(
                CONF_DAY_VOLUME, default=defaults.get(CONF_DAY_VOLUME, DEFAULT_DAY_VOLUME)
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0.0, max=1.0, step=0.05, mode=selector.NumberSelectorMode.SLIDER
                )
            ),
            vol.Required(
                CONF_NIGHT_VOLUME, default=defaults.get(CONF_NIGHT_VOLUME, DEFAULT_NIGHT_VOLUME)
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0.0, max=1.0, step=0.05, mode=selector.NumberSelectorMode.SLIDER
                )
            ),
            vol.Required(
                CONF_MUTE_DURING_GENERATION,
                default=defaults.get(CONF_MUTE_DURING_GENERATION, DEFAULT_MUTE_DURING_GENERATION),
            ): selector.BooleanSelector(),
            vol.Required(
                CONF_START_DELAY, default=defaults.get(CONF_START_DELAY, DEFAULT_START_DELAY)
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0.0, max=10.0, step=0.5, mode=selector.NumberSelectorMode.BOX
                )
            ),
        }
    )


def _color_selector() -> Any:
    """Sélecteur de couleur (ColorRGBSelector en 2026+, ColorSelector avant)."""
    color_rgb = getattr(selector, "ColorRGBSelector", None)
    if color_rgb is not None:
        return color_rgb()
    return selector.ColorSelector()


def _normalize_color(value: Any) -> str:
    """Normalise une couleur en hexadécimal '#rrggbb'."""
    if isinstance(value, (list, tuple)) and len(value) == 3:
        return "#{:02x}{:02x}{:02x}".format(*(int(c) for c in value))
    if isinstance(value, str):
        if value.startswith("#") and len(value) == 7:
            return value
        match = re.match(r"rgb\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)", value)
        if match:
            return "#{:02x}{:02x}{:02x}".format(*(int(g) for g in match.groups()))
    return DEFAULT_WAVE_COLOR


def _selector_color_default(defaults: dict[str, Any]) -> Any:
    """Valeur par défaut de la couleur au format attendu par le sélecteur."""
    color = _normalize_color(defaults.get(CONF_WAVE_COLOR, DEFAULT_WAVE_COLOR))
    if getattr(selector, "ColorRGBSelector", None) is not None:
        return [int(color[1:3], 16), int(color[3:5], 16), int(color[5:7], 16)]
    return color


def _visual_schema(defaults: dict[str, Any]) -> vol.Schema:
    """Schéma options visuelles (fond, onde, taille)."""
    return vol.Schema(
        {
            vol.Required(
                CONF_WAVE_COLOR, default=_selector_color_default(defaults)
            ): _color_selector(),
            vol.Required(
                CONF_WAVE_HEIGHT, default=defaults.get(CONF_WAVE_HEIGHT, DEFAULT_WAVE_HEIGHT)
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=50, max=550, step=10, mode=selector.NumberSelectorMode.SLIDER
                )
            ),
            vol.Required(
                CONF_VIDEO_WIDTH, default=defaults.get(CONF_VIDEO_WIDTH, DEFAULT_VIDEO_WIDTH)
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=320, max=3840, step=32, mode=selector.NumberSelectorMode.BOX
                )
            ),
            vol.Required(
                CONF_VIDEO_HEIGHT, default=defaults.get(CONF_VIDEO_HEIGHT, DEFAULT_VIDEO_HEIGHT)
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=240, max=2160, step=16, mode=selector.NumberSelectorMode.BOX
                )
            ),
        }
    )


class DttsvgConfigFlow(ConfigFlow, domain=DOMAIN):
    """Config flow de DTTSVG."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialise le flux."""
        super().__init__()
        self._data: dict[str, Any] = {}

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Étape 1 : choix du moteur TTS."""
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()

        engine_ids = tts_compat.async_get_engine_ids(self.hass)
        if not engine_ids:
            return _async_show_form(self, step_id="user", errors={"base": "no_engines"})

        default_engine = self._data.get(CONF_TTS_ENGINE)
        if not default_engine:
            default_engine = getattr(tts_compat.tts, "async_default_engine", None)
            if default_engine is not None:
                default_engine = default_engine(self.hass)
        if default_engine not in engine_ids:
            default_engine = engine_ids[0]
        schema = vol.Schema(
            {
                vol.Required(CONF_TTS_ENGINE, default=default_engine): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=engine_ids, mode=selector.SelectSelectorMode.DROPDOWN
                    )
                )
            }
        )

        if user_input is not None:
            self._data.update(user_input)
            engine = tts_compat.async_get_engine(self.hass, user_input[CONF_TTS_ENGINE])
            if engine is None:
                return _async_show_form(self, step_id="user", schema=schema, errors={"base": "unknown_engine"})
            return await self.async_step_language()

        return _async_show_form(self, step_id="user", schema=schema)

    async def async_step_language(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Étape 2 : choix de la langue."""
        engine = tts_compat.async_get_engine(self.hass, self._data[CONF_TTS_ENGINE])
        if engine is None:
            return self.async_abort(reason="engine_unavailable")

        languages = tts_compat.async_get_supported_languages(engine)
        default_language = (
            self._data.get(CONF_LANGUAGE) or tts_compat.async_get_default_language(engine)
        )
        if default_language not in languages and languages:
            default_language = languages[0]

        schema = vol.Schema(
            {
                vol.Required(CONF_LANGUAGE, default=default_language): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=languages, mode=selector.SelectSelectorMode.DROPDOWN
                    )
                )
            }
        )
        if user_input is not None:
            self._data.update(user_input)
            return await self.async_step_voice()

        return _async_show_form(self, step_id="language", schema=schema)

    async def async_step_voice(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Étape 3 : choix de la voix (si le moteur en gère)."""
        engine = tts_compat.async_get_engine(self.hass, self._data[CONF_TTS_ENGINE])
        language = self._data[CONF_LANGUAGE]
        voices = tts_compat.async_get_voices(engine, language) if engine else None

        if not voices:
            return await self.async_step_screen()

        default_voice = (
            self._data.get(CONF_VOICE) or tts_compat.async_get_default_voice(engine, language)
        )
        if default_voice not in voices and voices:
            default_voice = voices[0]

        schema = vol.Schema(
            {
                vol.Required(CONF_VOICE, default=default_voice): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=voices, mode=selector.SelectSelectorMode.DROPDOWN
                    )
                )
            }
        )
        if user_input is not None:
            self._data.update(user_input)
            return await self.async_step_screen()

        return _async_show_form(self, step_id="voice", schema=schema)

    async def async_step_screen(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Étape 4 : écran cible + options de lecture."""
        schema = _screen_schema(self._data)
        if user_input is not None:
            self._data.update(user_input)
            return await self.async_step_visual()

        return _async_show_form(self, step_id="screen", schema=schema)

    async def async_step_visual(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Étape 5 : options visuelles."""
        schema = _visual_schema(self._data)
        if user_input is not None:
            user_input = dict(user_input)
            user_input[CONF_WAVE_COLOR] = _normalize_color(user_input[CONF_WAVE_COLOR])
            self._data.update(user_input)
            return self.async_create_entry(
                title=f"DTTSVG - {self._data[CONF_TTS_ENGINE]}", data={}, options=self._data
            )

        return _async_show_form(self, step_id="visual", schema=schema)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Retourne le flux d'options."""
        return DttsvgOptionsFlow(config_entry)


class DttsvgOptionsFlow(OptionsFlow):
    """Options flow de DTTSVG (modification après installation)."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialise avec l'entrée existante."""
        self._entry = config_entry
        self._data: dict[str, Any] = dict(config_entry.options)

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Point d'entrée : choix du moteur TTS."""
        return await self.async_step_engine()

    async def async_step_engine(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Choix du moteur TTS."""
        engine_ids = tts_compat.async_get_engine_ids(self.hass)
        if not engine_ids:
            return self.async_abort(reason="no_engines")

        default_engine = self._data.get(CONF_TTS_ENGINE)
        if not default_engine:
            default_engine = getattr(tts_compat.tts, "async_default_engine", None)
            if default_engine is not None:
                default_engine = default_engine(self.hass)
        if default_engine not in engine_ids:
            default_engine = engine_ids[0]
        schema = vol.Schema(
            {
                vol.Required(CONF_TTS_ENGINE, default=default_engine): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=engine_ids, mode=selector.SelectSelectorMode.DROPDOWN
                    )
                )
            }
        )
        if user_input is not None:
            self._data.update(user_input)
            return await self.async_step_language()

        return _async_show_form(self, step_id="engine", schema=schema)

    async def async_step_language(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Choix de la langue."""
        engine = tts_compat.async_get_engine(self.hass, self._data[CONF_TTS_ENGINE])
        if engine is None:
            return self.async_abort(reason="engine_unavailable")

        languages = tts_compat.async_get_supported_languages(engine)
        default_language = (
            self._data.get(CONF_LANGUAGE) or tts_compat.async_get_default_language(engine)
        )
        if default_language not in languages and languages:
            default_language = languages[0]

        schema = vol.Schema(
            {
                vol.Required(CONF_LANGUAGE, default=default_language): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=languages, mode=selector.SelectSelectorMode.DROPDOWN
                    )
                )
            }
        )
        if user_input is not None:
            self._data.update(user_input)
            return await self.async_step_voice()

        return _async_show_form(self, step_id="language", schema=schema)

    async def async_step_voice(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Choix de la voix."""
        engine = tts_compat.async_get_engine(self.hass, self._data[CONF_TTS_ENGINE])
        language = self._data[CONF_LANGUAGE]
        voices = tts_compat.async_get_voices(engine, language) if engine else None

        if not voices:
            return await self.async_step_screen()

        default_voice = (
            self._data.get(CONF_VOICE) or tts_compat.async_get_default_voice(engine, language)
        )
        if default_voice not in voices and voices:
            default_voice = voices[0]

        schema = vol.Schema(
            {
                vol.Required(CONF_VOICE, default=default_voice): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=voices, mode=selector.SelectSelectorMode.DROPDOWN
                    )
                )
            }
        )
        if user_input is not None:
            self._data.update(user_input)
            return await self.async_step_screen()

        return _async_show_form(self, step_id="voice", schema=schema)

    async def async_step_screen(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Écran cible + options de lecture."""
        schema = _screen_schema(self._data)
        if user_input is not None:
            self._data.update(user_input)
            return await self.async_step_visual()

        return _async_show_form(self, step_id="screen", schema=schema)

    async def async_step_visual(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Options visuelles."""
        schema = _visual_schema(self._data)
        if user_input is not None:
            user_input = dict(user_input)
            user_input[CONF_WAVE_COLOR] = _normalize_color(user_input[CONF_WAVE_COLOR])
            self._data.update(user_input)
            return self.async_create_entry(data=self._data)

        return _async_show_form(self, step_id="visual", schema=schema)