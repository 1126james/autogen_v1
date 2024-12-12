import asyncio
from datetime import datetime

nums = [y for y in range(10000)]

async def sqr(nums):
    return nums**2

async def main():
    start = datetime.now().time().microsecond
    tasks = [sqr(i) for i in nums]
    end = datetime.now().time().microsecond
    print(f"Async time: {end-start}")
    result = await asyncio.gather(*tasks)

start = datetime.now().time().microsecond
ls = [x**2 for x in nums]
end = datetime.now().time().microsecond
print(f"Normal time: {end-start}")


asyncio.run(main())

