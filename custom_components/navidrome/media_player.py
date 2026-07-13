from homeassistant.components.media_player import MediaPlayerEntity
from homeassistant.const import STATE_IDLE, STATE_PLAYING, STATE_PAUSED
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.components.media_player import MediaPlayerEntityFeature
from homeassistant.util import dt as dt_util

from .const import DOMAIN


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities([
        NavidromeMediaPlayer(coordinator)
    ])


class NavidromeMediaPlayer(CoordinatorEntity, MediaPlayerEntity):
    def __init__(self, coordinator):
        super().__init__(coordinator)
        self._attr_name = "Navidrome"
        self._attr_unique_id = "navidrome_media_player"
        self._last_paused_track_id = None
        self._paused_at = None

    @property
    def state(self):
        # Safely fetch the track using the built-in helper
        track = self._get_current_track()

        # If no track is playing or the list is empty, return IDLE
        if not track:
            self._paused_at = None
            self._last_paused_track_id = None
            return STATE_IDLE

        # Get the unique ID of the track currently being evaluated
        track_id = track.get("id")

        # OpenSubsonic 'playbackReport' Extension (Modern Clients)
        playback_state = track.get("state")
        
        if playback_state is not None:
            state_val = str(playback_state).lower()
            
            if state_val in ["0", "stopped", "idle"]:
                self._paused_at = None
                self._last_paused_track_id = None
                return STATE_IDLE
                
            elif state_val in ["2", "paused"]:
                current_time = dt_util.utcnow()
                
                # If we just switched to paused, or the song changed, lock in the start time
                if self._paused_at == None or self._last_paused_track_id != track_id:
                    self._paused_at = current_time
                    self._last_paused_track_id = track_id
                
                paused_duration = (current_time - self._paused_at).total_seconds()
                
                # If paused longer than 60 seconds on the same track, force IDLE
                if paused_duration >= 60:
                    return STATE_IDLE
                    
                return STATE_PAUSED
                
            elif state_val in ["1", "playing", "3", "buffering"]:
                # Reset local pause state tracking immediately when playback resumes
                self._paused_at = None
                self._last_paused_track_id = None
                return STATE_PLAYING
            else:
                return STATE_PLAYING

        # Legacy Heuristic Fallback (For old clients without the 'state' field)
        minutes_ago = track.get("minutesAgo")
        duration = track.get("duration")

        if minutes_ago is not None:
            if minutes_ago >= 15:
                return STATE_IDLE
            if duration is not None and (minutes_ago * 60) > duration:
                return STATE_IDLE
            if minutes_ago >= 1:
                return STATE_PAUSED
        
        return STATE_PLAYING

    @property
    def device_info(self):
        system = self.coordinator.data.get("system", {})

        return {
            "identifiers": {("navidrome", "server")},
            "name": "Navidrome",
            "manufacturer": "Navidrome",
            "model": "Music Server",
            "sw_version": system.get("version"),
            "configuration_url": self.coordinator.api.base_url,
        }

    def _get_current_track(self):
        data = self.coordinator.data

        if not data:
            return None

        tracks = data.get("now_playing")

        if not tracks or len(tracks) == 0:
            return None

        return tracks[0]

    def _get(self, key):
        track = self._get_current_track()

        if not track:
            return None

        return track.get(key)

    @property
    def media_title(self):
        artist = self._get("artist")
        title = self._get("title")

        if artist and title:
            return f"{artist} - {title}"

        return title

    @property
    def media_artist(self):
        return self._get("displayArtist")

    @property
    def media_album_name(self):
        return self._get("album")

    @property
    def media_duration(self):
        return self._get("duration")

    @property
    def media_position(self):
        track = self._get_current_track()
        if not track:
            return None

        # Look for the OpenSubsonic playbackReport extension
        position_ms = track.get("positionMs")
        
        if position_ms is not None:
            # Home Assistant expects this value in seconds, not milliseconds
            return position_ms / 1000.0
            
        return None

    @property
    def media_position_updated_at(self):
        track = self._get_current_track()
        
        # Only provide an updated timestamp if we actually have a position
        if track and track.get("positionMs") is not None:
            return dt_util.utcnow()
            
        return None

    @property
    def media_content_type(self):
        return self._get("mediaType")

    @property
    def media_content_id(self):
        return self._get("id")

    @property
    def media_image_url(self):
        cover_id = self._get("coverArt")

        if not cover_id:
            return None

        salt, token = self.coordinator.api._generate_token()

        return (
            f"{self.coordinator.api.base_url}/rest/getCoverArt.view"
            f"?id={cover_id}"
            f"&u={self.coordinator.api.username}"
            f"&t={token}"
            f"&s={salt}"
            f"&v=1.16.1"
            f"&c=homeassistant"
        )

    @property
    def entity_picture(self):
        return self.media_image_url

    @property
    def extra_state_attributes(self):
        track = self._get_current_track()

        if not track:
            return {}

        attrs = {
            "track_number": track.get("track"),
            "year": track.get("year"),
            "genre": track.get("genre"),
            "path": track.get("path"),
            "bitrate": track.get("bitRate"),
            "sampling_rate": track.get("samplingRate"),
            "channel_count": track.get("channelCount"),
            "media_player": track.get("playerName"),
            "username": track.get("username")
        }

        return {k: v for k, v in attrs.items() if v is not None}