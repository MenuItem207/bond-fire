#!/usr/bin/env python
"""Verify configuration integration across modules."""

import sys
import warnings
warnings.filterwarnings("ignore")

def test_integration():
    """Run integration tests."""
    print("\n" + "=" * 70)
    print("CONFIGURATION INTEGRATION VERIFICATION")
    print("=" * 70)

    # Test 1: Config Loading
    print("\n[TEST 1] Config Loading")
    try:
        from bond_fire_vision.config import get_config
        cfg = get_config()
        print("✅ PASS: Config loaded successfully")
    except Exception as e:
        print(f"❌ FAIL: {e}")
        return False

    # Test 2: State Machine Integration
    print("\n[TEST 2] State Machine Integration")
    try:
        from bond_fire_vision.state_machine import StateMachine
        sm = StateMachine()
        
        expected_entry = cfg.state_machine.fire_entry_dwell
        actual_entry = sm.FIRE_ENTRY_DWELL
        entry_ok = actual_entry == expected_entry

        print(f"  FIRE_ENTRY_DWELL: {actual_entry} (expected {expected_entry}) {'✓' if entry_ok else '✗'}")

        if entry_ok:
            print("✅ PASS: State machine values match config")
        else:
            print("❌ FAIL: State machine values don't match config")
            return False
    except Exception as e:
        print(f"❌ FAIL: {e}")
        return False

    # Test 3: LocalPromptGenerator Integration
    print("\n[TEST 3] LocalPromptGenerator Integration")
    try:
        from bond_fire_vision.local_prompts import LocalPromptGenerator
        gen = LocalPromptGenerator()
        
        expected_normal = cfg.prompts.normal_cooldown
        actual_normal = gen._prompt_cooldown
        normal_ok = actual_normal == expected_normal

        print(f"  normal_cooldown: {actual_normal}s (expected {expected_normal}s) {'✓' if normal_ok else '✗'}")

        if normal_ok:
            print("✅ PASS: Prompt cooldowns match config")
        else:
            print("❌ FAIL: Prompt cooldowns don't match config")
            return False
    except Exception as e:
        print(f"❌ FAIL: {e}")
        return False

    # Test 4: AudioManager Integration
    print("\n[TEST 4] AudioManager Integration")
    try:
        from bond_fire_vision.audio_manager import AudioManager
        
        am = AudioManager(enabled=False)
        expected_volume = cfg.audio.master_volume
        actual_volume = am.master_volume
        
        volume_ok = actual_volume == expected_volume
        
        print(f"  master_volume: {actual_volume} (expected {expected_volume}) {'✓' if volume_ok else '✗'}")
        
        if volume_ok:
            print("✅ PASS: AudioManager volume matches config")
        else:
            print("❌ FAIL: AudioManager volume doesn't match config")
            return False
    except Exception as e:
        print(f"❌ FAIL: {e}")
        return False

    # Test 5: Import Verification
    print("\n[TEST 5] Config Import Verification")
    try:
        import inspect
        from bond_fire_vision import state_machine, local_prompts, audio_manager
        
        sm_source = inspect.getsource(state_machine)
        lp_source = inspect.getsource(local_prompts)
        am_source = inspect.getsource(audio_manager)
        
        sm_import = "from .config import get_config" in sm_source
        lp_import = "from .config import get_config" in lp_source
        am_import = "from .config import get_config" in am_source
        
        print(f"  state_machine.py imports config: {'✓' if sm_import else '✗'}")
        print(f"  local_prompts.py imports config: {'✓' if lp_import else '✗'}")
        print(f"  audio_manager.py imports config: {'✓' if am_import else '✗'}")
        
        if sm_import and lp_import and am_import:
            print("✅ PASS: All modules import config")
        else:
            print("❌ FAIL: Not all modules import config")
            return False
    except Exception as e:
        print(f"❌ FAIL: {e}")
        return False

    # Test 6: Config Values Summary
    print("\n[TEST 6] Configuration Values Summary")
    print(f"\nState Machine:")
    print(f"  fire_entry_dwell: {cfg.state_machine.fire_entry_dwell}s")
    print(f"  frame_rate: {cfg.state_machine.frame_rate} fps")
    
    print(f"\nPrompts:")
    print(f"  normal_cooldown: {cfg.prompts.normal_cooldown}s")
    
    print(f"\nAudio:")
    print(f"  master_volume: {cfg.audio.master_volume}")
    print(f"  audio_queue_size: {cfg.audio.audio_queue_size}")
    print(f"  TTS enabled: {cfg.audio.tts.enabled}")
    print(f"  TTS speech_rate: {cfg.audio.tts.speech_rate} WPM")
    print(f"  TTS voice_preference: {cfg.audio.tts.voice_preference}")
    
    print(f"\nVision:")
    print(f"  confidence_threshold: {cfg.vision.confidence_threshold}")
    print(f"  person_class_id: {cfg.vision.person_class_id}")
    
    print(f"\nDebug:")
    print(f"  verbose_logging: {cfg.debug.verbose_logging}")
    print(f"  log_prompts: {cfg.debug.log_prompts}")
    print(f"  disable_tts: {cfg.debug.disable_tts}")
    
    print("✅ PASS: All config values readable")
    
    return True


if __name__ == "__main__":
    success = test_integration()
    
    print("\n" + "=" * 70)
    if success:
        print("✅ ALL TESTS PASSED - CONFIGURATION INTEGRATION VERIFIED")
    else:
        print("❌ SOME TESTS FAILED - CHECK INTEGRATION")
    print("=" * 70 + "\n")
    
    sys.exit(0 if success else 1)
