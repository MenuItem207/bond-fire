# Configuration System Integration - Summary

## What Was Updated

All timing constants and configuration values have been moved from hardcoded values to the centralized `config.yaml` file.

### Files Modified

#### 1. **config.yaml** (New)
- Central configuration file with all adjustable parameters
- Organized into logical sections: state_machine, prompts, celebration, audio, vision, debug
- Well-commented with explanations of each setting

#### 2. **src/bond_fire_vision/config.py** (New)
- Python module to load and parse `config.yaml`
- Type-safe configuration access via dataclasses
- Auto-discovery of config.yaml in standard locations
- Global `get_config()` function for easy access
- Support for `BOND_FIRE_CONFIG` environment variable override

#### 3. **src/bond_fire_vision/state_machine.py** (Updated)
- Now loads `PHONE_ENTRY_DWELL` and `PHONE_EXIT_DWELL` from config at initialization
- Removed hardcoded `PHONE_ENTRY_DWELL = 0.0` and `PHONE_EXIT_DWELL = 0.5`
- Values are set dynamically in `__init__()` from config

#### 4. **src/bond_fire_vision/local_prompts.py** (Updated)
- Now loads `normal_cooldown` and `phone_cooldown` from config at initialization
- Constructor parameter `prompt_cooldown` is now optional (uses config if not provided)
- Both cooldown values are loaded from config, with support for override parameter

#### 5. **src/bond_fire_vision/audio_manager.py** (Updated)
- Now loads `master_volume` from config if not provided as parameter
- Loads `audio_queue_size` from config instead of hardcoded 50
- Loads TTS `speech_rate` from config instead of hardcoded 150
- Constructor parameter `master_volume` is now optional

#### 6. **CONFIG.md** (New)
- Comprehensive documentation of all configuration options
- Explains what each setting does and default values
- Includes example configurations for common use cases
- Usage examples in code

#### 7. **pyproject.toml** (Updated)
- Added `pyyaml` dependency for YAML parsing

## Configuration Values Managed

| File             | Setting           | Previous        | Config      |
| ---------------- | ----------------- | --------------- | ----------- |
| state_machine.py | PHONE_ENTRY_DWELL | 0.0 (hardcoded) | config.yaml |
| state_machine.py | PHONE_EXIT_DWELL  | 0.5 (hardcoded) | config.yaml |
| local_prompts.py | normal_cooldown   | 8.0 (hardcoded) | config.yaml |
| local_prompts.py | phone_cooldown    | 2.0 (hardcoded) | config.yaml |
| audio_manager.py | master_volume     | 0.7 (hardcoded) | config.yaml |
| audio_manager.py | audio_queue_size  | 50 (hardcoded)  | config.yaml |
| audio_manager.py | tts.speech_rate   | 150 (hardcoded) | config.yaml |

## How to Use

### Basic Usage
1. Edit `vision/config.yaml` to adjust any timing or parameter
2. Code will automatically use new values on next restart
3. No code changes needed

### Example: Adjust Phone Exit Response Time
```yaml
state_machine:
  phone_exit_dwell: 1.0  # Changed from 0.5 to 1.0 seconds
```

### Example: Faster Prompts While Phone Is Detected
```yaml
prompts:
  phone_cooldown: 1.0  # Changed from 2.0 to 1.0
```

### Override via Environment Variable
```bash
export BOND_FIRE_CONFIG=~/.config/bond-fire/config.yaml
python -m bond_fire_vision.cli --video 0
```

## Testing

All updated modules have been tested and verified to load configuration correctly:

✅ Config system loads without errors
✅ StateMachine initializes with config values
✅ LocalPromptGenerator initializes with config values
✅ AudioManager initializes with config values
✅ Default values match previous hardcoded values

## Backward Compatibility

- All default values in `config.yaml` match the previous hardcoded values
- Existing scripts continue to work without modification
- Command-line arguments still override config values where applicable
