# Centralized command trigger registry for JARVIS/Alfred
# Used by alfred.py and llm_engine.py

FOCUS_DEACTIVATE = [
    'disable focus mode', 'stop study mode', 'end focus mode',
    'deactivate focus', 'stop focus', 'end study mode',
    'disable focus', 'cancel focus', 'focus off', 'stop focus mode',
    'disable protocol omega', 'end protocol omega', 'deactivate omega', 'stop omega'
]

FOCUS_ACTIVATE = [
    'begin focus mode', 'focus mode', 'start study mode',
    'study mode', 'study mod', 'activate focus', 'start focus mode',
    'enable study mode', 'enable focus mode',
    'begin protocol omega', 'protocol omega', 'activate omega'
]

LOCKDOWN_ACTIVATE = ['lockdown', 'lock it down', 'engage lockdown', 'hard lock', 'lock down']

LOCKDOWN_DEACTIVATE = ['unlock', 'release lockdown', 'disengage lockdown', 'soft mode', 'disable lockdown']

SENTRY_ACTIVATE = [
    'engage sentry mode', 'sentry mode', 'start sentry', 'activate sentry',
    'enable sentry', 'sentry on', 'watchdog mode', 'engage watchdog',
    'watch dog mode', 'watch dog mod', 'watchdog mod',
    'century mode', 'sentry mod', 'start sentry mode',
    'security mode', 'security mod', 'guard mode', 'surveillance mode', 'centri mod'
]

SENTRY_DEACTIVATE = [
    'disengage sentry mode', 'stop sentry', 'disable sentry',
    'deactivate sentry', 'sentry off', 'stop watchdog', 'disengage watchdog',
    'stop watch dog', 'stop security mode', 'stop guard mode',
    'disable watchdog', 'turn off sentry', 'stop surveillance'
]

STANDBY_PHRASES = [
    'go to sleep', 'standby', 'dismissed', 'rest now', 'sleep alfred',
    'sleep', 'stand down', 'dismiss', 'stand by', 'go to sleep alfred'
]

EXIT_PHRASES = [
    'exit completely', 'shut down the system', 'kill protocol', 'exit', 'quit',
    'goodbye', 'stop', 'shutdown'
]

# Triggers for llm_engine.py CommandRouter fast matches
LLM_START_FOCUS = ['i am studying', 'time to study', 'start focus mode', 'study mode']
LLM_STOP_FOCUS = ['stop studying', 'stop focus mode', 'deactivate focus mode']

# Hardcore Mode (instant kill — no 15s warning)
HARDCORE_ACTIVATE = [
    'hardcore mode', 'no mercy', 'zero tolerance', 'hard mode', 'hardcore',
    'enable hardcore', 'activate hardcore', 'no warnings'
]
HARDCORE_DEACTIVATE = [
    'soft mode', 'normal mode', 'gentle mode', 'disable hardcore',
    'deactivate hardcore', 'stop hardcore', 'warnings on'
]

# Persona switching
PERSONA_SWITCH = [
    'switch to friday', 'activate friday', 'become friday', 'be friday',
    'switch to jarvis', 'activate jarvis', 'become jarvis', 'be jarvis',
    'switch to alfred', 'go back to alfred', 'become alfred', 'be alfred',
    'change persona', 'switch persona'
]

# Persona Triggers
PERSONA_ALFRED = ['switch to alfred', 'activate alfred', 'protocol alfred']
PERSONA_FRIDAY = ['switch to friday', 'activate friday', 'protocol friday']
PERSONA_JARVIS = ['switch to jarvis', 'activate jarvis', 'protocol jarvis']
