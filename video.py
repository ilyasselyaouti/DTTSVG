"""Génération de la vidéo d'onde sonore avec PyAV (ffmpeg embarqué).

Pipeline :
1. Décodage de l'audio (WAV/MP3/OGG/FLAC...) via PyAV
2. Rééchantillonnage mono float32 44.1 kHz
3. Construction des frames d'onde (numpy + Pillow) sur fond background.png
4. Encodage H.264 + AAC dans un MP4 (libx264 embarqué dans PyAV)

Fonctions synchrones : l'appelant doit les exécuter via un executor
(hass.async_add_executor_job) pour ne pas bloquer la boucle d'événements.
"""

from __future__ import annotations

import io
import math
import re
from fractions import Fraction
from pathlib import Path

import av
import numpy as np
from PIL import Image, ImageOps

DEFAULT_SAMPLE_RATE = 44100
DEFAULT_FPS = 30
WAVE_ALPHA = 220


class VideoGenerationError(Exception):
    """Erreur lors de la génération de la vidéo."""


def _resample(resampler: av.AudioResampler, frame: av.AudioFrame | None) -> list[av.AudioFrame]:
    """Compat entre les versions de PyAV (liste ou générateur)."""
    try:
        result = resampler.resample(frame)
    except (TypeError, ValueError):
        return []
    if result is None:
        return []
    if isinstance(result, (list, tuple)):
        return list(result)
    return list(result)


def decode_audio_to_mono(audio_bytes: bytes, sample_rate: int = DEFAULT_SAMPLE_RATE) -> np.ndarray:
    """Décode l'audio (n'importe quel format) en numpy float32 mono."""
    if not audio_bytes:
        raise VideoGenerationError("Données audio vides reçues du moteur TTS")

    chunks: list[np.ndarray] = []
    try:
        container = av.open(io.BytesIO(audio_bytes))
    except Exception as err:  # pylint: disable=broad-except
        raise VideoGenerationError(f"Audio illisible : {err}") from err

    stream = container.streams.audio[0]
    resampler = av.AudioResampler(format="fltp", layout="mono", rate=sample_rate)

    try:
        for frame in container.decode(stream):
            frame.pts = None
            for out_frame in _resample(resampler, frame):
                chunks.append(out_frame.to_ndarray().reshape(-1).astype(np.float32))
        for out_frame in _resample(resampler, None):
            chunks.append(out_frame.to_ndarray().reshape(-1).astype(np.float32))
    except Exception as err:  # pylint: disable=broad-except
        raise VideoGenerationError(f"Erreur de décodage audio : {err}") from err
    finally:
        container.close()

    if not chunks:
        raise VideoGenerationError("Aucun échantillon audio décodé")
    return np.concatenate(chunks)


def _build_wave_overlay(
    audio: np.ndarray,
    start_sample: int,
    frame_samples: int,
    width: int,
    height: int,
    color: tuple[int, int, int],
) -> np.ndarray:
    """Construit l'overlay RGBA de l'onde pour une frame vidéo."""
    overlay = np.zeros((height, width, 4), dtype=np.uint8)

    end = min(start_sample + frame_samples, audio.size)
    segment = audio[start_sample:end]
    if segment.size == 0:
        return overlay

    cols = np.linspace(0, segment.size - 1, width, dtype=np.int64)
    amps = np.abs(segment[cols])
    amps = np.sqrt(np.clip(amps, 0.0, 1.0))

    cy = height // 2
    half = (amps * (height * 0.5 - 2)).astype(np.int32)
    r, g, b = color

    for x in range(width):
        h = int(half[x])
        if h <= 0:
            continue
        overlay[cy - h : cy + h + 1, x] = (r, g, b, WAVE_ALPHA)

    return overlay


def _compose_frame(
    background: np.ndarray,
    overlay: np.ndarray,
    wave_offset_y: int,
) -> np.ndarray:
    """Compose l'onde sur le fond (RGBA over RGB)."""
    frame = background.copy()
    if wave_offset_y >= frame.shape[0]:
        return frame
    slice_end = min(wave_offset_y + overlay.shape[0], frame.shape[0])
    overlay = overlay[: slice_end - wave_offset_y]

    bg_slice = frame[wave_offset_y:slice_end].astype(np.float32)
    alpha = overlay[:, :, 3:4].astype(np.float32) / 255.0
    fg = overlay[:, :, :3].astype(np.float32)
    frame[wave_offset_y:slice_end] = (fg * alpha + bg_slice * (1.0 - alpha)).astype(np.uint8)
    return frame


