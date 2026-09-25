"""Couche de compatibilité multi-versions pour le composant TTS de Home Assistant.

Deux mondes coexistent selon la version de HA :

- HA ≤ 2024 : `hass.data[tts.DOMAIN]` est un dict {engine_id: Provider},
  audio via `tts.async_get_engine` + `Provider.async_get_tts_audio`.
- HA 2025+ : les moteurs sont des entités (`EntityComponent` dans
  `hass.data[tts.DOMAIN]`) + providers legacy (`SpeechManager.providers`
  dans `hass.data[tts.DATA_TTS_MANAGER]`), audio via l'API de streaming
  `tts.async_create_stream` (compatible moteurs entité ET legacy).

Ce module détecte l'API disponible et fonctionne avec toutes les versions.
"""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components import tts
from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)


def _iter_entities(hass: HomeAssistant) -> list[Any]:
    """Itère les moteurs TTS basés sur des entités (nouvelle API)."""
    component = hass.data.get(tts.DATA_COMPONENT)
    if component is None:
        return []
    if isinstance(component, dict):
        return []
    entities = getattr(component, "entities", None)
    if not entities:
        return []
    return list(entities.values()) if isinstance(entities, dict) else list(entities)


def _iter_providers(hass: HomeAssistant) -> dict[str, Any]:
    """Retourne les providers legacy (nouvelle API) ou le dict (ancienne API)."""
    manager = hass.data.get(tts.DATA_TTS_MANAGER)
    if isinstance(manager, dict):
        return manager
    providers = getattr(manager, "providers", None)
    return providers if isinstance(providers, dict) else {}


def async_get_engine_ids(hass: HomeAssistant) -> list[str]:
    """Liste les identifiants de tous les moteurs TTS configurés (toutes versions)."""
    engine_ids: set[str] = set()

    for entity in _iter_entities(hass):
        if getattr(entity, "entity_id", None):
            engine_ids.add(entity.entity_id)

    engine_ids.update(_iter_providers(hass).keys())

    legacy = hass.data.get(tts.DOMAIN)
    if isinstance(legacy, dict):
        engine_ids.update(legacy.keys())

    return sorted(engine_ids)


def async_get_engine(hass: HomeAssistant, engine_id: str) -> Any | None:
    """Récupère un moteur TTS par son identifiant (toutes versions confondues)."""
    get_engine = getattr(tts, "async_get_engine", None)
    if get_engine is not None:
        engine = get_engine(hass, engine_id)
        if engine is not None:
            return engine

    for entity in _iter_entities(hass):
        if getattr(entity, "entity_id", None) == engine_id:
            return entity

    legacy = hass.data.get(tts.DOMAIN)
    if isinstance(legacy, dict) and engine_id in legacy:
        return legacy[engine_id]

    return _iter_providers(hass).get(engine_id)


def async_get_supported_languages(engine: Any) -> list[str]:
    """Langues supportées par un moteur (list|dict selon la version)."""
    languages = getattr(engine, "supported_languages", None)
    if languages is None:
        default = getattr(engine, "default_language", None)
        return [default] if default else []
    if isinstance(languages, dict):
        return sorted(languages.keys())
    return sorted(languages)


def async_get_default_language(engine: Any) -> str | None:
    """Langue par défaut du moteur."""
    return getattr(engine, "default_language", None)


def async_get_voices(engine: Any, language: str) -> list[str] | None:
    """Voix disponibles pour une langue (None si le moteur n'en gère pas)."""
    get_voices = getattr(engine, "async_get_supported_voices", None)
    if get_voices is not None:
        try:
            voices = get_voices(language)
            if voices:
                return sorted(voice.voice_id for voice in voices)
        except Exception:  # pylint: disable=broad-except
            _LOGGER.debug("Voix non récupérables via async_get_supported_voices", exc_info=True)
            return None
        return None

    voices = getattr(engine, "voices", None)
    if not voices:
        return None
    if isinstance(voices, dict):
        found = voices.get(language) or voices.get(language.split("-")[0])
        if found:
            return sorted(str(voice) for voice in found)
        return None
    return sorted(str(voice) for voice in voices)


def async_get_default_voice(engine: Any, language: str) -> str | None:
    """Voix par défaut pour une langue si le moteur en gère."""
    get_voices = getattr(engine, "async_get_supported_voices", None)
    if get_voices is not None:
        try:
            voices = get_voices(language)
            if voices:
                return voices[0].voice_id
        except Exception:  # pylint: disable=broad-except
            return None
        return None
    voices = getattr(engine, "voices", None)
    if not voices:
        return None
    if isinstance(voices, dict):
        found = voices.get(language) or voices.get(language.split("-")[0])
        return str(found[0]) if found else None
    return str(voices[0])


def async_get_default_options(engine: Any) -> dict[str, Any]:
    """Options par défaut du moteur (ex: voix)."""
    options = getattr(engine, "default_options", None)
    return dict(options) if options else {}


def async_get_supported_options(engine: Any) -> list[str]:
    """Options supportées par le moteur."""
    options = getattr(engine, "supported_options", None)
    return list(options) if options else []


async def async_get_tts_audio(
    hass: HomeAssistant,
    engine_id: str,
    message: str,
    language: str,
    options: dict[str, Any] | None = None,
) -> tuple[str, bytes]:
    """Génère l'audio via le moteur TTS sélectionné.

    Retourne (extension, données audio binaires).
    """
    options = options or {}
    create_stream = getattr(tts, "async_create_stream", None)
    if create_stream is not None:
        # HA 2025+ : API streaming (moteurs entités + providers legacy)
        try:
            stream = create_stream(hass, engine_id, language=language, options=options)
            stream.async_set_message(message)
            data = b"".join([chunk async for chunk in stream.async_stream_result()])
        except Exception as err:  # pylint: disable=broad-except
            raise ValueError(f"Erreur de génération TTS ({engine_id}) : {err}") from err
        if not data:
            raise ValueError(f"Le moteur {engine_id} n'a retourné aucune donnée audio")
        return stream.extension, data

    # HA ≤ 2024 : API Provider.async_get_tts_audio
    engine = async_get_engine(hass, engine_id)
    if engine is None:
        raise ValueError(f"Moteur TTS introuvable : {engine_id}")

    get_audio = getattr(engine, "async_get_tts_audio", None)
    if get_audio is None:
        raise ValueError(f"Le moteur {engine_id} ne supporte pas la génération audio")

    result = await get_audio(message, language=language, options=options)
    if isinstance(result, tuple):
        extension, data = result
        if not data:
            raise ValueError(f"Le moteur {engine_id} n'a retourné aucune donnée audio")
        return extension, data
    raise ValueError(f"Réponse audio invalide du moteur {engine_id}")