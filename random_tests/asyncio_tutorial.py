
import asyncio
import time
import requests # Used to demonstrate a real "blocking" library

# ======================================================================================================================
# PART 0: INTRODUCTION - THE "WHY"
# ======================================================================================================================
#
# Normal Python code runs "synchronously". This means if you have a task that takes 10 seconds,
# the entire program freezes and waits for those 10 seconds to pass before doing anything else.
#
# Asynchronous code (asyncio) allows you to say: "This task is going to take a while. While I'm waiting
# for it, let me go do other useful work."
#
# This is perfect for bots, which are constantly waiting for slow things like:
#   - A response from Discord's API
#   - A response from the Guerrilla Mail API
#   - The AI to finish thinking
#
# This tutorial will walk you through the core concepts.
#

# ======================================================================================================================
# PART 1: THE BASICS - ASYNC, AWAIT, AND AWAITING A "COROUTINE"
# ======================================================================================================================

# When you write `async def`, you are not creating a normal function. You are creating a "coroutine".
# Think of it as a blueprint for a special, pausable task.
async def say_hello_slowly():
    """
    This is a coroutine. When we call it, it doesn't run immediately.
    It creates a "coroutine object" that the event loop can run.
    """
    print("Hello...")
    # `await` is the magic keyword. It says: "Pause this function right here."
    # `asyncio.sleep(2)` is the asynchronous version of `time.sleep()`. It's a coroutine that
    # tells the event loop to pause for 2 seconds without freezing the whole program.
    await asyncio.sleep(2)
    print("...World!")

async def main_part_1():
    """The main entry point for this part of the tutorial."""
    print("--- Running Part 1: The Basics ---")
    start_time = time.monotonic()

    # When we `await` our coroutine, we are telling the event loop: "Run this task and wait for it to finish."
    await say_hello_slowly()

    end_time = time.monotonic()
    print(f"Part 1 finished in {end_time - start_time:.2f} seconds.\n")


# ======================================================================================================================
# PART 2: CONCURRENCY - RUNNING MULTIPLE THINGS AT ONCE WITH ASYNCIO.GATHER()
# ======================================================================================================================

# This is where asyncio shines. We can start multiple "waiting" tasks at the same time.
async def count_to(number, delay):
    """A simple coroutine that counts up, pausing between each number."""
    for i in range(1, number + 1):
        print(f"Counting: {i}")
        await asyncio.sleep(delay)
    print("Counting finished!")

async def main_part_2():
    """Runs two counters and shows the power of concurrency."""
    print("--- Running Part 2: Concurrency with gather() ---")

    # --- First, let's run them sequentially (one after the other) to see the problem. ---
    print("\n>> Running sequentially (the slow way)...")
    start_time_seq = time.monotonic()
    await count_to(3, 1) # This will take 3 * 1 = 3 seconds
    await count_to(2, 2) # This will take 2 * 2 = 4 seconds
    end_time_seq = time.monotonic()
    print(f"Sequential run finished in {end_time_seq - start_time_seq:.2f} seconds. (Expected ~7s)")

    # --- Now, let's run them concurrently using asyncio.gather(). ---
    print("\n>> Running concurrently (the fast, async way)...")
    start_time_con = time.monotonic()
    # `asyncio.gather()` takes multiple coroutines and starts them all at roughly the same time.
    # It then waits for all of them to complete.
    await asyncio.gather(
        count_to(3, 1), # This task will run in the background
        count_to(2, 2)  # This task will also run in the background
    )
    end_time_con = time.monotonic()
    # The total time will be the time of the LONGEST task, not the sum of all tasks.
    print(f"Concurrent run finished in {end_time_con - start_time_con:.2f} seconds. (Expected ~4s)")
    print("Notice how the 'Counting' messages were interleaved!")
    print("\nPart 2 finished.\n")


# ======================================================================================================================
# PART 3: THE MOST IMPORTANT PART - INTEGRATING "BLOCKING" CODE
# ======================================================================================================================
#
# What happens when you need to use a library that wasn't designed for asyncio?
# For example, the `requests` library or your `ph.chat()` function are "blocking".
# If you call them directly, they will freeze your entire bot.
#
# The solution is `loop.run_in_executor()`. This tells the event loop:
# "Run this blocking function in a separate thread, so it doesn't freeze me."
#
# THIS IS EXACTLY HOW YOUR BOT'S `/ask-ai` AND `/tempmail` COMMANDS WORK.

def blocking_api_call(url):
    """
    This is a regular, synchronous function that simulates a slow network request.
    It is "blocking" because it uses `requests.get()`.
    """
    print(f"  [Blocking Task] Starting slow network request to {url}...")
    response = requests.get(url)
    print(f"  [Blocking Task] Finished slow network request. Status: {response.status_code}")
    return response.status_code

async def some_other_async_task():
    """A quick async task that we want to run while the blocking task is busy."""
    print("[Async Task] I can run while the blocking task is waiting!")
    await asyncio.sleep(0.5)
    print("[Async Task] Still running...")
    await asyncio.sleep(0.5)
    print("[Async Task] I'm done before the blocking task!")

async def main_part_3():
    """Shows how to correctly handle blocking code."""
    print("--- Running Part 3: Handling Blocking Code ---")
    start_time = time.monotonic()

    # Get the current asyncio event loop.
    loop = asyncio.get_running_loop()

    # We want to run our slow, blocking API call and another async task at the same time.
    await asyncio.gather(
        # `run_in_executor` takes 3 arguments:
        # 1. The executor (use `None` to use the default background thread pool).
        # 2. The blocking function to run (`blocking_api_call`).
        # 3. The arguments to pass to that function (`'https://httpbin.org/delay/2'`).
        loop.run_in_executor(None, blocking_api_call, 'https://httpbin.org/delay/2'),

        # This is our other normal async task.
        some_other_async_task()
    )

    end_time = time.monotonic()
    print(f"\nPart 3 finished in {end_time - start_time:.2f} seconds. (Expected ~2s)")
    print("Notice how the '[Async Task]' messages appeared while the '[Blocking Task]' was running!")
    print("This proves the bot was not frozen and could do other work.\n")


# ======================================================================================================================
# HOW TO RUN THIS SCRIPT
# ======================================================================================================================
#
# 1. Save this file as `asyncio_tutorial.py`.
# 2. Make sure you have `requests` installed: `pip install requests`
# 3. Run it from your terminal: `python asyncio_tutorial.py`
# 4. Follow the prompts in the terminal.
#
if __name__ == "__main__":
    # This block runs when you execute the script directly.
    # We use `asyncio.run()` to start the asyncio event loop and run our main coroutine.

    while True:
        print("=== Asyncio Tutorial ===")
        print("1. Part 1: The Basics")
        print("2. Part 2: Concurrency with gather()")
        print("3. Part 3: Handling Blocking Code (Most relevant to our bot)")
        print("4. Exit")
        choice = input("Choose a part to run (1-4): ")

        if choice == '1':
            asyncio.run(main_part_1())
        elif choice == '2':
            asyncio.run(main_part_2())
        elif choice == '3':
            asyncio.run(main_part_3())
        elif choice == '4':
            break
        else:
            print("Invalid choice, please try again.\n")
