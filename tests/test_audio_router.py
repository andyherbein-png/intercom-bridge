# tests/test_audio_router.py
import pytest
from unittest.mock import patch
from src.audio_router import AudioRouter

FAKE_DUMP = b"""
[{"type":"PipeWire:Interface:Node","props":{"node.name":"bluez_output.hfp","media.class":"Audio/Source"},"id":42},
 {"type":"PipeWire:Interface:Node","props":{"node.name":"alsa_input.xlr","media.class":"Audio/Source"},"id":10},
 {"type":"PipeWire:Interface:Node","props":{"node.name":"bluez_output.a2dp","media.class":"Audio/Sink"},"id":43}]
"""


@pytest.fixture
def router():
    return AudioRouter()


def test_reroute_for_hfp_links_correct_nodes(router):
    with patch("subprocess.run") as mock_run, \
         patch("src.audio_router.AudioRouter._get_nodes") as mock_nodes:
        mock_nodes.return_value = {
            "xlr_source": "10",
            "bt_hfp_source": "42",
            "bt_hfp_sink": "43",
        }
        router.reroute_for_hfp()
        # Should have called pw-link to connect XLR→HFP and HFP→XLR
        calls = [str(c) for c in mock_run.call_args_list]
        assert any("pw-link" in c for c in calls)


def test_reroute_for_a2dp_links_correct_nodes(router):
    with patch("subprocess.run") as mock_run, \
         patch("src.audio_router.AudioRouter._get_nodes") as mock_nodes:
        mock_nodes.return_value = {"xlr_source": "10", "bt_a2dp_sink": "43"}
        router.reroute_for_a2dp()
        calls = [str(c) for c in mock_run.call_args_list]
        assert any("pw-link" in c for c in calls)


def test_set_gain_calls_pw_metadata(router):
    with patch("subprocess.run") as mock_run:
        router.set_input_gain_db(10)
        mock_run.assert_called()
        cmd = str(mock_run.call_args)
        assert "pw-metadata" in cmd or "pactl" in cmd


def test_no_crash_when_nodes_not_found(router):
    with patch("src.audio_router.AudioRouter._get_nodes") as mock_nodes:
        mock_nodes.return_value = {}
        router.reroute_for_hfp()  # should log warning, not crash
        router.reroute_for_a2dp()
