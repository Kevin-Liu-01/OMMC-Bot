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
PROBLEM_FINISHED = -3


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
    problem_data: dict[str, Any]

    def _load(self) -> None:
        """Loads config & data from storage"""
        with open('config.json', 'r') as f:
            self.config = json.load(f)
        try:
            with open('data.pickle', 'rb') as f:
                self.data = pickle.load(f)
        except FileNotFoundError:
            self.data = {}
        try:
            with open('problemdata.pickle', 'rb') as f:
                self.problem_data = pickle.load(f)
        except FileNotFoundError:
            self.problem_data = {}
        if '--update-data' in sys.argv[1:]:
            if 'id' not in self.problem_data:
                self.problem_data['id'] = NO_LAST_PROBLEM_ID
            if 'text' not in self.problem_data:
                self.problem_data['text'] = ''
            if 'answers' not in self.problem_data:
                self.problem_data['answers'] = {}
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
        await self.client.process_commands(message)
        if message.channel.id != message.author.dm_channel.id:
            # Respond in DMs only
            return
        if message.author.id not in self.data:
            self.data[message.author.id] = get_default_user_data()
        userdata = self.data[message.author.id]
        if self.problem_data['id'] == NO_LAST_PROBLEM_ID:
            await message.channel.send('No problem has been set.')
            return

        if userdata['attemptsleft'] == PROBLEM_FINISHED:
            if userdata['lastproblemid'] == self.problem_data['id']:
                await message.channel.send('You have already solved this problem.')
                return
            # Otherwise, we solved the last problem, so just reset to default and keep going.
            userdata.update(get_default_user_data())
            userdata['lastproblemid'] = self.problem_data['id']
        if userdata['attemptsleft'] == 0:
            await message.channel.send('Sorry, you have no attempts left.')
            return

        # TODO: have a "confirm answer" function
        #       "Confirm Answer" "Are you sure you want to submit your answer for problem #ID?"
        if message.content.lower() in self.problem_data['answers']:
            userdata['totalscore'] += 10
            userdata['attemptsleft'] = PROBLEM_FINISHED
            await message.channel.send('Correct! (+10 points)')
        else:
            await message.channel.send(f'Sorry, that is not correct. ({userdata["attemptsleft"]} attempts left)')

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

    @commands.command()
    async def setproblem(self, ctx: commands.Context, *, text: str) -> None:
        self.main.problem_data['id'] = 1  \
                                       if self.main.problem_data['id'] == NO_LAST_PROBLEM_ID  \
                                       else self.main.problem_data['id'] + 1
        self.main.problem_data['text'] = text
        await ctx.send('Enter valid answers. Type `/done/` when finished. Note that answers are not case sensitive.')
        answers = []
        while True:
            answer = await self.client.wait_for('message', check=lambda m: m.author == ctx.author)
            if answer.content == '/done/':
                break
            answers.append(answer.content.lower())
            await answer.add_reaction('\u2611')
        self.main.problem_data['answers'] = answers
        await ctx.send(f'Problem successfully set with id={self.main.problem_data["id"]}.')

    @commands.command()
    async def sendproblem(self, ctx: commands.Context, channel: discord.TextChannel = None) -> None:
        if channel is None:
            channel = ctx.channel
        if self.main.problem_data['id'] == NO_LAST_PROBLEM_ID:
            await ctx.send('No problem has been set.')
            return
        await channel.send(f'## Problem #{self.main.problem_data["id"]}\n\n{self.main.problem_data["text"]}')


def main():
    main_class = Main()
    signal.signal(signal.SIGINT, main_class.termination_handler)
    signal.signal(signal.SIGTERM, main_class.termination_handler)
    asyncio.run(main_class.run())


if __name__ == '__main__':
    main()
