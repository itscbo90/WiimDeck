"""
wiim_client.py  –  MicroPython wrapper for the WiiM local HTTP API
-------------------------------------------------------------------
All requests are HTTPS to the device LAN IP.
urequests on MicroPython does not verify self-signed certs.

getPlayerStatus field reference
  status  : "play" | "pause" | "stop" | "loading"
  vol     : 0-100  (string)
  mute    : "0" | "1"
  loop    : "0"=loop-all  "1"=single  "2"=shuffle-loop
            "3"=shuffle-no-loop  "4"=no-shuffle-no-loop
  Title   : hex-encoded title (may be empty for radio / Spotify Connect)
  curpos  : position ms (string)
  totlen  : duration ms (string)

getMetaInfo -> metaData field reference
  title        : plain text track title
  artist       : artist name  ("unknow" when unavailable)
  subtitle     : fallback artist / station name
  album        : album title
  albumArtURI  : URL of album art (may contain ?size=0)
"""

import urequests as requests

TIMEOUT = 8   # seconds – short so the UI stays snappy


class WiimClient:
    def __init__(self, ip):
        self._base = "https://" + ip + "/httpapi.asp?command="

    # ------------------------------------------------------------------
    # Internal helper
    # ------------------------------------------------------------------
    def _get(self, command, parse_json=True):
        url = self._base + command
        try:
            resp = requests.get(url, timeout=TIMEOUT)
            if resp.status_code == 200:
                result = resp.json() if parse_json else resp.text
                resp.close()
                return result
            resp.close()
        except Exception as e:
            print("WiimClient [{}] error: {}".format(command, e))
        return None

    # ------------------------------------------------------------------
    # Status queries
    # ------------------------------------------------------------------
    def get_player_status(self):
        """Returns getPlayerStatus dict or None."""
        return self._get("getPlayerStatus")

    def get_meta_info(self):
        """Returns the metaData sub-dict from getMetaInfo or None."""
        data = self._get("getMetaInfo")
        if data and "metaData" in data:
            return data["metaData"]
        return None

    # ------------------------------------------------------------------
    # Playback control
    # ------------------------------------------------------------------
    def play(self):
        self._get("setPlayerCmd:play", parse_json=False)

    def pause(self):
        self._get("setPlayerCmd:pause", parse_json=False)

    def toggle_play_pause(self):
        """onepause: resume if paused, pause if playing."""
        self._get("setPlayerCmd:onepause", parse_json=False)

    def next_track(self):
        self._get("setPlayerCmd:next", parse_json=False)

    def previous_track(self):
        self._get("setPlayerCmd:prev", parse_json=False)

    # ------------------------------------------------------------------
    # Volume
    # ------------------------------------------------------------------
    def set_volume(self, level):
        level = max(0, min(100, int(level)))
        self._get("setPlayerCmd:vol:{}".format(level), parse_json=False)

    def volume_up(self):
        """Increase volume by 5 steps."""
        for _ in range(5):
            self._get("setPlayerCmd:vol++", parse_json=False)

    def volume_down(self):
        """Decrease volume by 5 steps."""
        for _ in range(5):
            self._get("setPlayerCmd:vol--", parse_json=False)

    def toggle_mute(self, muted):
        cmd = "setPlayerCmd:mute:1" if muted else "setPlayerCmd:mute:0"
        self._get(cmd, parse_json=False)

    # ------------------------------------------------------------------
    # Loop / Shuffle  (loopmode values)
    #   0 = loop all           (repeat-all, no shuffle)
    #   1 = single loop        (repeat-one)
    #   2 = shuffle + loop     (shuffle + repeat)
    #   3 = shuffle, no loop
    #   4 = no shuffle, no loop  (default / off)
    # ------------------------------------------------------------------
    def set_loop_mode(self, mode):
        self._get("setPlayerCmd:loopmode:{}".format(mode), parse_json=False)

    def set_shuffle(self, enabled):
        # shuffle on  -> mode 2 (shuffle + loop all)
        # shuffle off -> mode 0 (loop all, ordered)
        self.set_loop_mode(2 if enabled else 0)

    def set_repeat(self, mode):
        # mode: "off"->4  "one"->1  "all"->0
        mapping = {"off": 4, "one": 1, "all": 0}
        self.set_loop_mode(mapping.get(mode, 4))
