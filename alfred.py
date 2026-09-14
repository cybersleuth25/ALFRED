import llm_engine
from llm_engine import USER_NAME
import voice_engine
import stt_engine
import shared
import cron_engine
import security_engine
import vision_engine
import study_mentor
import briefing_engine
import persona_engine
import context_engine
import routine_engine
import tripwire_engine
import gesture_engine
import threading
import commands
import time
import random
import queue
import pyaudio
import json
import struct
import sys
from datetime import datetime

def _get_dynamic_greeting(user_name):
    hour = datetime.now().hour
    title = random.choice([f"Master {user_name}", "sir", user_name])
    
    if 1 <= hour < 5:
        return random.choice([
            f"Hey, you're still up? Couldn't sleep, {title}? I'm right here.",
            f"The quiet hours, huh? Just us and the glow of the screen, {title}. What's on your mind?",
            f"Late night vibes, {title}. Whatever you need, I've got you.",
            f"Most of the world's asleep right now, but hey, we don't follow rules. What's up?",
            f"Can't sleep either, {title}? Well, good thing I never do. How can I help?",
            f"Ah, another late night adventure. I'm here for it, {title}. What do you need?",
        ])
    elif 5 <= hour < 8:
        return random.choice([
            f"Oh wow, you're up early! Good on you, {title}. What are we doing today?",
            f"Rise and shine, {title}! The world's barely awake but look at you go.",
            f"Early start today, huh? I like the energy, {title}. What's the plan?",
            f"Morning, {title}! You beat the sunrise. I'm impressed. What do you need?",
            f"Hey, good morning! Coffee first, or do we jump straight into it, {title}?",
            f"The early hours are the best, {title}. Quiet, focused, just us. What's up?",
        ])
    elif 8 <= hour < 12:
        return random.choice([
            f"Good morning, {title}! Great to have you here. What are we working on?",
            f"Hey, morning! I've been waiting for you, {title}. Let's make today count.",
            f"Morning, {title}! Hope you're feeling good. What can I help with?",
            f"Good morning! Fresh day, fresh start, {title}. What do you need?",
            f"Hey there, {title}! Ready whenever you are. What's first today?",
            f"Morning, {title}! I've got everything ready on my end. Just say the word.",
        ])
    elif 12 <= hour < 17:
        return random.choice([
            f"Hey, {title}! Afternoon check-in. What are we up to?",
            f"Good afternoon, {title}! How's the day treating you so far?",
            f"Hey! Middle of the day energy, {title}. What do you need?",
            f"Afternoon, {title}! Need a hand with anything? I'm all yours.",
            f"Hey there! Half the day done already, {title}. Let's make the rest count.",
            f"Good afternoon, {title}! I'm here and ready. What's on your mind?",
        ])
    elif 17 <= hour < 22:
        return random.choice([
            f"Hey, {title}! Good evening. How was your day?",
            f"Evening, {title}! Winding down or gearing up? Either way, I'm here.",
            f"Hey there, {title}! The evening hours are all ours. What do you need?",
            f"Good evening, {title}! Nice to see you. What can I help with?",
            f"Hey! Evening vibes, {title}. Let me know what you need.",
            f"Evening, {title}! I hope today was good to you. What's up?",
        ])
    else:
        return random.choice([
            f"Hey, {title}! Still going strong, huh? I admire the dedication.",
            f"Night owl mode activated, {title}. I'm right here with you.",
            f"Hey, it's getting late, {title}. But I'm not judging. What do you need?",
            f"Late night, {title}? No worries, I don't sleep anyway. What's on your mind?",
            f"Still at it, {title}? You're something else. How can I help?",
            f"The night is ours, {title}. Whatever you need, just say the word.",
        ])

