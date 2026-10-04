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
    'sleep', 'stand down', 'dismiss', 'stand by', 'go to sleep alfred',
    'so jao', 'so ja alfred', 'so ja jarvis', 'aaram karo', 'ruk jao', 'chup ho jao', 'chup raho'
]

EXIT_PHRASES = [
    'exit completely', 'shut down the system', 'kill protocol', 'exit', 'quit',
    'goodbye', 'stop', 'shutdown', 'band kar do', 'system band karo', 'alvida'
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
    # Friday triggers
    'switch to friday', 'switch back to friday', 'change to friday', 'activate friday',
    'become friday', 'be friday', 'load friday', 'bring up friday', 'protocol friday',
    'switch persona to friday', 'change persona to friday', 'switch voice to friday',
    'switch over to friday', 'go to friday', 'call friday',
    # Jarvis triggers
    'switch to jarvis', 'switch back to jarvis', 'change to jarvis', 'activate jarvis',
    'become jarvis', 'be jarvis', 'load jarvis', 'bring up jarvis', 'protocol jarvis',
    'switch persona to jarvis', 'change persona to jarvis', 'switch voice to jarvis',
    'switch over to jarvis', 'go to jarvis', 'call jarvis',
    # Alfred triggers
    'switch to alfred', 'switch back to alfred', 'go back to alfred', 'change to alfred',
    'activate alfred', 'become alfred', 'be alfred', 'load alfred', 'bring up alfred',
    'bring back alfred', 'protocol alfred', 'switch persona to alfred',
    'change persona to alfred', 'switch voice to alfred', 'switch over to alfred',
    'go to alfred', 'call alfred',
    # Generic switches & short options
    'change persona', 'switch persona', 'change voice', 'switch voice',
    'change personality', 'switch personality', 'choose persona', 'select persona',
    'persona friday', 'persona jarvis', 'persona alfred'
]

# Persona Direct Triggers
PERSONA_ALFRED = ['switch to alfred', 'activate alfred', 'protocol alfred', 'switch back to alfred']
PERSONA_FRIDAY = ['switch to friday', 'activate friday', 'protocol friday', 'switch back to friday']
PERSONA_JARVIS = ['switch to jarvis', 'activate jarvis', 'protocol jarvis', 'switch back to jarvis']

# Live Screen Co-Pilot Triggers (English, Hindi, Hinglish)
SCREEN_COPILOT_TRIGGERS = [
    'look at my screen', "look at what's on my screen", 'what is on my screen',
    "what's on my screen", 'inspect my screen', 'inspect the screen', 'check my screen',
    'read my screen', 'debug this screen', 'debug this code', 'debug the code on screen',
    'debug my code', 'explain this diagram', 'explain what is on my screen', 'screen copilot',
    'analyze my screen', 'examine my screen', 'what am i looking at', 'look at this error',
    'help me debug this', 'can you see my screen', 'check the error on screen',
    # Hindi & Hinglish triggers
    'screen dekho', 'meri screen dekho', 'screen pe kya hai', 'screen check karo',
    'mera code dekho', 'code dekho', 'ye code dekho', 'ye error dekho',
    'kya chal raha hai screen pe', 'screen read karo', 'screen par kya hai',
    'meri screen check kar', 'error dekh', 'debug karo', 'screen inspect karo'
]

# Media Playback Controls (English & Hinglish)
MEDIA_PLAY_PAUSE = [
    'pause music', 'resume music', 'pause song', 'resume song', 'music pause',
    'gana pause karo', 'gana bajao', 'gana roko', 'pause the music', 'resume the music',
    'pause track', 'resume track', 'music roko'
]
MEDIA_NEXT = [
    'next song', 'skip song', 'next track', 'skip track', 'agla gana', 'gana badlo',
    'change song', 'skip this song', 'next'
]
MEDIA_PREV = [
    'previous song', 'previous track', 'pichhla gana', 'last song', 'prev song'
]
MEDIA_MUTE = [
    'mute sound', 'mute audio', 'unmute sound', 'unmute audio', 'mute system',
    'awaz band karo', 'mute karo', 'unmute karo'
]

