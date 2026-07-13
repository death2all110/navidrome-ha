from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.const import Platform

from .const import DOMAIN, CONF_HOST, CONF_USERNAME, CONF_PASSWORD, CONF_USE_SSL
from .api import NavidromeAPI
from .coordinator import NavidromeCoordinator

# Define all platforms used by this integration in one place
PLATFORMS: list[Platform] = [
    Platform.MEDIA_PLAYER,
    Platform.SENSOR,
    Platform.BUTTON,
]

async def async_setup(hass: HomeAssistant, config: dict):
    return True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    hass.data.setdefault(DOMAIN, {})

    use_ssl = entry.data.get(CONF_USE_SSL, True)
    host = entry.data[CONF_HOST].replace("http://", "").replace("https://", "")
    scheme = "https" if use_ssl else "http"
    base_url = f"{scheme}://{host}"

    api = NavidromeAPI(
        base_url,
        entry.data[CONF_USERNAME],
        entry.data[CONF_PASSWORD],
    )

    coordinator = NavidromeCoordinator(hass, api)
    await coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][entry.entry_id] = coordinator

    async def start_scan_service(call):
        await hass.async_add_executor_job(api.start_scan)
        # refrescar datos tras lanzar scan
        await coordinator.async_request_refresh()

    hass.services.async_register(
        DOMAIN,
        "start_scan",
        start_scan_service
    )

    # Use the PLATFORMS constant to load everything safely
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    # Use the same PLATFORMS constant to ensure nothing gets left behind in memory
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok