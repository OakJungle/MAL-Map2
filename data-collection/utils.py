import asyncio
import random


async def random_wait(min_wait: int = 2000):
    random_wait = random.randint(0, 3000) + min_wait
    await asyncio.sleep(random_wait / 1000)  # convert ms → seconds