# Acoustic Sentry Ear Triggers
ACOUSTIC_SENTRY_ACTIVATE = [
    'activate acoustic sentry', 'enable acoustic sentry', 'start acoustic sentry',
    'acoustic sentry on', 'turn on acoustic sentry', 'listen for intrusions',
    'acoustic ear on', 'activate acoustic ear', 'enable acoustic ear'
]
ACOUSTIC_SENTRY_DEACTIVATE = [
    'deactivate acoustic sentry', 'disable acoustic sentry', 'stop acoustic sentry',
    'acoustic sentry off', 'turn off acoustic sentry', 'stop acoustic ear',
    'disable acoustic ear'
]

# Evening Executive Debrief Triggers
DEBRIEF_TRIGGERS = [
    'debrief my day', 'evening debrief', 'daily debrief', 'executive debrief',
    'give me my debrief', 'give me my evening debrief', 'end of day report',
    'summary of my day', 'how did my day go', 'run debrief', 'start evening debrief'
]

# Autonomous Developer Co-Pilot Triggers
GIT_STATUS_TRIGGERS = [
    'git status', 'check git', 'git diff', 'what changed in git',
    'git check karo', 'git status batao', 'git branch status', 'check repo',
    'check git status', 'repo status'
]

SECRET_SCAN_TRIGGERS = [
    'scan secrets', 'check for leaks', 'scan for secrets', 'scan api keys',
    'check leaked keys', 'leak check karo', 'secrets scan karo', 'security scan',
    'scan credentials', 'token leak check'
]

WORKSPACE_CLEAN_TRIGGERS = [
    'clean workspace', 'clean cache', 'clean dev workspace', 'free disk space',
    'cache saaf karo', 'cache clear karo', 'clear pycache', 'clean junk',
    'clean build cache'
]

MEETING_START_TRIGGERS = [
    'start meeting', 'start meeting mode', 'record meeting', 'record lecture',
    'meeting shuru karo', 'meeting chalu karo', 'begin meeting', 'meeting mode on',
    'take meeting notes', 'meeting note taker', 'lecture record karo'
]

MEETING_STOP_TRIGGERS = [
    'stop meeting', 'stop meeting mode', 'end meeting', 'finish meeting',
    'meeting khatam karo', 'meeting roko', 'meeting band karo', 'end recording',
    'stop recording meeting', 'stop lecture recording'
]

# Daily Chief of Staff & Executive Intelligence Triggers
CHIEF_OF_STAFF_TRIGGERS = [
    'chief of staff', 'chief of staff dossier', 'daily dossier', 'executive dossier',
    'morning dossier', 'give me my dossier', 'chief of staff briefing', 'chief briefing',
    'executive briefing', 'daily executive briefing'
]

AGENDA_TRIGGERS = [
    'agenda', 'what is on my agenda', "what's on my agenda", 'daily agenda',
    'what is my schedule', "what's my schedule", 'aaj ka schedule', 'aaj ka agenda',
    'check my calendar', 'check calendar', 'today schedule', 'what meetings do i have',
    'check schedule', 'schedule check karo'
]

EMAIL_INBOX_TRIGGERS = [
    'check emails', 'check my emails', 'check email', 'check my email',
    'triage inbox', 'inbox triage', 'check inbox', 'unread emails',
    'koi email aayi hai', 'email check karo', 'koi mail aayi hai',
    'important emails', 'urgent emails'
]

# Market Intelligence & Stock Prediction Triggers
STOCK_QUOTE_TRIGGERS = [
    'stock price', 'stock quote', 'share price', 'market price',
    'stock rate', 'price of stock', 'quote for', 'share rate',
    'stock check karo', 'share ka price', 'price check karo'
]

STOCK_FORECAST_TRIGGERS = [
    'stock prediction', 'stock forecast', 'predict stock', 'forecast stock',
    'chronos prediction', 'chronos forecast', 'predict share', 'forecast share',
    'share forecast', 'future price of', 'stock analysis', 'market prediction',
    'stock kaisa rahega', 'stock forecast karo', 'share predict karo'
]

# Facial OSINT & Reverse Face Search Triggers
REVERSE_FACE_SEARCH_TRIGGERS = [
    'reverse face search', 'face search', 'find person by photo', 'who is this person',
    'identify this face', 'face lookup', 'reverse image face', 'face match',
    'chehra pehchano', 'face search karo', 'find face', 'search this face',
    'faceseek', 'who is this in the camera', 'identify face in camera'
]




