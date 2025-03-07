import requests # type: ignore
from requests_html import HTMLSession # type: ignore
from bs4 import BeautifulSoup # type: ignore
import logging
from config.settings import Config

class BaseScraper:
    def __init__(self):
        self.headers = {'User-Agent': Config.USER_AGENT}
        self.session = HTMLSession()
        self.logger = logging.getLogger(__name__)

    def fetch_page(self, url, render_js=False):
        try:
            if render_js:
                response = self.session.get(url, headers=self.headers, timeout=Config.REQUEST_TIMEOUT)
                response.html.render(timeout=20)
                return response.html.html
            else:
                response = requests.get(url, headers=self.headers, timeout=Config.REQUEST_TIMEOUT)
                response.raise_for_status()
                return response.text
        except Exception as e:
            self.logger.error(f"Error fetching {url}: {str(e)}")
            return None