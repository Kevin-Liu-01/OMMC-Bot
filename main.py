"""

OMMC PROBLEM OF THE DAY BOT

"""
import asyncio
import json
import pickle
import signal
import sys
from typing import Any

import discord
from discord.ext import commands


NO_LAST_PROBLEM_ID = -2


def get_default_user_data() -> dict[str, Any]:
    return {
        'lastproblemid': NO_LAST_PROBLEM_ID,
        'attemptsleft': 5,
        'totalscore': 0,
    }


class Main:
    client: commands.Bot
    config: dict[str, Any]
    data: dict[int, dict[str, Any]]

    def _load(self) -> None:
        """Loads config & data from storage"""
        with open('config.json', 'r') as f:
            self.config = json.load(f)
        try:
            with open('data.pickle', 'rb') as f:
                self.data = pickle.load(f)
        except FileNotFoundError:
            self.data = {}
        if '--update-data' in sys.argv[1:]:
            for key, data in self.data:
                self.data[key] = get_default_user_data()

    def _save(self) -> None:
        """Saves data to storage"""
        with open('data.pickle', 'wb') as f:
            pickle.dump(self.data, f)
        print('[info]  data successfully saved')

    def termination_handler(self, signal, frame):
        """Handles SIGINT and SIGTERM"""
        print('[info]  exiting...')
        self._save()
        sys.exit(0)

    def __init__(self):
        self._load()
        intents = discord.Intents.default()
        #intents.members = True
        #intents.message_content = True
        self.client = commands.Bot(command_prefix=self.config['prefix'], intents=intents)
        self.client.event(self.on_ready)
        self.client.event(self.on_message)

    async def on_ready(self) -> None:
        """Handles on_ready event"""
        print(f'[info]  bot is ready, logged in as {self.client.user.display_name} ({self.client.user.id})')

    async def on_message(self, message: discord.Message) -> None:
        """Handles on_message event"""
        if message.author.bot:
            return
        if message.channel.id != message.author.dm_channel.id:
            # Respond in DMs only
            return
        if message.author.id not in self.data:
            self.data[message.author.id] = get_default_user_data()
        if message.content == 'the answer':
            await message.channel.send('Yes')
        else:
            await message.channel.send('No')

    async def run(self):
        await self.client.add_cog(Commands(self))
        print('[info]  starting bot...')
        await self.client.start(self.config['token'])


class Commands(commands.Cog):
    main: Main
    client: commands.Bot

    def __init__(self, main_class: Main):
        self.main = main_class
        self.client = main_class.client

    @commands.command()
    async def ping(self, ctx: commands.Context) -> None:
        await ctx.send('pong')


def main():
    main_class = Main()
    signal.signal(signal.SIGINT, main_class.termination_handler)
    signal.signal(signal.SIGTERM, main_class.termination_handler)
    asyncio.run(main_class.run())


if __name__ == '__main__':
    main()
