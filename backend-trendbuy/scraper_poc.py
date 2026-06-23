import asyncio
import json

from scraper.scrapers import scrape_comparison, serialize_scraped_product


async def main() -> None:
    products = await scrape_comparison()

    print(
        json.dumps(
            {"products": [serialize_scraped_product(product) for product in products]},
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    asyncio.run(main())
