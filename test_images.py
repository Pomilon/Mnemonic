import asyncio
from ddgs import DDGS

async def test_images():
    with DDGS() as ddgs:
        results = [r for r in ddgs.images("nebula", max_results=5)]
        for r in results:
            print(f"Title: {r.get('title')}")
            print(f"Image: {r.get('image')}")
            print(f"Thumb: {r.get('thumbnail')}")
            print("-" * 20)

if __name__ == "__main__":
    asyncio.run(test_images())
