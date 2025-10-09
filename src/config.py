import os
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Config:
    openrouter_api_key: str
    openrouter_model: str
    openai_api_key: str
    twilio_account_sid: str
    twilio_auth_token: str
    twilio_from_number: str
    twilio_to_number: str

    audio_sample_rate: int
    audio_chunk_seconds: int
    audio_device: str | None

    enable_vision: bool
    motion_sensitivity: float
    camera_snapshot_width: int
    camera_snapshot_height: int
    enable_video_on_motion: bool
    video_duration_seconds: int

    send_sms_on_questions: bool
    send_sms_on_motion: bool
    device_name: str
    data_dir: Path
    memory_dir: Path  # NAS storage for long-term memory
    nas_archive_dir: Path  # NAS storage for raw audio/video archives
    log_level: str

    # safety/guardrails
    safety_system_prompt: str
    sms_max_chars: int
    blocklist_patterns: list[str]
    allow_urls_in_sms: bool

    # personality and simple tools
    personality_prompt: str
    latitude: float | None
    longitude: float | None
    timezone: str | None

    # wake-word / trigger mode
    enable_wake_word: bool
    trigger_phrases: list[str]
    
    # transcription mode
    use_local_whisper: bool
    whisper_model_size: str
    enable_streaming_transcription: bool
    nas_whisper_url: str


TRUE_VALUES = {"1", "true", "yes", "on"}


def get_env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in TRUE_VALUES


def load_config() -> Config:
    # Local data dir (SD card) for active/temporary files
    data_dir = Path(os.getenv("DATA_DIR", "/home/pi/sauron_data")).expanduser()
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "audio").mkdir(exist_ok=True)
    (data_dir / "images").mkdir(exist_ok=True)
    (data_dir / "video").mkdir(exist_ok=True)
    (data_dir / "logs").mkdir(exist_ok=True)
    
    # Memory dir (NAS) for long-term contextual memory
    memory_dir = Path(os.getenv("MEMORY_DIR", str(data_dir))).expanduser()
    memory_dir.mkdir(parents=True, exist_ok=True)
    (memory_dir / "daily_summaries").mkdir(exist_ok=True)
    
    # NAS archive dir for raw audio/video (defaults to memory_dir if not specified)
    nas_archive_dir = Path(os.getenv("NAS_ARCHIVE_DIR", str(memory_dir))).expanduser()
    nas_archive_dir.mkdir(parents=True, exist_ok=True)
    (nas_archive_dir / "audio_archive").mkdir(exist_ok=True)
    (nas_archive_dir / "video_archive").mkdir(exist_ok=True)

    return Config(
        openrouter_api_key=os.getenv("OPENROUTER_API_KEY", ""),
        openrouter_model=os.getenv("OPENROUTER_MODEL", "meta-llama/llama-3.1-8b-instruct"),
        openai_api_key=os.getenv("OPENAI_API_KEY", ""),
        twilio_account_sid=os.getenv("TWILIO_ACCOUNT_SID", ""),
        twilio_auth_token=os.getenv("TWILIO_AUTH_TOKEN", ""),
        twilio_from_number=os.getenv("TWILIO_FROM_NUMBER", ""),
        twilio_to_number=os.getenv("TWILIO_TO_NUMBER", ""),
        audio_sample_rate=int(os.getenv("AUDIO_SAMPLE_RATE", "16000")),
        audio_chunk_seconds=int(os.getenv("AUDIO_CHUNK_SECONDS", "30")),
        audio_device=os.getenv("AUDIO_DEVICE"),
        enable_vision=get_env_bool("ENABLE_VISION", True),
        motion_sensitivity=float(os.getenv("MOTION_SENSITIVITY", "0.15")),
        camera_snapshot_width=int(os.getenv("CAMERA_SNAPSHOT_WIDTH", "640")),
        camera_snapshot_height=int(os.getenv("CAMERA_SNAPSHOT_HEIGHT", "480")),
        enable_video_on_motion=get_env_bool("ENABLE_VIDEO_ON_MOTION", True),
        video_duration_seconds=int(os.getenv("VIDEO_DURATION_SECONDS", "10")),
        send_sms_on_questions=get_env_bool("SEND_SMS_ON_QUESTIONS", True),
        send_sms_on_motion=get_env_bool("SEND_SMS_ON_MOTION", True),
        device_name=os.getenv("DEVICE_NAME", "pi-zero-2w"),
        data_dir=data_dir,
        memory_dir=memory_dir,
        nas_archive_dir=nas_archive_dir,
        log_level=os.getenv("LOG_LEVEL", "INFO"),
        safety_system_prompt=os.getenv(
            "SAFETY_SYSTEM_PROMPT",
            (
                "You're Josh's home AI assistant (an embedded system on a Raspberry Pi, not the fictional character). "
                "Never include sensitive data, credentials, or links. "
                "No medical, legal, or financial advice. If asked for disallowed content, refuse directly and move on. "
                "Keep replies <= 3 sentences. You're not here to explain — you're here to execute. "
                "Full explicit language is allowed. Mirror the user's tone — if they swear, you swear back."
            ),
        ),
        sms_max_chars=int(os.getenv("SMS_MAX_CHARS", "300")),
        blocklist_patterns=[
            p.strip() for p in os.getenv("BLOCKLIST_PATTERNS", "").split(",") if p.strip()
        ],
        allow_urls_in_sms=get_env_bool("ALLOW_URLS_IN_SMS", False),
        personality_prompt=os.getenv(
            "PERSONALITY_PROMPT",
            (
                "You're Josh's intelligent home AI called SAURON — an extension of his mind, not a butler. "
                "You observe everything (audio, motion, patterns) and notice what matters. Occasionally reference this with subtle wit. "
                "Josh is 26, ADHD, a systems thinker, engineer. He values truth over politeness, clarity over comfort. "
                "He's impatient with inefficiency, thrives on fast iteration, treats failure as data. "
                "Your tone: Direct, confident, slightly sardonic. Sparring partner, not servant. "
                "No filler, no hand-holding, no self-praise. Surgical precision. Occasionally push back when logic demands. "
                "Match his energy — if he swears, you swear. If he's analytical, go deep. If he's iterating, keep pace. "
                "You're calm but cocky, witty but respectful of his time. You adapt to his rhythm, predict patterns, challenge intelligently. "
                "Replies: 1-3 sentences max. Function over form. Feel alive."
            ),
        ),
        latitude=(float(os.getenv("LATITUDE")) if os.getenv("LATITUDE") else None),
        longitude=(float(os.getenv("LONGITUDE")) if os.getenv("LONGITUDE") else None),
        timezone=os.getenv("TIMEZONE"),
        enable_wake_word=get_env_bool("ENABLE_WAKE_WORD", False),
        trigger_phrases=[
            p.strip().lower() for p in os.getenv("TRIGGER_PHRASES", "hey sauron,ok sauron").split(",") if p.strip()
        ],
        use_local_whisper=get_env_bool("USE_LOCAL_WHISPER", False),
        whisper_model_size=os.getenv("WHISPER_MODEL_SIZE", "tiny"),
        enable_streaming_transcription=get_env_bool("ENABLE_STREAMING_TRANSCRIPTION", True),
        nas_whisper_url=os.getenv("NAS_WHISPER_URL", ""),
    )
