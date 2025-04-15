# backend/network_scanner.py
import asyncio
import aiohttp
import logging

class NetworkScanner:
    def __init__(self, concurrency=5, max_requests=100, timeout=30):
        self.concurrency = concurrency
        self.max_requests = max_requests
        self.timeout = timeout
        self.logger = logging.getLogger(__name__)
        
    async def scan_url(self, url):
        # Use asyncio to make concurrent requests
        tasks = []
        async with aiohttp.ClientSession() as session:
            for _ in range(self.concurrency):
                tasks.append(self.fetch_with_timeout(session, url))
                
            return await asyncio.gather(*tasks)
            
    async def fetch_with_timeout(self, session, url):
        try:
            start_time = asyncio.get_event_loop().time()
            async with session.get(url, timeout=self.timeout) as response:
                duration = (asyncio.get_event_loop().time() - start_time) * 1000
                # Process response
                return {
                    'url': url,
                    'status_code': response.status,
                    'headers': dict(response.headers),
                    'duration': duration,
                    'content_type': response.headers.get('content-type')
                }
        except Exception as e:
            self.logger.error(f"Error scanning {url}: {str(e)}")
            return {
                'url': url,
                'error': str(e),
                'anomaly_type': 'connection_error'
            }