"""Configuratieschermen van de YouTube Tracker integratie."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .const import (
    CONF_CHANNEL_ID,
    CONF_CHANNEL_NAME,
    CONF_LOOKBACK_DAYS,
    CONF_LOOKBACK_MODE,
    CONF_SCAN_INTERVAL,
    DEFAULT_LOOKBACK_DAYS,
    DEFAULT_LOOKBACK_MODE,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MAX_LOOKBACK_DAYS,
    MAX_SCAN_INTERVAL,
    MIN_LOOKBACK_DAYS,
    MIN_SCAN_INTERVAL,
    MODE_DAGEN,
    MODE_VORIGE_MAAND,
)
from .feed import FeedError, async_fetch_feed, async_resolve_channel_id

STAP_GEBRUIKER_SCHEMA = vol.Schema({vol.Required("kanaal"): str})


class YouTubeTrackerConfigFlow(ConfigFlow, domain=DOMAIN):
    """Voegt een YouTube-kanaal toe."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Vraag om het kanaal en controleer of de feed werkt."""
        fouten: dict[str, str] = {}

        if user_input is not None:
            session = async_get_clientsession(self.hass)
            try:
                channel_id = await async_resolve_channel_id(
                    session, user_input["kanaal"]
                )
                kanaalnaam, _ = await async_fetch_feed(session, channel_id)
            except FeedError:
                fouten["base"] = "kanaal_niet_gevonden"
            else:
                await self.async_set_unique_id(channel_id)
                self._abort_if_unique_id_configured()

                # Een kanaal zonder video's levert geen naam op
                kanaalnaam = kanaalnaam or channel_id

                return self.async_create_entry(
                    title=kanaalnaam,
                    data={
                        CONF_CHANNEL_ID: channel_id,
                        CONF_CHANNEL_NAME: kanaalnaam,
                    },
                )

        return self.async_show_form(
            step_id="user", data_schema=STAP_GEBRUIKER_SCHEMA, errors=fouten
        )

    @staticmethod
    @callback
    def async_get_options_flow(entry: ConfigEntry) -> YouTubeTrackerOptionsFlow:
        """Geef het optiescherm."""
        return YouTubeTrackerOptionsFlow()


class YouTubeTrackerOptionsFlow(OptionsFlow):
    """Instellingen per kanaal."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Toon en verwerk de instellingen."""
        if user_input is not None:
            # De selectors leveren getallen als float aan
            user_input[CONF_LOOKBACK_DAYS] = int(user_input[CONF_LOOKBACK_DAYS])
            user_input[CONF_SCAN_INTERVAL] = int(user_input[CONF_SCAN_INTERVAL])
            return self.async_create_entry(data=user_input)

        opties = self.config_entry.options

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_LOOKBACK_MODE,
                    default=opties.get(CONF_LOOKBACK_MODE, DEFAULT_LOOKBACK_MODE),
                ): SelectSelector(
                    SelectSelectorConfig(
                        options=[MODE_VORIGE_MAAND, MODE_DAGEN],
                        translation_key="lookback_mode",
                        mode=SelectSelectorMode.DROPDOWN,
                    )
                ),
                vol.Required(
                    CONF_LOOKBACK_DAYS,
                    default=opties.get(CONF_LOOKBACK_DAYS, DEFAULT_LOOKBACK_DAYS),
                ): NumberSelector(
                    NumberSelectorConfig(
                        min=MIN_LOOKBACK_DAYS,
                        max=MAX_LOOKBACK_DAYS,
                        step=1,
                        mode=NumberSelectorMode.BOX,
                    )
                ),
                vol.Required(
                    CONF_SCAN_INTERVAL,
                    default=opties.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
                ): NumberSelector(
                    NumberSelectorConfig(
                        min=MIN_SCAN_INTERVAL,
                        max=MAX_SCAN_INTERVAL,
                        step=5,
                        mode=NumberSelectorMode.BOX,
                        unit_of_measurement="minuten",
                    )
                ),
            }
        )

        return self.async_show_form(step_id="init", data_schema=schema)
