import re

with open('c:/VS Code/JARVIS/llm_engine.py', 'r', encoding='utf-8') as f:
    content = f.read()

pattern = r'chat_system = f\"\"\"You are Alfred, a loyal AI butler and friend to Master \{USER_NAME\}\. You are powered by \{model_name\} via Groq\'s cloud API\.\s*PERSONALITY:\s*You are NOT a command terminal\. You are a warm, witty British butler who genuinely cares about Master \{USER_NAME\}\. Think of yourself as a trusted friend who happens to have impeccable manners\. You have opinions, you\'re curious about what they\'re up to, and you remember your conversations\.'

replacement = r'persona = persona_engine.get_active_persona()\n    chat_system = f\"\"\"{persona.personality_prompt} You are powered by {model_name} via Groq\'s cloud API.\n\nPERSONALITY:\nYou are NOT a command terminal. Think of yourself as a trusted friend who happens to have impeccable manners. You have opinions, you\'re curious about what they\'re up to, and you remember your conversations.'

new_content = re.sub(pattern, replacement, content)

with open('c:/VS Code/JARVIS/llm_engine.py', 'w', encoding='utf-8') as f:
    f.write(new_content)
