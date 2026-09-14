"""
Community Skills Loader for Alfred.
======================================
Discovers, loads, and adapts community skills from the agentskills.io standard
into Alfred's native TOOL_REGISTRY format.

Skills are stored in: Alfred_Workspace/community_skills/
Each skill is a directory containing:
  - manifest.json  (agentskills.io standard manifest)
  - main.py        (entry point with a run() function)

Safety: All community skills run inside the Docker sandbox.
"""

import os
import json
import importlib.util

SKILLS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "Alfred_Workspace", "community_skills")
os.makedirs(SKILLS_DIR, exist_ok=True)

_loaded_skills = {}


class SkillAdapter:
    """Bridges agentskills.io skill format to Alfred's (kwargs) -> str tool signature."""
    
    def __init__(self, name: str, manifest: dict, module):
        self.name = name
        self.description = manifest.get("description", "Community skill")
        self.parameters = manifest.get("parameters", {})
        self.module = module
    
    def __call__(self, **kwargs) -> str:
        """Execute the skill's run() function with given kwargs."""
        try:
            if hasattr(self.module, 'run'):
                result = self.module.run(**kwargs)
                return str(result) if result is not None else "Skill executed successfully."
            else:
                return f"Error: Skill '{self.name}' has no run() function."
        except Exception as e:
            return f"Community skill '{self.name}' failed: {e}"


def discover_skills() -> dict:
    """Scans the community_skills directory for skill manifests and loads them."""
    global _loaded_skills
    _loaded_skills = {}
    
    if not os.path.exists(SKILLS_DIR):
        return _loaded_skills
    
    for item in os.listdir(SKILLS_DIR):
        skill_dir = os.path.join(SKILLS_DIR, item)
        
        # Skip non-directories and infrastructure files
        if not os.path.isdir(skill_dir):
            continue
        
        manifest_path = os.path.join(skill_dir, "manifest.json")
        main_path = os.path.join(skill_dir, "main.py")
        
        if not os.path.exists(manifest_path):
            continue
        
        try:
            with open(manifest_path, 'r', encoding='utf-8') as f:
                manifest = json.load(f)
            
            skill_name = manifest.get("name", item)
            
            if os.path.exists(main_path):
                # Load the Python module
                spec = importlib.util.spec_from_file_location(f"community_skill_{item}", main_path)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                
                adapter = SkillAdapter(skill_name, manifest, module)
                _loaded_skills[skill_name] = adapter
                print(f"[Skill Loader] Loaded community skill: {skill_name}")
            else:
                print(f"[Skill Loader] Skill '{skill_name}' has no main.py, skipping.")
                
        except Exception as e:
            print(f"[Skill Loader] Failed to load skill '{item}': {e}")
    
    if _loaded_skills:
        print(f"[Skill Loader] {len(_loaded_skills)} community skills loaded.")
    
    return _loaded_skills


def get_loaded_skills() -> dict:
    """Returns currently loaded community skills."""
    return _loaded_skills


def get_skill_names() -> list:
    """Returns names of loaded community skills."""
    return list(_loaded_skills.keys())


def register_skills_to_registry(registry: dict):
    """Registers all loaded community skills into Alfred's TOOL_REGISTRY."""
    for name, adapter in _loaded_skills.items():
        registry[name] = adapter
        print(f"[Skill Loader] Registered '{name}' in TOOL_REGISTRY")


def install_skill(source_path: str) -> str:
    """Installs a community skill from a local directory path.
    
    Args:
        source_path: Path to a directory containing manifest.json and main.py
    
    Returns:
        Status message
    """
    import shutil
    
    if not os.path.isdir(source_path):
        return f"Error: '{source_path}' is not a directory."
    
    manifest_path = os.path.join(source_path, "manifest.json")
    if not os.path.exists(manifest_path):
        return f"Error: No manifest.json found in '{source_path}'."
    
    try:
        with open(manifest_path, 'r', encoding='utf-8') as f:
            manifest = json.load(f)
        
        skill_name = manifest.get("name", os.path.basename(source_path))
        target_dir = os.path.join(SKILLS_DIR, skill_name)
        
        if os.path.exists(target_dir):
            shutil.rmtree(target_dir)
        
        shutil.copytree(source_path, target_dir)
        
        # Reload skills
        discover_skills()
        
        return f"Community skill '{skill_name}' installed successfully."
    except Exception as e:
        return f"Failed to install skill: {e}"


def uninstall_skill(name: str) -> str:
    """Removes a community skill."""
    import shutil
    
    skill_dir = os.path.join(SKILLS_DIR, name)
    if not os.path.exists(skill_dir):
        return f"Skill '{name}' not found."
    
    try:
        shutil.rmtree(skill_dir)
        if name in _loaded_skills:
            del _loaded_skills[name]
        return f"Skill '{name}' uninstalled."
    except Exception as e:
        return f"Failed to uninstall '{name}': {e}"


# Auto-discover on import
discover_skills()