def generate_video(
    audio_bytes: bytes,
    output_path: str,
    background_path: str,
    width: int = 1024,
    height: int = 600,
    wave_height: int = 240,
    wave_color: str = "#00ccff",
    start_delay: float = 2.0,
    fps: int = DEFAULT_FPS,
) -> str:
    """Génère le MP4 d'onde sonore et l'écrit dans output_path.

    Retourne le chemin du fichier généré.
    """
    sample_rate = DEFAULT_SAMPLE_RATE
    delay_samples = int(start_delay * sample_rate)
    frame_samples = sample_rate // fps

    audio = decode_audio_to_mono(audio_bytes, sample_rate)
    total_audio_samples = audio.size
    total_samples = delay_samples + total_audio_samples
    total_frames = max(1, math.ceil(total_samples / frame_samples))

    padded_audio = np.zeros(total_samples, dtype=np.float32)
    padded_audio[delay_samples:] = audio

    try:
        background_img = Image.open(background_path).convert("RGB")
    except Exception as err:  # pylint: disable=broad-except
        raise VideoGenerationError(f"Fond illisible ({background_path}) : {err}") from err

    background_img = ImageOps.fit(background_img, (width, height), Image.Resampling.LANCZOS)
    background = np.asarray(background_img, dtype=np.uint8)

    color = _parse_color(wave_color)
    wave_offset_y = max(0, (height - wave_height) // 2)

    output = av.open(output_path, "w")

    video_stream = output.add_stream("h264", rate=fps)
    video_stream.width = width
    video_stream.height = height
    video_stream.pix_fmt = "yuv420p"
    video_stream.options = {"preset": "veryfast", "crf": "20"}
    video_stream.time_base = Fraction(1, fps)

    audio_stream = output.add_stream("aac", rate=sample_rate)
    audio_stream.layout = "mono"
    audio_stream.time_base = Fraction(1, sample_rate)

    audio_index = 0
    try:
        for frame_idx in range(total_frames):
            frame_start = frame_idx * frame_samples

            if frame_start < delay_samples:
                overlay = np.zeros((wave_height, width, 4), dtype=np.uint8)
            else:
                overlay = _build_wave_overlay(
                    audio, frame_start - delay_samples, frame_samples, width, wave_height, color
                )

            frame = _compose_frame(background, overlay, wave_offset_y)
            video_frame = av.VideoFrame.from_ndarray(frame, format="rgb24")
            video_frame.pts = frame_idx
            for packet in video_stream.encode(video_frame):
                output.mux(packet)

            segment = padded_audio[audio_index : audio_index + frame_samples]
            segment = np.pad(segment, (0, max(0, frame_samples - segment.size)))
            audio_frame = av.AudioFrame.from_ndarray(
                segment.reshape(1, -1), format="fltp", layout="mono"
            )
            audio_frame.sample_rate = sample_rate
            audio_frame.pts = audio_index
            audio_index += frame_samples
            for packet in audio_stream.encode(audio_frame):
                output.mux(packet)

        for packet in video_stream.encode(None):
            output.mux(packet)
        for packet in audio_stream.encode(None):
            output.mux(packet)
    except Exception as err:  # pylint: disable=broad-except
        raise VideoGenerationError(f"Erreur d'encodage vidéo : {err}") from err
    finally:
        output.close()

    if not Path(output_path).exists() or Path(output_path).stat().st_size == 0:
        raise VideoGenerationError("La vidéo générée est vide")

    return output_path


def _parse_color(color: str | tuple | list) -> tuple[int, int, int]:
    if isinstance(color, (tuple, list)) and len(color) == 3:
        return tuple(int(c) for c in color)
    if not isinstance(color, str):
        raise VideoGenerationError(f"Couleur invalide : {color}")
    match = re.match(r"rgb\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)", color)
    if match:
        return tuple(int(g) for g in match.groups())
    color = color.lstrip("#")
    if len(color) != 6:
        raise VideoGenerationError(f"Couleur invalide : {color}")
    try:
        return tuple(int(color[i : i + 2], 16) for i in (0, 2, 4))
    except ValueError as err:
        raise VideoGenerationError(f"Couleur invalide : {color}") from err