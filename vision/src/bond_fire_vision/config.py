"""Configuration management for Bond Fire Vision system."""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import yaml


@dataclass
class StateConfig:
    """State machine configuration."""
    fire_entry_dwell: float
    phone_entry_dwell: float
    phone_exit_dwell: float
    frame_rate: int


@dataclass
class PromptsConfig:
    """Prompt generation configuration."""
    normal_cooldown: float
    phone_cooldown: float
    same_state_cooldown: float


@dataclass
class CelebrationConfig:
    """Celebration effect configuration."""
    duration_frames: int


@dataclass
class TTSConfig:
    """Text-to-speech configuration."""
    enabled: bool
    speech_rate: int
    voice_preference: list[str]


@dataclass
class AudioConfig:
    """Audio system configuration."""
    master_volume: float
    sfx_volume: float
    music_volume: float
    tts: TTSConfig
    audio_queue_size: int
    worker_thread_enabled: bool


@dataclass
class VisionConfig:
    """Vision detection configuration."""
    confidence_threshold: float
    person_class_id: int
    phone_class_id: int


@dataclass
class DebugConfig:
    """Debug configuration."""
    verbose_logging: bool
    log_prompts: bool
    disable_tts: bool


@dataclass
class Config:
    """Complete application configuration."""
    state_machine: StateConfig
    prompts: PromptsConfig
    celebration: CelebrationConfig
    audio: AudioConfig
    vision: VisionConfig
    debug: DebugConfig


def load_config(config_path: Optional[str] = None) -> Config:
    """
    Load configuration from YAML file.
    
    Args:
        config_path: Optional path to config.yaml. If not provided, searches in:
                    1. BOND_FIRE_CONFIG environment variable
                    2. vision/ directory (relative to script)
                    3. Current working directory
    
    Returns:
        Config: Loaded configuration object
    
    Raises:
        FileNotFoundError: If config file not found
        yaml.YAMLError: If config file is invalid YAML
    """
    if config_path is None:
        # Check environment variable
        if env_path := os.getenv("BOND_FIRE_CONFIG"):
            config_path = env_path
        else:
            # Search in standard locations
            vision_dir = Path(__file__).parent.parent.parent
            candidates = [
                vision_dir / "config.yaml",
                Path.cwd() / "config.yaml",
            ]
            
            for candidate in candidates:
                if candidate.exists():
                    config_path = str(candidate)
                    break
    
    if config_path is None:
        raise FileNotFoundError(
            "config.yaml not found. Set BOND_FIRE_CONFIG environment variable "
            "or place config.yaml in vision/ or current directory."
        )
    
    config_file = Path(config_path)
    if not config_file.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")
    
    with open(config_file) as f:
        data = yaml.safe_load(f)
    
    return _parse_config(data)


def _parse_config(data: dict) -> Config:
    """Parse raw config dictionary into Config dataclass."""
    return Config(
        state_machine=StateConfig(
            fire_entry_dwell=data["state_machine"].get("fire_entry_dwell", 0.0),
            phone_entry_dwell=data["state_machine"]["phone_entry_dwell"],
            phone_exit_dwell=data["state_machine"]["phone_exit_dwell"],
            frame_rate=data["state_machine"]["frame_rate"],
        ),
        prompts=PromptsConfig(
            normal_cooldown=data["prompts"]["normal_cooldown"],
            phone_cooldown=data["prompts"]["phone_cooldown"],
            same_state_cooldown=data["prompts"].get("same_state_cooldown", data["prompts"]["normal_cooldown"] * 1.5),
        ),
        celebration=CelebrationConfig(
            duration_frames=data["celebration"]["duration_frames"],
        ),
        audio=AudioConfig(
            master_volume=data["audio"]["master_volume"],
            sfx_volume=data["audio"]["sfx_volume"],
            music_volume=data["audio"]["music_volume"],
            tts=TTSConfig(
                enabled=data["audio"]["tts"]["enabled"],
                speech_rate=data["audio"]["tts"]["speech_rate"],
                voice_preference=data["audio"]["tts"]["voice_preference"],
            ),
            audio_queue_size=data["audio"]["audio_queue_size"],
            worker_thread_enabled=data["audio"]["worker_thread_enabled"],
        ),
        vision=VisionConfig(
            confidence_threshold=data["vision"]["confidence_threshold"],
            person_class_id=data["vision"]["person_class_id"],
            phone_class_id=data["vision"]["phone_class_id"],
        ),
        debug=DebugConfig(
            verbose_logging=data["debug"]["verbose_logging"],
            log_prompts=data["debug"]["log_prompts"],
            disable_tts=data["debug"]["disable_tts"],
        ),
    )


# Global config instance
_global_config: Optional[Config] = None


def get_config() -> Config:
    """Get the loaded configuration."""
    global _global_config
    if _global_config is None:
        _global_config = load_config()
    return _global_config


def reload_config(config_path: Optional[str] = None) -> Config:
    """Reload configuration from file."""
    global _global_config
    _global_config = load_config(config_path)
    return _global_config
