import httpx

http_client = httpx.AsyncClient()


async def close_http_client() -> None:
    await http_client.aclose()
