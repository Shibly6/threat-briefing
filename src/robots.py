from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser
import httpx

class RobotsChecker:
    def __init__(self, user_agent: str, timeout: float = 5.0):
        self.user_agent = user_agent
        self.timeout = timeout
        self._parsers = {}

    def is_allowed(self, url: str) -> bool:
        parsed = urlparse(url)
        base_url = f"{parsed.scheme}://{parsed.netloc}"
        robots_url = f"{base_url}/robots.txt"

        if base_url not in self._parsers:
            parser = RobotFileParser()
            try:
                with httpx.Client(timeout=self.timeout, follow_redirects=True) as client:
                    resp = client.get(robots_url, headers={"User-Agent": self.user_agent})
                    if resp.status_code == 200:
                        parser.parse(resp.text.splitlines())
                    else:
                        parser.allow_all = True
            except Exception:
                # If robots.txt cannot be retrieved, default to allowing fetch
                parser.allow_all = True
            self._parsers[base_url] = parser

        return self._parsers[base_url].can_fetch(self.user_agent, url)