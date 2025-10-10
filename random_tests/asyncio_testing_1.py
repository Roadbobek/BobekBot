import asyncio

async def say_hello():
    print("Hello...")
    await asyncio.sleep(2)  # Pretend this is a 2-second network request
    print("...World!")

async def main():
    # Run multiple greetings at the same time
    await asyncio.gather(
        say_hello(),
        say_hello()
    )

# This is how you run the main async function
asyncio.run(main())