def main_loop():
    print("\n" + "="*50)
    print(" ALFRED IS ONLINE (VOICE MODE) ".center(50, "="))
    print("="*50)
    print("Say 'Alfred' to wake him up.")
    print("Say 'exit' or press Ctrl+C to end the session.\n")

    # Start the proactive background daemon
    cron_engine.start_cron_daemon()
    security_engine.start_security_daemon()
    context_engine.start_context_daemon()
    tripwire_engine.start_tripwire_daemon()
    routine_engine.init_default_routines()
    gesture_engine.init_default_gestures()

    # Pre-warm the LLM in background (eliminates cold-start on first command)
    if hasattr(llm_engine, 'prewarm_model'):
        threading.Thread(target=llm_engine.prewarm_model, daemon=True).start()

    # System online indicator (silent boot — speech only triggers when woken up)
    shared.push_state("idle")
    shared.push_log("All systems online. Standing by for wake word.", "System")

    is_active_mode = False
    _has_given_briefing = False  # Only deliver full briefing on first wake
    _empty_cmd_streak = 0        # Count consecutive empty/unheard commands

    while True:
        try:
            # ── HALTED CHECK: Stop toggle engaged from the UI ──
            if getattr(shared, 'alfred_halted', False):
                shared.push_state("idle")
                time.sleep(0.3)
                continue

            # If he's awake, UX state should reflect he is constantly listening
            shared.push_state("idle" if not is_active_mode else "listening")
            
            # 1. Background listening (Only run if he's currently asleep)
            if not is_active_mode:
                shared.alfred_awake = False
                wake_detected = stt_engine.listen_for_wake_word()
                if not wake_detected:
                    continue
                
                # He woke up! Enter active mode indefinitely
                is_active_mode = True
                shared.alfred_awake = True
                shared.push_state("speaking")
                
                # First wake: deliver full real intelligence briefing
                # Subsequent wakes: short greeting
                if not _has_given_briefing:
                    try:
                        briefing = briefing_engine.generate_startup_briefing(USER_NAME)
                        shared.push_log(briefing, "Alfred")
                        shared.push_caption(briefing)
                        voice_engine.speak(briefing)
                        shared.push_caption("")
                        _has_given_briefing = True
                    except Exception as e:
                        print(f"[Briefing Error] {e}")
                        greeting = _get_dynamic_greeting(USER_NAME)
                        voice_engine.speak(greeting)
                        _has_given_briefing = True
                else:
                    greeting = _get_dynamic_greeting(USER_NAME)
                    # Inject context summary if user was away
                    ctx_summary = context_engine.get_context_summary()
                    if ctx_summary:
                        greeting += f" {ctx_summary}"
                    voice_engine.speak(greeting)
            
            # 2. Command listening phase: Capture the actual command
            shared.push_state("listening")
            user_input = stt_engine.listen_for_command()
            
            if not user_input.strip():
                # In active mode, if he hears nothing, just loop back and keep listening
                _empty_cmd_streak += 1
                if _empty_cmd_streak >= 2:
                    _empty_cmd_streak = 0
                    shared.push_state("speaking")
                    _nudge = random.choice([
                        "I didn't quite catch that, sir. Could you repeat?",
                        "Pardon, sir? I didn't hear you clearly.",
                        "I'm listening, sir. Could you say that again?",
                    ])
                    voice_engine.speak(_nudge)
                    shared.push_caption("")
                continue

            _empty_cmd_streak = 0  # Reset on successful command

            shared.push_log(user_input, "User")
            shared.push_caption(user_input)

            ui_lower = user_input.lower()

            # -- FOCUS MODE (Study Mentor) --
            # Check DEACTIVATE first (because "stop study mode" contains "study mode")
            if any(phrase in ui_lower for phrase in commands.FOCUS_DEACTIVATE):
                if study_mentor.is_active():
                    result = study_mentor.deactivate(speak=False)
                    shared.push_state("speaking")
                    voice_engine.speak(result)
                    shared.push_caption("")
                else:
                    shared.push_state("speaking")
                    voice_engine.speak("Focus Mode is not currently active, sir.")
                    shared.push_caption("")
                continue

            if any(phrase in ui_lower for phrase in commands.FOCUS_ACTIVATE):
                if not study_mentor.is_active():
                    result = study_mentor.activate()
                    shared.push_state("speaking")
                    voice_engine.speak(f"Focus Mode engaged, Master {USER_NAME}. I am now monitoring your focus. Distracting applications will be detected and dealt with. Your webcam is active. Do not test me, sir.")
                    shared.push_caption("")
                else:
                    shared.push_state("speaking")
                    voice_engine.speak("Focus Mode is already active, sir. I am watching.")
                    shared.push_caption("")
                continue

            # -- LOCKDOWN MODE (only during Focus Mode) --
            if any(phrase in ui_lower for phrase in commands.LOCKDOWN_DEACTIVATE):
                if study_mentor.is_active() and shared.omega_lockdown:
                    result = study_mentor.disengage_lockdown()
                    shared.push_state("speaking")
                    shared.push_log(result, "Alfred")
                    voice_engine.speak(result)
                    shared.push_caption("")
                else:
                    shared.push_state("speaking")
                    voice_engine.speak("Lockdown is not currently active, sir.")
                    shared.push_caption("")
                continue

            if any(phrase in ui_lower for phrase in commands.LOCKDOWN_ACTIVATE):
                if study_mentor.is_active():
                    result = study_mentor.engage_lockdown()
                    shared.push_state("speaking")
                    shared.push_log(result, "Alfred")
                    voice_engine.speak(result)
                    shared.push_caption("")
                else:
                    shared.push_state("speaking")
                    voice_engine.speak("Lockdown requires Focus Mode to be active first, sir.")
                    shared.push_caption("")
                continue

            # -- HARDCORE MODE (Focus Mode sub-mode) --
            if any(phrase in ui_lower for phrase in commands.HARDCORE_DEACTIVATE):
                if study_mentor.is_active() and study_mentor.is_hardcore():
                    result = study_mentor.disengage_hardcore()
                    shared.push_state("speaking")
                    shared.push_log(result, "Alfred")
                    voice_engine.speak(result)
                    shared.push_caption("")
                else:
                    shared.push_state("speaking")
                    voice_engine.speak("Hardcore mode is not currently active, sir.")
                    shared.push_caption("")
                continue

            if any(phrase in ui_lower for phrase in commands.HARDCORE_ACTIVATE):
                if study_mentor.is_active():
                    result = study_mentor.engage_hardcore()
                    shared.push_state("speaking")
                    shared.push_log(result, "Alfred")
                    voice_engine.speak(result)
                    shared.push_caption("")
                else:
                    shared.push_state("speaking")
                    voice_engine.speak("Hardcore mode requires Focus Mode to be active first, sir.")
                    shared.push_caption("")
                continue

            # -- PERSONA SWITCHING --
            if any(phrase in ui_lower for phrase in commands.PERSONA_SWITCH):
                target = persona_engine.extract_persona_name(ui_lower)
                if target:
                    result = persona_engine.switch_persona(target)
                    persona = persona_engine.get_active_persona()
                    shared.push_state("speaking")
                    shared.push_log(result, "Alfred")
                    voice_engine.speak(f"Persona switched. I am now {persona.display_name}. At your service, {persona.honorific}.")
                    shared.push_caption("")
                else:
                    available = ", ".join(persona_engine.get_persona_names())
                    shared.push_state("speaking")
                    voice_engine.speak(f"Which persona would you like, {persona_engine.get_active_persona().honorific}? Available: {available}.")
                    shared.push_caption("")
                continue

            # -- SENTRY MODE (Vision Engine) --
            if any(phrase in ui_lower for phrase in commands.SENTRY_DEACTIVATE):
                if vision_engine.is_active():
                    vision_engine.stop_vision_daemon()
                    shared.push_state("speaking")
                    voice_engine.speak(f"Sentry Mode disengaged, sir. I have stopped monitoring the room.")
                    shared.push_caption("")
                else:
                    shared.push_state("speaking")
                    voice_engine.speak("Sentry Mode is not currently active, sir.")
                    shared.push_caption("")
                continue

            if any(phrase in ui_lower for phrase in commands.SENTRY_ACTIVATE):
                if not vision_engine.is_active():
                    vision_engine.start_vision_daemon()
                    shared.push_state("speaking")
                    voice_engine.speak(f"Sentry Mode engaged, Master {USER_NAME}. I am now watching the room. Any suspicious movement will be reported to you immediately.")
                    shared.push_caption("")
                else:
                    shared.push_state("speaking")
                    voice_engine.speak("Sentry Mode is already active, sir. I am watching.")
                    shared.push_caption("")
                continue

            # Dismissal logic
            if any(phrase in ui_lower for phrase in commands.STANDBY_PHRASES):
                # If Focus Mode is active, deactivate it too
                if study_mentor.is_active():
                    study_mentor.deactivate()
                # If Sentry Mode is active, deactivate it too
                if vision_engine.is_active():
                    vision_engine.stop_vision_daemon()
                is_active_mode = False
                shared.alfred_awake = False
                shared.push_log("Entering sleep mode.", "System")
                shared.push_state("speaking")
                _sleep_lines = [
                    "Standing by, sir.",
                    f"Very well, Master {USER_NAME}. I will be here when you need me.",
                    "Going quiet. Wake me when you are ready.",
                    "Understood. Entering standby mode.",
                    f"Rest well, {random.choice(['sir', f'Master {USER_NAME}'])}. I will keep watch.",
                    "Stepping back, sir. Just say the word when you need me again.",
                    "Copy that. Going silent.",
                ]
                voice_engine.speak(random.choice(_sleep_lines))
                shared.push_caption("")
                continue

            if any(phrase in ui_lower for phrase in commands.EXIT_PHRASES):
                # The user wants to exit completely
                shared.push_log("Shutting down the application.", "System")
                shared.push_state("speaking")
                _shutdown_lines = [
                    f"Very well, Master {USER_NAME}. Shutting down.",
                    f"Understood, sir. It was a pleasure. Powering off.",
                    f"Goodbye, Master {USER_NAME}. Until next time.",
                    f"Signing off, sir. Take care of yourself.",
                    f"As you wish, {random.choice(['sir', f'Master {USER_NAME}'])}. Going offline.",
                    f"Acknowledged. Shutting all systems down. Goodbye, sir.",
                    f"Until we meet again, Master {USER_NAME}. Goodnight.",
                ]
                voice_engine.speak(random.choice(_shutdown_lines))
                sys.exit(0)

            # 3. Get the response from Llama (The Brain)
            shared.push_state("processing")
            sentence_queue = queue.Queue()
            
            def _tts_callback(sentence):
                sentence_queue.put(sentence)
                
            alfred_text_container = [""]
            def _run_llm():
                try:
                    alfred_text_container[0] = llm_engine.generate_response(user_input, tts_callback=_tts_callback)
                except Exception as e:
                    print(e)
                sentence_queue.put(None) # EOF marker
                
            llm_thread = threading.Thread(target=_run_llm, daemon=True)
            llm_thread.start()
            
            # Wait for first chunk
            first_chunk = sentence_queue.get()
            
            if first_chunk is None:
                # LLM errored out without producing any output
                shared.push_state("listening")
                llm_thread.join()
                continue
            
            if first_chunk == "[IGNORE]":
                shared.push_state("listening")
                llm_thread.join()
                continue

            # 4. Generate the audio and speak it (The Voice) — STREAMING PIPELINE
            shared.push_caption(first_chunk)
            shared.push_state("speaking")
            
            # Smart interrupt system: Vosk detects wake-words/direct address mid-speech
            # and captures what the user said so they don't have to repeat themselves
            _was_interrupted = [False]
            _is_done_speaking = [False]
            _interrupted_text = [""]  # Captured speech during interruption
            
            def _speak_streamed():
                """Use the streaming TTS pipeline for true overlap between generation and playback."""
                voice_engine.speak_streamed(sentence_queue, first_chunk)
                _is_done_speaking[0] = True
                
            def _monitor_wake_word_for_interrupt():
                """Monitor mic using Vosk for wake-word/direct-address detection.
                
                Smart interrupt logic:
                - Wake words ("Alfred", "stop", "buddy") → immediate interrupt
                - Direct address (speech containing Alfred's name) → interrupt + capture text
                - The captured text is saved so the main loop can use it as the next command
                """
                # Wait for playback to actually begin
                for _ in range(50):
                    if voice_engine.is_speaking():
                        break
                    time.sleep(0.1)
                
                if not voice_engine.is_speaking():
                    return
                
                # Try Vosk-based interrupt (accurate, wake-word based)
                if stt_engine._vosk_available and stt_engine._vosk_model:
                    pa = None
                    stream = None
                    try:
                        from vosk import KaldiRecognizer
                        pa = pyaudio.PyAudio()
                        
                        stream = pa.open(
                            format=pyaudio.paInt16,
                            channels=1,
                            rate=stt_engine.VOSK_RATE,
                            input=True,
                            frames_per_buffer=stt_engine.VOSK_CHUNK,
                        )
                        
                        rec = KaldiRecognizer(stt_engine._vosk_model, stt_engine.VOSK_RATE)
                        rec.SetWords(False)
                        
                        print("[Interrupt monitor] Vosk smart detection active during speech")
                        
                        while not _is_done_speaking[0]:
                            if not voice_engine.is_speaking():
                                time.sleep(0.05)
                                continue
                            
                            data = stream.read(stt_engine.VOSK_CHUNK, exception_on_overflow=False)
                            
                            if rec.AcceptWaveform(data):
                                result = json.loads(rec.Result())
                                text = result.get("text", "").lower().strip()
                                if not text:
                                    continue
                                
                                # Check for direct address (wake words or interrupt words)
                                if any(word in text for word in stt_engine.INTERRUPT_SYNONYMS):
                                    print(f"\n[Interrupt!] Direct address detected: '{text}'")
                                    voice_engine.stop_speaking()
                                    _was_interrupted[0] = True
                                    # Capture the full text minus the wake word for use as next command
                                    remaining = text
                                    for word in stt_engine.INTERRUPT_SYNONYMS:
                                        remaining = remaining.replace(word, "").strip()
                                    if len(remaining.split()) >= 2:
                                        _interrupted_text[0] = remaining
                                    break
                            else:
                                partial = json.loads(rec.PartialResult())
                                partial_text = partial.get("partial", "").lower().strip()
                                if partial_text and any(word in partial_text for word in stt_engine.INTERRUPT_SYNONYMS):
                                    print(f"\n[Interrupt!] Wake word detected (partial): '{partial_text}'")
                                    voice_engine.stop_speaking()
                                    _was_interrupted[0] = True
                                    break
                    except Exception as e:
                        print(f"[Interrupt monitor error]: {e}")
                    finally:
                        if stream:
                            try:
                                stream.stop_stream()
                                stream.close()
                            except Exception:
                                pass
                        if pa:
                            try:
                                pa.terminate()
                            except Exception:
                                pass
                else:
                    # Fallback: volume-based interrupt if Vosk is unavailable
                    # Thresholds lowered for more natural interruption
                    pa = None
                    stream = None
                    try:
                        pa = pyaudio.PyAudio()
                        dev_info = pa.get_default_input_device_info()
                        channels = min(int(dev_info['maxInputChannels']), 2)
                        rate = int(dev_info['defaultSampleRate'])
                        chunk = 2048
                        
                        stream = pa.open(
                            format=pyaudio.paInt16,
                            channels=channels,
                            rate=rate,
                            input=True,
                            frames_per_buffer=chunk
                        )
                        
                        print(f"[Interrupt monitor] Volume-based fallback active")
                        
                        baseline_samples = []
                        for _ in range(8):
                            if not voice_engine.is_speaking(): break
                            data = stream.read(chunk, exception_on_overflow=False)
                            samples = struct.unpack(f'<{len(data)//2}h', data)
                            rms = (sum(s*s for s in samples) / len(samples)) ** 0.5
                            baseline_samples.append(rms)
                        
                        baseline = max(baseline_samples) if baseline_samples else 200
                        threshold = max(baseline * 2.5, 6000)  # Lowered: was 4.0 / 16000
                        
                        while not _is_done_speaking[0]:
                            if not voice_engine.is_speaking():
                                time.sleep(0.05)
                                continue
                            data = stream.read(chunk, exception_on_overflow=False)
                            samples = struct.unpack(f'<{len(data)//2}h', data)
                            rms = (sum(s*s for s in samples) / len(samples)) ** 0.5
                            if rms > threshold:
                                print(f"\n[Interrupt!] Voice spike detected (level: {rms:.0f})")
                                voice_engine.stop_speaking()
                                _was_interrupted[0] = True
                                break
                    except Exception as e:
                        print(f"[Interrupt monitor error]: {e}")
                    finally:
                        if stream:
                            try:
                                stream.stop_stream()
                                stream.close()
                            except Exception:
                                pass
                        if pa:
                            try:
                                pa.terminate()
                            except Exception:
                                pass
            
            speak_thread = threading.Thread(target=_speak_streamed, daemon=True)
            monitor_thread = threading.Thread(target=_monitor_wake_word_for_interrupt, daemon=True)
            
            speak_thread.start()
            monitor_thread.start()
            speak_thread.join()
            llm_thread.join()
            
            # Finalize log
            shared.push_log(alfred_text_container[0], "Alfred")
            
            # Clear caption
            shared.push_caption("")
            
            # If interrupted, handle the transition intelligently
            if _was_interrupted[0]:
                shared.push_log("(interrupted)", "System")
                shared.push_state("listening")
                
                # If we captured speech during the interrupt, use it as the next command
                if _interrupted_text[0]:
                    captured = _interrupted_text[0]
                    print(f"[System] Alfred interrupted. Captured command: '{captured}'")
                    shared.push_log(captured, "User")
                    shared.push_caption(captured)
                    
                    # Process the captured command immediately
                    shared.push_state("processing")
                    sentence_queue_2 = queue.Queue()
                    
                    def _tts_callback_2(sentence):
                        sentence_queue_2.put(sentence)
                    
                    alfred_text_2 = [""]
                    def _run_llm_2():
                        try:
                            alfred_text_2[0] = llm_engine.generate_response(captured, tts_callback=_tts_callback_2)
                        except Exception as e:
                            print(e)
                        sentence_queue_2.put(None)
                    
                    llm_thread_2 = threading.Thread(target=_run_llm_2, daemon=True)
                    llm_thread_2.start()
                    
                    first_chunk_2 = sentence_queue_2.get()
                    if first_chunk_2 and first_chunk_2 != "[IGNORE]":
                        shared.push_caption(first_chunk_2)
                        shared.push_state("speaking")
                        voice_engine.speak_streamed(sentence_queue_2, first_chunk_2)
                    
                    llm_thread_2.join()
                    shared.push_log(alfred_text_2[0], "Alfred")
                    shared.push_caption("")
                else:
                    print("[System] Alfred was interrupted. Listening for new command...")
                    # Fall through — the loop will continue and listen for their command

        except KeyboardInterrupt:
            shared.push_log("Shutting down by KeyboardInterrupt.", "System")
            voice_engine.speak(f"Goodbye, Master {USER_NAME}.")
            sys.exit(0)

        except Exception as e:
            print(f"\n[Error]: {e}")

if __name__ == "__main__":
    main_loop()
