import llm_engine
from llm_engine import USER_NAME
import voice_engine
import stt_engine
import shared
import cron_engine
import security_engine
import study_mentor
import briefing_engine
import threading

def _get_dynamic_greeting(user_name):
    from datetime import datetime
    import random
    
    hour = datetime.now().hour
    title = random.choice([f"Master {user_name}", "sir"])
    
    if 1 <= hour < 5:
        return random.choice([
            f"Working the graveyard shift, I see. What can I do for you at this hour, {title}?",
            f"Unable to sleep, {title}? I am here to assist.",
            f"A very early start, {title}. Systems are nominal.",
            f"The world sleeps, but we do not, {title}. How may I help?",
            f"Burning the midnight oil, {title}? Tell me what you need.",
            f"At this hour, {title}? You are either very dedicated or very restless. Either way, I am here.",
        ])
    elif 5 <= hour < 8:
        return random.choice([
            f"You're up quite early today, {title}. How may I help you start your day?",
            f"Good morning, {title}. The sun is barely up, but I am ready.",
            f"A productive morning awaits, {title}. How shall we begin?",
            f"Early bird gets the worm, {title}. What shall we tackle first?",
            f"Dawn patrol reporting for duty, {title}. What is on your mind?",
            f"Rise and shine, {title}. I have been waiting. How can I assist?",
        ])
    elif 8 <= hour < 12:
        return random.choice([
            f"Good morning, {title}. Online and ready.",
            f"Morning, {title}. All systems running smoothly.",
            f"Good morning, {title}. How can I assist you today?",
            f"Welcome back, {title}. What is first on today's agenda?",
            f"Good morning, {title}. I trust you are well. What do you need?",
            f"Ready for action, {title}. Just say the word.",
        ])
    elif 12 <= hour < 17:
        return random.choice([
            f"Good afternoon, {title}. How may I assist?",
            f"Good afternoon, {title}. I am awaiting your command.",
            f"The day continues, {title}. What is next on our agenda?",
            f"Afternoon, {title}. What can I do for you?",
            f"At your service this afternoon, {title}. What do you need?",
            f"Good afternoon, {title}. Shall we get something done?",
        ])
    elif 17 <= hour < 22:
        return random.choice([
            f"Good evening, {title}. System is online.",
            f"Good evening, {title}. How may I be of service tonight?",
            f"Evening, {title}. Standing by for your command.",
            f"Good evening, {title}. What brings you to me at this hour?",
            f"The evening is young, {title}. What shall we accomplish?",
            f"Good evening, {title}. I am here whenever you need me.",
        ])
    else:
        return random.choice([
            f"Working late today, {title}? I am at your service.",
            f"It is getting late, {title}. How can I assist?",
            f"The night is quiet, {title}. I am online and ready.",
            f"Still at it, {title}? Admirable dedication. How may I help?",
            f"Late night session, {title}. Tell me what you need.",
            f"Most people are asleep by now, {title}. But not us. What do you need?",
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

    is_active_mode = False
    _has_given_briefing = False  # Only deliver full briefing on first wake

    while True:
        try:
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
                    voice_engine.speak(greeting)
            
            # 2. Command listening phase: Capture the actual command
            shared.push_state("listening")
            user_input = stt_engine.listen_for_command()
            
            if not user_input.strip():
                # In active mode, if he hears nothing, just loop back and keep listening
                continue

            shared.push_log(user_input, "User")
            shared.push_caption(user_input)

            ui_lower = user_input.lower()

            # -- PROTOCOL OMEGA (Study Mentor) --
            omega_deactivate = ['disable protocol omega', 'stop study mode', 'end protocol omega',
                                'deactivate omega', 'stop omega', 'end study mode',
                                'disable omega', 'cancel omega', 'omega off', 'stop focus mode']
            omega_activate = ['begin protocol omega', 'protocol omega', 'start study mode',
                              'study mode', 'study mod', 'focus mode', 'activate omega', 'omega protocol',
                              'start protocol omega', 'enable study mode']
            
            # Check DEACTIVATE first (because "stop study mode" contains "study mode")
            if any(phrase in ui_lower for phrase in omega_deactivate):
                if study_mentor.is_active():
                    result = study_mentor.deactivate()
                    shared.push_state("speaking")
                    voice_engine.speak(f"Protocol Omega disengaged. Well done on your study session, Master {USER_NAME}. You've earned a break.")
                    shared.push_caption("")
                else:
                    shared.push_state("speaking")
                    voice_engine.speak("Protocol Omega is not currently active, sir.")
                    shared.push_caption("")
                continue

            if any(phrase in ui_lower for phrase in omega_activate):
                if not study_mentor.is_active():
                    result = study_mentor.activate()
                    shared.push_state("speaking")
                    voice_engine.speak(f"Protocol Omega engaged, Master {USER_NAME}. I am now monitoring your focus. Distracting applications will be detected and dealt with. Your webcam is active. Do not test me, sir.")
                    shared.push_caption("")
                else:
                    shared.push_state("speaking")
                    voice_engine.speak("Protocol Omega is already active, sir. I am watching.")
                    shared.push_caption("")
                continue

            # Dismissal logic
            if any(phrase in ui_lower for phrase in ['go to sleep', 'standby', 'dismissed', 'rest now', 'sleep alfred', 'sleep', 'stand down', 'dismiss', 'stand by', 'go to sleep alfred']):
                # If Protocol Omega is active, deactivate it too
                if study_mentor.is_active():
                    study_mentor.deactivate()
                is_active_mode = False
                shared.alfred_awake = False
                shared.push_log("Entering sleep mode.", "System")
                shared.push_state("speaking")
                import random as _rng
                _sleep_lines = [
                    "Standing by, sir.",
                    f"Very well, Master {USER_NAME}. I will be here when you need me.",
                    "Going quiet. Wake me when you are ready.",
                    "Understood. Entering standby mode.",
                    f"Rest well, {_rng.choice(['sir', f'Master {USER_NAME}'])}. I will keep watch.",
                    "Stepping back, sir. Just say the word when you need me again.",
                    "Copy that. Going silent.",
                ]
                voice_engine.speak(_rng.choice(_sleep_lines))
                shared.push_caption("")
                continue

            if any(phrase in ui_lower for phrase in ['exit completely', 'shut down the system', 'kill protocol', 'exit', 'quit', 'goodbye', 'stop', 'shutdown']):
                # The user wants to exit completely
                shared.push_log("Shutting down the application.", "System")
                shared.push_state("speaking")
                import random as _rng2
                _shutdown_lines = [
                    f"Very well, Master {USER_NAME}. Shutting down.",
                    f"Understood, sir. It was a pleasure. Powering off.",
                    f"Goodbye, Master {USER_NAME}. Until next time.",
                    f"Signing off, sir. Take care of yourself.",
                    f"As you wish, {_rng2.choice(['sir', f'Master {USER_NAME}'])}. Going offline.",
                    f"Acknowledged. Shutting all systems down. Goodbye, sir.",
                    f"Until we meet again, Master {USER_NAME}. Goodnight.",
                ]
                voice_engine.speak(_rng2.choice(_shutdown_lines))
                import os
                os._exit(0)

            # 3. Get the response from Llama (The Brain)
            shared.push_state("processing")
            alfred_text = llm_engine.generate_response(user_input)
            
            if alfred_text == "[IGNORE]":
                shared.push_state("listening")
                continue

            # 4. Generate the audio and speak it (The Voice)
            shared.push_log(alfred_text, "Alfred")
            shared.push_caption(alfred_text)
            shared.push_state("speaking")
            
            # Interrupt system: monitor raw mic volume while speaking
            _was_interrupted = [False]
            
            def _speak_and_wait():
                voice_engine.speak(alfred_text)
            
            def _monitor_mic_for_interrupt():
                """Monitor raw mic audio levels — if user speaks, stop Alfred."""
                import pyaudio
                import struct
                import time
                
                # Wait for playback to actually begin
                for _ in range(50):
                    if voice_engine.is_speaking():
                        break
                    time.sleep(0.1)
                
                if not voice_engine.is_speaking():
                    return
                
                try:
                    pa = pyaudio.PyAudio()
                    
                    # Get the default input device's actual settings
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
                    
                    print(f"[Interrupt monitor] Mic: {dev_info['name']}, {channels}ch, {rate}Hz")
                    
                    # First, measure Alfred's own speaker bleed for 0.5s to set baseline
                    baseline_samples = []
                    for _ in range(8):
                        if not voice_engine.is_speaking():
                            break
                        data = stream.read(chunk, exception_on_overflow=False)
                        samples = struct.unpack(f'<{len(data)//2}h', data)
                        rms = (sum(s*s for s in samples) / len(samples)) ** 0.5
                        baseline_samples.append(rms)
                    
                    # Interrupt threshold = 4x the speaker bleed baseline, with a high minimum
                    baseline = max(baseline_samples) if baseline_samples else 200
                    threshold = max(baseline * 4.0, 16000)
                    print(f"[Interrupt monitor] Baseline: {baseline:.0f}, Threshold: {threshold:.0f}")
                    
                    # Now monitor continuously
                    while voice_engine.is_speaking():
                        data = stream.read(chunk, exception_on_overflow=False)
                        samples = struct.unpack(f'<{len(data)//2}h', data)
                        rms = (sum(s*s for s in samples) / len(samples)) ** 0.5
                        
                        if rms > threshold:
                            print(f"\n[Interrupt!] Voice spike detected (level: {rms:.0f}, threshold: {threshold:.0f})")
                            voice_engine.stop_speaking()
                            _was_interrupted[0] = True
                            break
                    
                    stream.stop_stream()
                    stream.close()
                    pa.terminate()
                except Exception as e:
                    print(f"[Interrupt monitor error]: {e}")
            
            speak_thread = threading.Thread(target=_speak_and_wait, daemon=True)
            monitor_thread = threading.Thread(target=_monitor_mic_for_interrupt, daemon=True)
            
            speak_thread.start()
            monitor_thread.start()
            speak_thread.join()
            
            # Clear caption
            shared.push_caption("")
            
            # If interrupted, immediately listen for the user's new command
            if _was_interrupted[0]:
                shared.push_log("(interrupted)", "System")
                shared.push_state("listening")
                print("[System] Alfred was interrupted. Listening for new command...")
                # Fall through — the loop will continue and listen for their command

        except KeyboardInterrupt:
            shared.push_log("Shutting down by KeyboardInterrupt.", "System")
            voice_engine.speak(f"Goodbye, Master {USER_NAME}.")
            import os
            os._exit(0)

        except Exception as e:
            print(f"\n[Error]: {e}")

if __name__ == "__main__":
    main_loop()
