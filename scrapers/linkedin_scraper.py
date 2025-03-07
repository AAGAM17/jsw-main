import logging
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, WebDriverException
from config.settings import Config
import random

class LinkedInScraper:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.driver = None
        self.max_retries = 3
        self.retry_delay = 5  # seconds
        
    def _init_driver(self):
        """Initialize Chrome driver with necessary options"""
        try:
            if self.driver:
                try:
                    self.driver.quit()
                except:
                    pass
                    
            options = webdriver.ChromeOptions()
            options.add_argument('--headless')
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--disable-gpu')
            options.add_argument('--window-size=1920x1080')
            options.add_argument('--disable-blink-features=AutomationControlled')
            options.add_argument(f'user-agent={Config.USER_AGENT}')
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            options.add_experimental_option('useAutomationExtension', False)
            
            self.driver = webdriver.Chrome(options=options)
            self.driver.execute_cdp_cmd('Network.setUserAgentOverride', {"userAgent": Config.USER_AGENT})
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            self.driver.implicitly_wait(10)
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to initialize Chrome driver: {str(e)}")
            return False
            
    def _login(self):
        """Login to LinkedIn with retry logic"""
        for attempt in range(self.max_retries):
            try:
                self.driver.get('https://www.linkedin.com/login')
                time.sleep(random.uniform(2, 4))  # Random delay
                
                # Wait for login form
                email_field = WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.ID, "username"))
                )
                password_field = self.driver.find_element(By.ID, "password")
                
                # Enter credentials with human-like typing
                self._type_like_human(email_field, Config.LINKEDIN_EMAIL)
                time.sleep(random.uniform(0.5, 1.5))
                self._type_like_human(password_field, Config.LINKEDIN_PASSWORD)
                time.sleep(random.uniform(0.5, 1.5))
                
                password_field.send_keys(Keys.RETURN)
                time.sleep(random.uniform(3, 5))
                
                # Verify login success
                if "feed" in self.driver.current_url or "checkpoint" in self.driver.current_url:
                    return True
                    
            except Exception as e:
                self.logger.error(f"Login attempt {attempt + 1} failed: {str(e)}")
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay * (attempt + 1))
                    self._init_driver()  # Reinitialize driver for next attempt
                    
        return False
            
    def _type_like_human(self, element, text):
        """Type text with random delays between keystrokes"""
        for char in text:
            element.send_keys(char)
            time.sleep(random.uniform(0.1, 0.3))
            
    def search_company_employees(self, company_name, roles=None):
        """Search for employees at a company with specific roles"""
        results = []
        try:
            if not self.driver and not self._init_driver():
                return results
                
            if not self._login():
                self.logger.error("Failed to login to LinkedIn")
                return results
                
            # Build search query
            search_query = f'"{company_name}"'
            if roles:
                role_query = ' OR '.join(f'"{role}"' for role in roles)
                search_query = f'{search_query} ({role_query})'
            
            # Navigate to search with retry logic
            for attempt in range(self.max_retries):
                try:
                    search_url = f'https://www.linkedin.com/search/results/people/?keywords={search_query}&origin=GLOBAL_SEARCH_HEADER'
                    self.driver.get(search_url)
                    time.sleep(random.uniform(3, 5))
                    
                    # Wait for results to load
                    WebDriverWait(self.driver, 10).until(
                        EC.presence_of_element_located((By.CLASS_NAME, "reusable-search__result-container"))
                    )
                    
                    # Extract results from first page only to avoid detection
                    profile_cards = self.driver.find_elements(By.CLASS_NAME, "reusable-search__result-container")
                    
                    for card in profile_cards[:5]:  # Limit to top 5 results
                        try:
                            name = card.find_element(By.CLASS_NAME, "entity-result__title-text").text.strip()
                            title = card.find_element(By.CLASS_NAME, "entity-result__primary-subtitle").text.strip()
                            profile_url = card.find_element(By.CLASS_NAME, "app-aware-link").get_attribute("href")
                            
                            if profile_url:
                                profile_url = profile_url.split('?')[0]  # Remove URL parameters
                                results.append({
                                    'name': name,
                                    'title': title,
                                    'profile_url': profile_url
                                })
                            
                        except NoSuchElementException:
                            continue
                            
                    break  # Success, exit retry loop
                    
                except Exception as e:
                    self.logger.error(f"Search attempt {attempt + 1} failed: {str(e)}")
                    if attempt < self.max_retries - 1:
                        time.sleep(self.retry_delay * (attempt + 1))
                        self._init_driver()
                        self._login()
            
            return results
            
        except Exception as e:
            self.logger.error(f"LinkedIn search failed for {company_name}: {str(e)}")
            return results
            
        finally:
            if self.driver:
                try:
                    self.driver.quit()
                except:
                    pass
                self.driver = None
    
    def get_profile_details(self, profile_url):
        """Get detailed information from a LinkedIn profile"""
        try:
            if not self.driver and not self._init_driver():
                return None
                
            if not self._login():
                self.logger.error("Failed to login to LinkedIn")
                return None
            
            # Visit profile with retry logic
            for attempt in range(self.max_retries):
                try:
                    self.driver.get(profile_url)
                    time.sleep(random.uniform(3, 5))
                    
                    # Extract profile information
                    profile_info = {}
                    
                    try:
                        profile_info['name'] = WebDriverWait(self.driver, 10).until(
                            EC.presence_of_element_located((By.CLASS_NAME, "text-heading-xlarge"))
                        ).text.strip()
                    except:
                        profile_info['name'] = ""
                        
                    try:
                        profile_info['title'] = self.driver.find_element(By.CLASS_NAME, "text-body-medium").text.strip()
                    except:
                        profile_info['title'] = ""
                        
                    try:
                        profile_info['location'] = self.driver.find_element(By.CLASS_NAME, "text-body-small").text.strip()
                    except:
                        profile_info['location'] = ""
                    
                    return profile_info
                    
                except Exception as e:
                    self.logger.error(f"Profile fetch attempt {attempt + 1} failed: {str(e)}")
                    if attempt < self.max_retries - 1:
                        time.sleep(self.retry_delay * (attempt + 1))
                        self._init_driver()
                        self._login()
            
            return None
            
        except Exception as e:
            self.logger.error(f"Failed to get profile details from {profile_url}: {str(e)}")
            return None
            
        finally:
            if self.driver:
                try:
                    self.driver.quit()
                except:
                    pass
                self.driver = None 