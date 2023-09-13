"""

OMMC PROBLEM OF THE DAY BOT

"""


import json
import pickle
import signal
import sys
from typing import Any

import discord
from discord.ext import commands


NO_LAST_PROBLEM_ID = -2


class Main:
    client: commands.Bot
    config: dict[str, Any]
    data: dict[int, dict[str, Any]]

    def _load(self):
        """Loads config & data from storage"""
        with open('config.json', 'r') as f:
            self.config = json.load(f)
        with open('data.pickle', 'rb') as f:
            self.data = pickle.load(f)
        if '--update-data' in sys.argv[1:]:
            for key, data in self.data:
                if 'lastproblemid' not in data:
                    data['lastproblemid'] = NO_LAST_PROBLEM_ID
                if 'attemptsleft' not in data:
                    data['attemptsleft'] = 5
                if 'totalscore' not in data:
                    data['totalscore'] = 0

    def _save(self):
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
        intents = discord.Intents.default()
        #intents.members = True
        #intents.message_content = True
        self.client = commands.Bot(command_prefix=self.config['prefix'], intents=intents)

    def run(self):
        # TODO: add the tasks to this and use asyncio
        self.client.run(self.config['token'])


def main():
    main_class = Main()
    signal.signal(signal.SIGINT, main_class.termination_handler)
    signal.signal(signal.SIGTERM, main_class.termination_handler)