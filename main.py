"""

OMMC PROBLEM OF THE DAY BOT

"""


import asyncio
import datetime
import json
import logging
import math
import pickle
import re
import signal
import sys
from typing import Any

import discord
from discord.ext import commands, tasks

SHARES = [
    0,
    0.15,  # 1 attempt left
    0.35,
    0.55,
    0.75,
    1.0,  # 5 attempts (first try)
]
HOUR_OF_RESET = 22
TIMEDELTA = datetime.timedelta(days=1.0)
LEAD_PAGE_SIZE = 10
POINTS_TO_EACH_STAR = [0, 100, 250, 450, 700, 1000, 1300, 1600, 1900, 2200, 2500]
STARS = '⭑★✬✰✶✵✭✪✸✦❂'


discord.utils.setup_logging()


def get_default_user_data() -> dict[str, Any]:
    return {
        'answered': False,
        'attemptsleft': 5,
        'totalscore': 0,
    }


def get_star(points: int) -> str:
    """Returns the star character for some number of points."""
    for i, points_needed in enumerate(POINTS_TO_EACH_STAR):
        if points < points_needed:
            return STARS[i-1]
    return STARS[-1]


def get_next_index(points: int) -> int:
    """Returns the next star index some number of points."""
    for i, points_needed in enumerate(POINTS_TO_EACH_STAR):
        if points < points_needed:
            return i
    return None


def validate_answer(answer: str, answerformat: str) -> tuple[bool, str]:
    """Validates :answer: to :answerformat:. Returns a tuple[success or not, message if failed]"""
    if answerformat == 'integer':
        if re.match(r'^(-?[1-9]\d*|0)$', answer) is None:
            return False, 'This is an invalid integer. Enter an integer, like `10` or `-2`.'
        return True, ''
    if answerformat == 'fraction':
        match = re.match(r'^-?([1-9]\d*)/([1-9]\d*)$', answer)
        if match is None:
            return False, 'This is an invalid fraction. Enter `m/n` or `-m/n` where `m` and `n` are positive integers, like `5/3` or `-1/2`.'
        numerator = int(match.group(1))
        denominator = int(match.group(2))
        if numerator > 1_000_000 or denominator > 1_000_000:
            return False, 'Fraction too large!'
        if math.gcd(numerator, denominator) != 1:
            return False, 'This fraction is not simplified.'
        return True, ''
    if answerformat == 'string':
        return True, ''
    return False, 'Invalid answer format supplied by the problem. Contact admin.'


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
                    'lastreset': [1970, 1, 1],  # year, month, day, hour (in UTC)
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
        self.client.remove_command('help')
        self.client.event(self.on_ready)
        self.client.event(self.on_command_error)
        self.client.event(self.on_message)

    #

    @tasks.loop(seconds=20.0)
    async def check_time(self) -> None:
        """Checks if the current problem has expired"""
        if not self.is_current_problem():
            return
        now = datetime.datetime.now()
        if now >= self.get_last_reset_time() + TIMEDELTA:
            logging.info('check_time: Problem expired!')
            await self.next_problem()

    async def post_question(self) -> None:
        problem_channel = await self.client.fetch_channel(self.config['problemchannel'])
        new_problem = self.problems[self.state["currentproblemid"]]
        timestamp = int((self.get_last_reset_time() + TIMEDELTA).timestamp())
        embed = discord.Embed(title='Problem of the Day',
                              description=f'Closes <t:{timestamp}:R>\nAnswer format: `{new_problem["answerformat"]}`')
        embed.set_image(url=new_problem['imageurl'])
        await problem_channel.send(embed=embed)

    async def next_problem(self) -> None:
        """Gives points for the current problem and moves to the next."""
        if not self.is_current_problem():
            logging.warning('next_problem was called while no problem was active')
            return

        guild = await self.client.fetch_guild(self.config['guildid'])
        role = None if guild is None else guild.get_role(self.config['solvedrole'])

        total_shares = sum(SHARES[user_data['attemptsleft']] for user_data in self.users.values() if user_data['answered'])
        logging.info(f'total shares is {total_shares}')
        score_per_share = 3000.0 / (6.0 + total_shares)
        logging.info(f'score per share is {score_per_share}')
        for user_id, user_data in self.users.items():
            if user_data['answered']:
                score = int(score_per_share * SHARES[user_data['attemptsleft']])
                user_data['totalscore'] += score
                user = self.client.get_user(user_id)
                if user is not None:
                    try:
                        await user.send(f'You earned **{score}** points for this problem!\n'
                                        f'Your total score is now **{user_data["totalscore"]}** points.'
                                        )
                    except discord.errors.Forbidden:
                        logging.warning(f'Could not send DM to user ID {user_id}')
                if role is not None:
                    member = await guild.fetch_member(user_id)
                    if member is not None:
                        await member.remove_roles(role)
                    else:
                        logging.warning(f'Could not remove role from user ID {user_id} because member is None')
        for userdata in self.users.values():
            userdata['answered'] = False
            userdata['attemptsleft'] = 5

        self.state['currentproblemid'] += 1
        self.state['lastreset'] = datetime.datetime.now().timetuple()[:3]  # Y, M, D

        if not self.is_current_problem():
            logging.warning('No more problems!')
            return
        await self.post_question()

    #

    def get_last_reset_time(self) -> datetime.datetime:
        return datetime.datetime(*self.state['lastreset'], HOUR_OF_RESET)

    def is_current_problem(self) -> bool:
        """Returns whether there is a current problem"""
        return self.state['currentproblemid'] < len(self.problems)

    #

    async def on_ready(self) -> None:
        """Handles on_ready event"""
        logging.info(f'bot is ready, logged in as {self.client.user.display_name} ({self.client.user.id})')

    async def on_command_error(self, ctx: commands.Context, exception) -> None:
        """Handles on_command_error event"""
        error_type = type(exception)
        if error_type is commands.MissingRequiredArgument:
            await ctx.send(f'```\n[Error] Missing Argument: {exception}\n\n----- Usage is below -----\n{ctx.command.usage}\n```')
        elif error_type is commands.UnexpectedQuoteError:
            await ctx.send('[Error] unexpected quote mark found. Try escaping it (`\\\"` or `\\\'`)')
        elif error_type is commands.CommandOnCooldown:
            waittime = int(exception.retry_after)
            await ctx.send(f'This command is on cooldown. Try again in **{waittime}s**.')
        elif error_type is commands.BadArgument:
            await ctx.send('Bad argument! Please try again.')
        elif error_type is commands.CommandNotFound:
            pass
        else:
            logging.error(f'Ignoring exception in command {ctx.command}', exc_info=exception)

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
        
        problem = self.problems[self.state['currentproblemid']]
        given_answer = message.content.lower()
        validated, errmsg = validate_answer(given_answer, problem['answerformat'])
        if not validated:
            await message.channel.send(f'{errmsg}\n*No credit lost. You still have {user["attemptsleft"]} attempts. Please try again.*')
            return

        if given_answer == problem['answer']:
            user['answered'] = True
            guild = await self.client.fetch_guild(self.config['guildid'])
            role = None if guild is None else guild.get_role(self.config['solvedrole'])
            if role is None:
                await message.channel.send('Failed to give solved role! Please contact an admin.')
            else:
                member = await guild.fetch_member(message.author.id)
                if member is None:
                    await message.channel.send('Failed to give solved role! Please contact an admin.')
                else:
                    try:
                        await member.add_roles(role)
                    except discord.errors.Forbidden:
                        await message.channel.send('Failed to give solved role! I do not have permission! Please contact an admin.')
            await message.channel.send('Correct! You will receive points when the problem closes.')
            logging.info(f'{message.author.name} gave correct answer')
        else:
            user['attemptsleft'] -= 1
            await message.channel.send(f'Incorrect! You have {user["attemptsleft"]} attempts left.')
            logging.info(f'{message.author.name} gave WRONG answer ({given_answer=})')

    async def run(self):
        await self.client.add_cog(Commands(self))
        self.check_time.start()
        logging.info('starting bot')
        await self.client.start(self.config['token'])


