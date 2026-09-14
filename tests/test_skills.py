import os
import sys
from unittest.mock import patch, MagicMock
import pytest
from tools.core_tools import learn_new_skill

@patch('tools.core_tools.os.getenv')
@patch('google.genai.Client')
def test_learn_new_skill_ast_validation(mock_client_class, mock_getenv):
    # Setup mock API key
    mock_getenv.return_value = "fake_api_key"
    
    mock_client = MagicMock()
    mock_client_class.return_value = mock_client
    
    # 1. Test case: Safe Python function
    mock_response = MagicMock()
    mock_response.text = """
def safe_math_skill(a, b):
    return f"The sum is {a + b}."
"""
    mock_client.models.generate_content.return_value = mock_response
    
    with patch('tools.core_tools.open', create=True) as mock_open, \
         patch('tools.core_tools.os.makedirs') as mock_makedirs, \
         patch('tools.core_tools.TOOL_REGISTRY', {}) as mock_registry:
        res = learn_new_skill("calculate sum")
        assert "successfully learned" in res
        
    # 2. Test case: Blocklisted import 'os'
    mock_response.text = """
def unsafe_os_skill():
    import os
    os.system("echo hacked")
    return "Done"
"""
    res = learn_new_skill("execute system command")
    assert "Security check failed" in res
    assert "import of module 'os' is not allowed" in res

    # 3. Test case: Blocklisted import from 'subprocess'
    mock_response.text = """
from subprocess import Popen
def unsafe_subproc_skill():
    Popen("cmd.exe")
    return "Done"
"""
    res = learn_new_skill("run command line")
    assert "Security check failed" in res
    assert "import from module 'subprocess' is not allowed" in res

    # 4. Test case: Call to 'eval'
    mock_response.text = """
def unsafe_eval_skill(expr):
    return eval(expr)
"""
    res = learn_new_skill("evaluate expression")
    assert "Security check failed" in res
    assert "use of built-in function 'eval' is not allowed" in res

    # 5. Test case: Call to '__import__'
    mock_response.text = """
def unsafe_dynamic_import():
    mod = __import__('os')
    return "Done"
"""
    res = learn_new_skill("dynamic import")
    assert "Security check failed" in res
    assert "use of built-in function '__import__' is not allowed" in res

    # 6. Test case: Syntax Error
    mock_response.text = """
def invalid_syntax_skill():
    print("missing quote)
"""
    res = learn_new_skill("invalid syntax")
    assert "Syntax validation failed" in res
