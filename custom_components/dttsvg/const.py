"""Constantes pour DTTSVG."""

DOMAIN = "dttsvg"

CONF_TTS_ENGINE = "tts_engine"
CONF_LANGUAGE = "language"
CONF_VOICE = "voice"
CONF_SCREEN = "screen"
CONF_BACKGROUND = "background"
CONF_WAVE_COLOR = "wave_color"
CONF_VIDEO_WIDTH = "video_width"
CONF_VIDEO_HEIGHT = "video_height"
CONF_WAVE_HEIGHT = "wave_height"
CONF_MUTE_DURING_GENERATION = "mute_during_generation"
CONF_DAY_VOLUME = "day_volume"
CONF_NIGHT_VOLUME = "night_volume"
CONF_VOLUME_MODE = "volume_mode"
CONF_START_DELAY = "start_delay"
CONF_WAVE_SCALE = "wave_scale"

VOLUME_MODE_FIXED = "fixed"
VOLUME_MODE_DAY_NIGHT = "day_night"

DEFAULT_WAVE_COLOR = "#00ccff"
DEFAULT_VIDEO_WIDTH = 1024
DEFAULT_VIDEO_HEIGHT = 600
DEFAULT_WAVE_HEIGHT = 240
DEFAULT_START_DELAY = 2.0
DEFAULT_MUTE_DURING_GENERATION = True
DEFAULT_VOLUME_MODE = VOLUME_MODE_FIXED
DEFAULT_DAY_VOLUME = 0.5
DEFAULT_NIGHT_VOLUME = 0.2

ATTR_LAST_VIDEO_URL = "last_generated_video_url"
ATTR_LAST_VIDEO_PATH = "last_generated_video_path"
ATTR_TARGET_ENTITY = "target_screen_entity"

EVENT_VIDEO_GENERATED = f"{DOMAIN}_video_generated"

MEDIA_DIR = "dttsvg"
VIDEO_EXTENSION = "mp4"

SERVICE_SPEAK = "speak"