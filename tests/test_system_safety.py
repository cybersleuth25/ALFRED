import os
import pytest
from unittest.mock import patch, MagicMock
from tools.core_tools import launch_application, play_music

def test_launch_application_os_startfile():
    # Mock os.startfile
    with patch('tools.core_tools.os.startfile') as mock_startfile:
        res = launch_application("notepad")
        assert "Launch signal sent" in res
        mock_startfile.assert_called_once_with("notepad")

def test_play_music_os_startfile():
    # Mock os.startfile, requests.post, requests.get and env keys
    with patch('tools.core_tools.os.startfile') as mock_startfile, \
         patch('tools.core_tools.requests.post') as mock_post, \
         patch('tools.core_tools.requests.get') as mock_get, \
         patch('tools.core_tools.os.getenv') as mock_getenv:
         
         mock_getenv.side_effect = lambda key, default=None: "fake_token" if "SPOTIFY" in key else default
         
         # Mock post for token retrieval
         mock_token_resp = MagicMock()
         mock_token_resp.json.return_value = {"access_token": "fake_token"}
         mock_token_resp.raise_for_status = MagicMock()
         mock_post.return_value = mock_token_resp
         
         # Mock search results
         mock_search_resp = MagicMock()
         mock_search_resp.json.return_value = {
             "tracks": {
                 "items": [
                     {
                         "uri": "spotify:track:123",
                         "name": "Believer",
                         "artists": [{"name": "Imagine Dragons"}]
                     }
                 ]
             }
         }
         mock_search_resp.raise_for_status = MagicMock()
         mock_get.return_value = mock_search_resp
         
         res = play_music("believer")
         assert "Now playing: Believer" in res
         mock_startfile.assert_called_once_with("spotify:track:123")
