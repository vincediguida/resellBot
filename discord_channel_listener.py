"""Discord channel listener and forwarder.

This utility connects to Discord using a bot token, listens to one or more
channels, and forwards the captured messages to a webhook endpoint. It is
designed for reseller workflows where receiving restock pings in near real time
is essential and where the classic webhook export is not available.

Example usage::

    python discord_channel_listener.py \
        --config discord_listener_config.json \
        --log-level INFO

The script expects the ``discord.py`` package (v2+) to be installed.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
from dataclasses import dataclass
from typing import Iterable, Sequence

import aiohttp
import discord


LOGGER = logging.getLogger("resell.discord.listener")


def _default(obj: object) -> list[int] | dict | str | None:
    """Helper for dataclass serialisation when writing sample configs."""

    if isinstance(obj, set):
        return list(obj)
    raise TypeError(f"Object of type {obj.__class__.__name__} is not JSON serialisable")


@dataclass
class ListenerConfig:
    """In-memory representation of the listener configuration."""

    channels: Sequence[int]
    webhook_url: str
    keywords: Sequence[str]
    ignore_bot_messages: bool = True
    include_attachments: bool = True

    @classmethod
    def from_mapping(cls, data: dict[str, object]) -> "ListenerConfig":
        try:
            raw_channels = data.get("channels") or []
            channels = [int(ch) for ch in raw_channels]
        except (TypeError, ValueError) as exc:  # pragma: no cover - defensive guard
            raise ValueError("'channels' deve essere una lista di ID numerici") from exc

        webhook_url = str(data.get("webhook_url", "")).strip()
        keywords_raw: Iterable[str] = data.get("keywords") or []
        keywords = tuple(sorted({kw.strip().lower() for kw in keywords_raw if kw}))

        ignore_bots = bool(data.get("ignore_bot_messages", True))
        include_attachments = bool(data.get("include_attachments", True))

        if not channels:
            raise ValueError("Config: specificare almeno un channel ID in 'channels'.")
        if not webhook_url:
            raise ValueError("Config: 'webhook_url' non può essere vuoto.")

        return cls(
            channels=tuple(channels),
            webhook_url=webhook_url,
            keywords=keywords,
            ignore_bot_messages=ignore_bots,
            include_attachments=include_attachments,
        )


class ForwardingClient(discord.Client):
    """Discord client that forwards messages to an external webhook."""

    def __init__(self, config: ListenerConfig, *, log_jump_url: bool = True):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.messages = True
        super().__init__(intents=intents)
        self.config = config
        self._session: aiohttp.ClientSession | None = None
        self._log_jump_url = log_jump_url

    async def setup_hook(self) -> None:
        self._session = aiohttp.ClientSession()

    async def close(self) -> None:  # pragma: no cover - I/O heavy
        try:
            if self._session and not self._session.closed:
                await self._session.close()
        finally:
            await super().close()

    async def on_ready(self) -> None:
        guilds = ", ".join(g.name for g in self.guilds) or "(nessuna guild)"
        LOGGER.info(
            "Bot connesso come %s (%s). Guild attive: %s",
            self.user,
            self.user.id if self.user else "?",
            guilds,
        )
        LOGGER.info("Monitoraggio canali: %s", ", ".join(map(str, self.config.channels)))

    async def on_message(self, message: discord.Message) -> None:
        # Ignora messaggi provenienti da altri bot, se richiesto
        if self.config.ignore_bot_messages and message.author.bot:
            return
        if message.channel.id not in self.config.channels:
            return

        content = (message.content or "").strip()
        if self.config.keywords and not any(
            keyword in content.lower() for keyword in self.config.keywords
        ):
            return

        lines = [
            f"**{message.author.display_name}** in <#{message.channel.id}>",
        ]
        if content:
            lines.append(content)

        if self._log_jump_url:
            lines.append(f"Link messaggio: {message.jump_url}")

        if self.config.include_attachments and message.attachments:
            lines.append("Allegati:")
            for attachment in message.attachments:
                lines.append(f"- {attachment.filename}: {attachment.url}")

        payload = {"content": "\n".join(lines)}

        if not payload["content"].strip():
            LOGGER.debug("Messaggio vuoto ignorato (ID: %s)", message.id)
            return

        LOGGER.debug(
            "Inoltro messaggio %s del canale %s al webhook", message.id, message.channel.id
        )

        assert self._session is not None  # setup_hook guarantees it
        async with self._session.post(self.config.webhook_url, json=payload) as resp:
            if resp.status >= 300:
                body = await resp.text()
                LOGGER.error(
                    "Errore dal webhook (%s): %s", resp.status, body.strip() or "<vuoto>"
                )
            else:
                LOGGER.info(
                    "Messaggio %s inoltrato con successo al webhook (status %s)",
                    message.id,
                    resp.status,
                )


def read_config(path: str) -> dict[str, object]:
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"File di configurazione '{path}' non trovato. Crea il file partendo "
            "dall'esempio 'discord_listener_config.example.json'."
        )

    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        default="discord_listener_config.json",
        help="Percorso del file JSON con la configurazione.",
    )
    parser.add_argument(
        "--token",
        help="Bot token Discord (sovrascrive config/env).",
    )
    parser.add_argument(
        "--webhook",
        help="Webhook URL (sovrascrive il valore nel file di config).",
    )
    parser.add_argument(
        "--channel",
        dest="channels",
        action="append",
        type=int,
        help="ID di un canale da monitorare (può essere ripetuto).",
    )
    parser.add_argument(
        "--keyword",
        dest="keywords",
        action="append",
        help="Keyword da filtrare (può essere ripetuta).",
    )
    parser.add_argument(
        "--log-level",
        default=os.getenv("DISCORD_LISTENER_LOG", "INFO"),
        help="Livello di logging (es. DEBUG, INFO, WARNING).",
    )
    return parser.parse_args()


def configure_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )


def main() -> None:
    args = parse_args()
    configure_logging(args.log_level)

    raw_config = read_config(args.config)

    if args.channels:
        raw_config["channels"] = args.channels
    if args.webhook:
        raw_config["webhook_url"] = args.webhook
    if args.keywords:
        raw_config["keywords"] = args.keywords

    token = (
        args.token
        or raw_config.get("bot_token")
        or os.getenv("DISCORD_BOT_TOKEN")
        or ""
    ).strip()
    if not token:
        raise SystemExit(
            "⚠️ Nessun bot token fornito. Usa --token, il campo 'bot_token' nel "
            "file di configurazione o l'environment variable DISCORD_BOT_TOKEN."
        )

    config = ListenerConfig.from_mapping(raw_config)
    LOGGER.debug("Config caricata: %s", json.dumps(config.__dict__, default=_default))

    client = ForwardingClient(config)

    try:
        asyncio.run(client.start(token))
    except KeyboardInterrupt:
        LOGGER.info("Interruzione manuale, arresto del bot...")
    finally:
        if not client.is_closed():  # pragma: no cover - shutdown path
            asyncio.run(client.close())


if __name__ == "__main__":
    main()

