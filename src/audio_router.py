# src/audio_router.py
import json
import logging
import subprocess
from typing import Dict

logger = logging.getLogger(__name__)


class AudioRouter:
    """Controls PipeWire audio routing via pw-link/pw-dump/pw-metadata."""

    def reroute_for_hfp(self):
        """Connect XLR input → HFP mic, HFP speaker → XLR output."""
        nodes = self._get_nodes()
        xlr_src = nodes.get("xlr_source")
        hfp_sink = nodes.get("bt_hfp_sink")
        hfp_src = nodes.get("bt_hfp_source")
        if not all([xlr_src, hfp_sink]):
            logger.warning("reroute_for_hfp: required nodes not found — aborting")
            return
        self._unlink_all()
        self._link(xlr_src, hfp_sink)
        if hfp_src:
            xlr_out = nodes.get("xlr_sink")
            if xlr_out:
                self._link(hfp_src, xlr_out)
        logger.info("Rerouted for HFP (talk)")

    def reroute_for_a2dp(self):
        """Connect XLR input → A2DP sink (listen-only)."""
        nodes = self._get_nodes()
        xlr_src = nodes.get("xlr_source")
        a2dp_sink = nodes.get("bt_a2dp_sink")
        if not all([xlr_src, a2dp_sink]):
            logger.warning("reroute_for_a2dp: required nodes not found — aborting")
            return
        self._unlink_all()
        self._link(xlr_src, a2dp_sink)
        logger.info("Rerouted for A2DP (listen)")

    def reroute_for_dect(self, talk: bool = False):
        """Connect XLR ↔ DECT node. talk=True opens mic path."""
        nodes = self._get_nodes()
        xlr_src = nodes.get("xlr_source")
        dect_sink = nodes.get("dect_sink")
        dect_src = nodes.get("dect_source")
        if not all([xlr_src, dect_sink]):
            logger.warning("reroute_for_dect: required nodes not found")
            return
        self._unlink_all()
        self._link(xlr_src, dect_sink)
        if talk and dect_src:
            xlr_out = nodes.get("xlr_sink")
            if xlr_out:
                self._link(dect_src, xlr_out)

    def set_input_gain_db(self, db: float):
        self._set_volume("alsa_input", db)

    def set_output_gain_db(self, db: float):
        self._set_volume("alsa_output", db)

    def _set_volume(self, node_partial: str, db: float):
        # Convert dB to linear: V = 10^(dB/20)
        linear = 10 ** (db / 20.0)
        linear = max(0.0, min(linear, 4.0))
        try:
            subprocess.run(
                ["pw-metadata", "-n", "settings", "0",
                 "node.{}.volume".format(node_partial), str(linear)],
                capture_output=True, check=False
            )
        except FileNotFoundError:
            logger.warning("pw-metadata not found — running without PipeWire?")

    def _get_nodes(self) -> Dict[str, str]:
        """Query pw-dump and return a dict of logical role → node ID."""
        try:
            result = subprocess.run(
                ["pw-dump"], capture_output=True, check=False, timeout=2
            )
            nodes = json.loads(result.stdout)
        except Exception as e:
            logger.warning("pw-dump failed: %s", e)
            return {}

        role_map: Dict[str, str] = {}
        for node in nodes:
            if node.get("type") != "PipeWire:Interface:Node":
                continue
            props = node.get("props", {})
            name = props.get("node.name", "")
            nid = str(node.get("id", ""))
            media_class = props.get("media.class", "")

            if "bluez" in name and "hfp" in name:
                if "Source" in media_class:
                    role_map["bt_hfp_source"] = nid
                else:
                    role_map["bt_hfp_sink"] = nid
            elif "bluez" in name and "a2dp" in name:
                role_map["bt_a2dp_sink"] = nid
            elif "alsa" in name and "input" in name:
                role_map["xlr_source"] = nid
            elif "alsa" in name and "output" in name:
                role_map["xlr_sink"] = nid
            elif "dect" in name or "jabra" in name.lower() or "epos" in name.lower():
                if "Source" in media_class:
                    role_map["dect_source"] = nid
                else:
                    role_map["dect_sink"] = nid

        return role_map

    def _link(self, src_id: str, dst_id: str):
        try:
            subprocess.run(
                ["pw-link", src_id, dst_id],
                capture_output=True, check=False
            )
        except FileNotFoundError:
            logger.warning("pw-link not found")

    def _unlink_all(self):
        """Remove all existing pw-link connections (clean slate before reroute)."""
        try:
            result = subprocess.run(
                ["pw-link", "--list"], capture_output=True, check=False
            )
            for line in result.stdout.decode().splitlines():
                parts = line.strip().split()
                if len(parts) >= 3 and "->" in parts:
                    src, dst = parts[0], parts[2]
                    subprocess.run(
                        ["pw-link", "--disconnect", src, dst],
                        capture_output=True, check=False
                    )
        except Exception as e:
            logger.warning("_unlink_all: %s", e)