class Commands(commands.Cog):
    main: Main
    client: commands.Bot

    def __init__(self, main_class: Main):
        self.main = main_class
        self.client = main_class.client

    def validate_staff_role(self, ctx: commands.Context) -> bool:
        """Checks if the user has the staff role"""
        if ctx.guild is None:
            return False
        return self.main.config['staffroleid'] in [role.id for role in ctx.author.roles]

    #

    @commands.command()
    @commands.cooldown(1, 3.0, commands.BucketType.user)
    async def help(self, ctx: commands.Context, *, args: str = None) -> None:
        embed = discord.Embed(
            title='Help',
            description='**Commands**\n'
                        '`help` - show this message\n'
                        '`rank` - show your rank\n'
                        '`leaderboard` - show the leaderboard'
        )
        await ctx.send(embed=embed)

    @commands.command()
    @commands.cooldown(1, 3.0, commands.BucketType.user)
    async def rank(self, ctx: commands.Context) -> None:
        if ctx.author.id not in self.main.users:
            await ctx.send('You have not answered any problems yet.')
            return
        points = self.main.users[ctx.author.id]['totalscore']
        i = get_next_index(points)
        nextstartext = 'None' if i is None else f'{STARS[i]} (in {POINTS_TO_EACH_STAR[i] - points} points)'
        embed = discord.Embed(
            title='Rank',
            description=f'Points: **{points}{get_star(points)}**\n\n'
                        f'Next Star: {nextstartext}',
            color=discord.Color.random()
        )
        await ctx.send(embed=embed)

    @commands.command()
    @commands.cooldown(1, 3.0, commands.BucketType.user)
    async def leaderboard(self, ctx: commands.Context, page: int = 1) -> None:
        """Shows the leaderboard"""
        max_page = math.ceil(len(self.main.users) / LEAD_PAGE_SIZE)
        page = min(max(page, 1), max_page)
        i_start = (page - 1) * LEAD_PAGE_SIZE
        leaderboard = sorted(self.main.users.items(), key=lambda x: x[1]['totalscore'], reverse=True)
        descs = []
        for i, (user_id, userdata) in enumerate(leaderboard[i_start:i_start+LEAD_PAGE_SIZE], start=i_start):
            descs.append(f'**#{i+1}** <@{user_id}>\n\u2192 **{userdata["totalscore"]}{get_star(userdata["totalscore"])}**')
        embed = discord.Embed(title='Leaderboard', description='\n\n'.join(descs))
        embed.set_footer(text=f'Page {page}/{max_page}')
        await ctx.send(embed=embed)

    #

    @commands.command()
    async def status(self, ctx: commands.Context) -> None:
        if not self.validate_staff_role(ctx):
            await ctx.send('You do not have permission to use this command.')
            return

        last_reset = self.main.get_last_reset_time()
        problems_left = len(self.main.problems) - self.main.state['currentproblemid'] - 1
        guild = await self.client.fetch_guild(self.main.config['guildid'])
        role = None if guild is None else guild.get_role(self.main.config['solvedrole'])
        desc = (f'Current problem: **#{self.main.state["currentproblemid"]}**\n'
                f'Active: **{"yes" if self.main.is_current_problem() else "no"}**\n\n'
                f'Problem count: **{len(self.main.problems)}**\n\n'
                f'Last reset: <t:{int(last_reset.timestamp())}:R> (calculated time)\n'
                f'Next reset: <t:{int((last_reset + TIMEDELTA).timestamp())}:R>\n\n'
                f'Guild: {"**FAILED**" if guild is None else guild.name}\n'
                f'Role to give: <@&{self.main.config["solvedrole"]}> (successfully fetched: **{role is not None}**)\n\n'
                f'{"**ATTENTION!** Only " if problems_left <= 2 else ""}{problems_left} problems left'
                )
        embed = discord.Embed(title='Status', description=desc)
        await ctx.send(embed=embed)

    @commands.command(usage='addproblem <imageurl> <answer> <answerformat>')
    async def addproblem(self, ctx: commands.Context, imageurl: str, answer: str, answerformat: str) -> None:
        if not self.validate_staff_role(ctx):
            await ctx.send('You do not have permission to use this command.')
            return

        valid_answer_formats = ('integer', 'fraction', 'string')
        if answerformat not in valid_answer_formats:
            await ctx.send(f'Invalid answer format. Must be one of: {", ".join(valid_answer_formats)}')
            return
        answer = answer.lower()
        validated, errmsg = validate_answer(answer, answerformat)
        if not validated:
            await ctx.send(f'The answer you gave does not comply with the format `{answerformat}`: {errmsg}')
            return
        self.main.problems.append({
            'imageurl': imageurl,
            'answer': answer,
            'answerformat': answerformat,
        })
        await ctx.send(f'Problem added (#{len(self.main.problems) - 1})')

    @commands.command()
    async def forcenextproblem(self, ctx: commands.Context) -> None:
        if not self.validate_staff_role(ctx):
            await ctx.send('You do not have permission to use this command.')
            return

        await self.main.next_problem()
        await ctx.send(f'Problem is now #{self.main.state["currentproblemid"]}')

    @commands.command()
    async def resetproblems(self, ctx: commands.Context, *, extra: str = '') -> None:
        if not self.validate_staff_role(ctx):
            await ctx.send('You do not have permission to use this command.')
            return

        if not extra:
            await ctx.send('Specify what to delete.')
            return
        if 'currentproblemid' in extra:
            self.main.state['currentproblemid'] = 0
        if 'problems' in extra:
            self.main.problems.clear()
        if 'lastreset' in extra:
            self.main.state['lastreset'] = [1970, 1, 1]
        if '-iknowwhatimdoing-195827485091-allpoints' in extra:
            print(self.main.users)
            for userdata in self.main.users.values():
                userdata['totalscore'] = 0
        await ctx.send(f'Done. (extra = `{extra}`)')

    @commands.command()
    async def postagain(self, ctx: commands.Context) -> None:
        if not self.validate_staff_role(ctx):
            await ctx.send('You do not have permission to use this command.')
            return
        await self.main.post_question()

    @commands.command()
    async def extenddeadline(self, ctx: commands.Context) -> None:
        if not self.validate_staff_role(ctx):
            await ctx.send('You do not have permission to use this command.')
            return
        current_deadline = datetime.datetime(*self.main.state['lastreset']) + TIMEDELTA
        self.main.state['lastreset'] = current_deadline.timetuple()[:3]
        await ctx.send(f'`lastreset` is now {self.main.state["lastreset"]}, run `postagain` to show changes')


def main():
    main_class = Main()
    signal.signal(signal.SIGINT, main_class.termination_handler)
    signal.signal(signal.SIGTERM, main_class.termination_handler)
    asyncio.run(main_class.run())


if __name__ == '__main__':
    main()
