"""

OMMC PROBLEM OF THE DAY BOT

"""


import asyncio
import json
import logging
import pickle
import signal
import sys
from typing import Any

import discord
from discord.ext import commands


SHARES = [
    0,
    0.15,  # 1 attempt left
    0.35,
    0.55,
    0.75,
    1.0,  # 5 attempts (first try)
]


discord.utils.setup_logging()


def get_default_user_data() -> dict[str, Any]:
    return {
        'answered': False,
        'attemptsleft': 5,
        'totalscore': 0,
    }


class Main:
    client: commands.Bot

    config: dict[str, Any]
    _data: dict[str, Any]

    @property
    def problems(self) -> list[dict[str, Any]]:
        return self._data['problems']
    @property
    def users(self) -> dict[int, dict[str, Any]]:
        return self._data['users']
    @property
    def state(self) -> dict[str, Any]:
        return self._data['state']

    def load_data(self) -> None:
        """Loads config & data from storage"""
        with open('config.json', 'r') as f:
            self.config = json.load(f)
        try:
            with open('data.pickle', 'rb') as f:
                self._data = pickle.load(f)
        except FileNotFoundError:
            self._data = {
                'problems': [],
                'users': {},
                'state': {
                    'currentproblemid': 0,
                    'lastreset': [1970, 1, 1, 0],  # year, month, day, hour (in UTC)
                },
            }

    def save_data(self) -> None:
        """Saves data to storage"""
        with open('data.pickle', 'wb') as f:
            pickle.dump(self._data, f)
        logging.info('data successfully saved')

    def termination_handler(self, signal, frame):
        """Handles SIGINT and SIGTERM"""
        logging.info('exiting')
        self.save_data()
        sys.exit(0)

    def __init__(self):
        self.load_data()
        intents = discord.Intents.default()
        intents.members = True
        intents.message_content = True
        self.client = commands.Bot(command_prefix=self.config['prefix'], intents=intents)
        self.client.event(self.on_ready)
        self.client.event(self.on_message)

    #

    async def next_problem(self) -> None:
        """Gives points for the current problem and moves to the next."""
        if not self.is_current_problem():
            logging.warning('next_problem was called while no problem was active')
            return
        total_shares = sum(SHARES[user_data['attemptsleft']] for user_data in self.users.values() if user_data['answered'])
        logging.info(f'total shares is {total_shares}')
        score_per_share = 5000.0 / (6.0 + total_shares)
        logging.info(f'score per share is {score_per_share}')
        for user_id, user_data in self.users.items():
            if user_data['answered']:
                score = int(score_per_share * SHARES[user_data['attemptsleft']])
                user_data['totalscore'] += score
                user = self.client.get_user(user_id)
                if user is not None:
                    await user.send(f'You earned **{score}** points for this problem!\n'
                                    f'Your total score is now **{user_data["totalscore"]}** points.'
                                    )
        for userdata in self.users.values():
            userdata['answered'] = False
            userdata['attemptsleft'] = 5
        #self.state['currentproblemid'] += 1
        # TODO: make this work
        self.state['lastreset'] = [1970, 1, 1, 0]

    #

    def is_current_problem(self) -> bool:
        """Returns whether there is a current problem"""
        return self.state['currentproblemid'] < len(self.problems)

    #

    async def on_ready(self) -> None:
        """Handles on_ready event"""
        logging.info(f'bot is ready, logged in as {self.client.user.display_name} ({self.client.user.id})')

    async def on_message(self, message: discord.Message) -> None:
        """Handles on_message event"""
        if message.author.bot:
            return
        await self.client.process_commands(message)
        if message.channel.type != discord.ChannelType.private:
            # Respond in DMs only
            return
        if not self.is_current_problem():
            await message.channel.send('No problem is currently active.')
            return
        if message.author.id not in self.users:
            # Add user if nonexistent
            self.users[message.author.id] = get_default_user_data()
        user = self.users[message.author.id]
        if user['answered']:
            await message.channel.send('You have already answered this problem.')
            return
        if user['attemptsleft'] <= 0:
            await message.channel.send('You have no attempts left.')
            return
        # TODO: better quality answer checker
        problem = self.problems[self.state['currentproblemid']]
        if message.content.lower() == problem['answer'].lower():
            user['answered'] = True
            await message.channel.send('Correct!')
        else:
            user['attemptsleft'] -= 1
            await message.channel.send(f'Incorrect! You have {user["attemptsleft"]} attempts left.')

    async def run(self):
        await self.client.add_cog(Commands(self))
        logging.info('starting bot')
        await self.client.start(self.config['token'])


class Commands(commands.Cog):
    main: Main
    client: commands.Bot

    def __init__(self, main_class: Main):
        self.main = main_class
        self.client = main_class.client

    @commands.command()
    async def status(self, ctx: commands.Context) -> None:
        desc = (f'Current problem: **#{self.main.state["currentproblemid"]}** '
                f'(active: **{"yes" if self.main.is_current_problem() else "no"}**)\n\n'
                f'Problem count: **{len(self.main.problems)}**\n'
                )
        embed = discord.Embed(title='Status', description=desc)
        await ctx.send(embed=embed)

    @commands.command()
    async def addproblem(self, ctx: commands.Context, imageurl: str, answer: str, answerformat: str) -> None:
        valid_answer_formats = ('integer', 'fraction', 'string', 'decimal1', 'decimal2', 'decimal3')
        if answerformat not in valid_answer_formats:
            await ctx.send(f'Invalid answer format. Must be one of: {", ".join(valid_answer_formats)}')
            return
        self.main.problems.append({
            'imageurl': imageurl,
            'answer': answer,
            'answerformat': answerformat,
        })
        await ctx.send(f'Problem added (#{len(self.main.problems) - 1})')

    @commands.command()
    async def sendproblem(self, ctx: commands.Context, channel: discord.TextChannel = None) -> None:
        if channel is None:
            channel = ctx.channel
        if not self.main.is_current_problem():
            await channel.send('No problem is currently active.')
            return
        problem = self.main.problems[self.main.state['currentproblemid']]
        embed = discord.Embed(title=f'Problem #{self.main.state["currentproblemid"]}')
        embed.set_image(url=problem['imageurl'])
        embed.set_footer(text=f'Answer format: {problem["answerformat"]}')
        await channel.send(embed=embed)

    @commands.command()
    async def forcenextproblem(self, ctx: commands.Context) -> None:
        await self.main.next_problem()
        await ctx.send(f'Problem is now #{self.main.state["currentproblemid"]}')


def main():
    main_class = Main()
    signal.signal(signal.SIGINT, main_class.termination_handler)
    signal.signal(signal.SIGTERM, main_class.termination_handler)
    asyncio.run(main_class.run())


if __name__ == '__main__':
    main()
