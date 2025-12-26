import os
import time
import random
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional
import urllib.parse

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException, 
    NoSuchElementException, 
    StaleElementReferenceException,
    ElementClickInterceptedException
)

from dotenv import load_dotenv

# Import our backend components
# Note: These imports assume the package structure is set up correctly.
# If running this script directly, you might need to adjust python path.
try:
    from backend.llm_analyzer import LLMAnalyzer
    from utils.database import save_job_listings, get_skills_gap_analysis, get_user_analysis
except ImportError:
    # Fallback for direct execution/testing
    import sys
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from backend.llm_analyzer import LLMAnalyzer
    from utils.database import save_job_listings, get_skills_gap_analysis, get_user_analysis

load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("scraper.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# --------------------------------------------------
# WebDriver Setup
# --------------------------------------------------
def get_driver(headless=False, user_agent=None):
    options = Options()
    if headless:
        options.add_argument("--headless=new")
    
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-notifications")
    options.add_argument("--start-maximized")

    if user_agent:
        options.add_argument(f"user-agent={user_agent}")
    else:
        # Default modern user agent
        options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

    # Path to chromedriver - adjust if needed or use webdriver_manager
    chromedriver_path = r"C:\ChromeDriver\chromedriver.exe"
    if os.path.exists(chromedriver_path):
        service = Service(chromedriver_path)
        driver = webdriver.Chrome(service=service, options=options)
    else:
        # Fallback to default path (assumes in PATH)
        driver = webdriver.Chrome(options=options)
        
    return driver

# --------------------------------------------------
# Utilities
# --------------------------------------------------
def human_typing(element, text):
    """Simulate human typing with random delays."""
    for ch in text:
        element.send_keys(ch)
        time.sleep(random.uniform(0.05, 0.15))
    time.sleep(random.uniform(0.3, 0.6))

def random_sleep(min_seconds=1.0, max_seconds=3.0):
    time.sleep(random.uniform(min_seconds, max_seconds))

# --------------------------------------------------
# LinkedIn Scraper Class
# --------------------------------------------------
class LinkedInJobScraper:
    def __init__(self, user_id=None, headless=False):
        self.user_id = user_id
        self.driver = get_driver(headless=headless)
        self.wait = WebDriverWait(self.driver, 20)
        self.llm_analyzer = LLMAnalyzer()
        self.base_url = "https://www.linkedin.com"
        
    def login(self, email, password):
        """Login to LinkedIn."""
        logger.info(f"Logging in as {email}...")
        try:
            self.driver.get(f"{self.base_url}/login")
            
            email_elem = self.wait.until(EC.presence_of_element_located((By.ID, "username")))
            human_typing(email_elem, email)
            
            pass_elem = self.driver.find_element(By.ID, "password")
            human_typing(pass_elem, password)
            
            pass_elem.send_keys(Keys.RETURN)
            
            # Wait for feed or challenge
            try:
                WebDriverWait(self.driver, 15).until(EC.url_contains("/feed"))
                logger.info("Login successful.")
                return True
            except TimeoutException:
                if "checkpoint" in self.driver.current_url:
                    logger.warning("LinkedIn security checkpoint detected. Manual intervention required.")
                    input("Press Enter after solving the CAPTCHA in the browser...")
                    return True
                logger.error("Login failed or timed out.")
                return False
                
        except Exception as e:
            logger.error(f"Login error: {e}")
            return False

    def search_jobs(self, keywords: str, location: str, limit: int = 20, filters: Optional[Dict[str, Any]] = None):
        """
        Navigate to jobs page and search with filters.
        
        Args:
            keywords: e.g. "Software Engineer Python"
            location: e.g. "San Francisco, CA"
            limit: Max jobs to scrape
            filters: Dict with optional keys:
                - date_posted: "24h", "week", "month"
                - experience: list of ["internship", "entry", "associate", "mid_senior", "director", "executive"]
                - job_type: list of ["full_time", "contract", "part_time", "temporary", "internship", "volunteer", "other"]
                - remote: list of ["on_site", "remote", "hybrid"]
        """
        logger.info(f"Searching for '{keywords}' in '{location}' with filters: {filters}")
        
        # Base query params
        query_params = {
            "keywords": keywords,
            "location": location,
        }
        
        # Helper to map filters to LinkedIn URL params
        if filters:
            # Date Posted (f_TPR)
            date_map = {"24h": "r86400", "week": "r604800", "month": "r2592000"}
            if filters.get("date_posted") in date_map:
                query_params["f_TPR"] = date_map[filters["date_posted"]]
                
            # Experience Level (f_E)
            exp_map = {
                "internship": "1", "entry": "2", "associate": "3", 
                "mid_senior": "4", "director": "5", "executive": "6"
            }
            if filters.get("experience"):
                # Handle single string or list
                exps = filters["experience"] if isinstance(filters["experience"], list) else [filters["experience"]]
                codes = [exp_map[e] for e in exps if e in exp_map]
                if codes:
                    query_params["f_E"] = ",".join(codes)
                    
            # Remote Filter (f_WT)
            remote_map = {"on_site": "1", "remote": "2", "hybrid": "3"}
            if filters.get("remote"):
                remotes = filters["remote"] if isinstance(filters["remote"], list) else [filters["remote"]]
                codes = [remote_map[r] for r in remotes if r in remote_map]
                if codes:
                    query_params["f_WT"] = ",".join(codes)

            # Job Type (f_JT)
            type_map = {
                "full_time": "F", "part_time": "P", "contract": "C", 
                "temporary": "T", "internship": "I", "volunteer": "V", "other": "O"
            }
            if filters.get("job_type"):
                types = filters["job_type"] if isinstance(filters["job_type"], list) else [filters["job_type"]]
                codes = [type_map[t] for t in types if t in type_map]
                if codes:
                    query_params["f_JT"] = ",".join(codes)

        # Construct URL
        query_string = urllib.parse.urlencode(query_params, safe=",")
        search_url = f"{self.base_url}/jobs/search/?{query_string}"
        
        logger.info(f"Navigating to: {search_url}")
        self.driver.get(search_url)
        random_sleep(3, 5)
        
        return self._scrape_job_list(limit)

    def _scrape_job_list(self, limit: int) -> List[Dict]:
        """Iterate through job list and extract details."""
        scraped_jobs = []
        page = 1
        
        while len(scraped_jobs) < limit:
            logger.info(f"Scraping page {page}, collected {len(scraped_jobs)}/{limit} jobs...")
            
            # Wait for job list to load
            try:
                # Common selectors for job cards
                # These classes change frequently. Using clearer attributes if available.
                job_card_selector = ".job-card-container, li.jobs-search-results__list-item"
                self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, job_card_selector)))
                
                # Scroll the list to load lazy-loaded elements
                job_list_container = self.driver.find_elements(By.CSS_SELECTOR, ".jobs-search-results-list")
                if job_list_container:
                    # Scroll within the sidebar container
                    js_script = "arguments[0].scrollTop = arguments[0].scrollTop + 500;"
                    for _ in range(5):
                        self.driver.execute_script(js_script, job_list_container[0])
                        time.sleep(0.5)
                else:
                    # Generic window scroll
                    self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight / 2);")
                
                random_sleep(1, 2)
                
                # Find job cards
                job_cards = self.driver.find_elements(By.CSS_SELECTOR, job_card_selector)
                
                for card in job_cards:
                    if len(scraped_jobs) >= limit:
                        break
                        
                    try:
                        # Extract basic info
                        title_elem = card.find_element(By.CSS_SELECTOR, ".job-card-list__title, strong")
                        job_title = title_elem.text.strip()
                        
                        # Click to load details
                        # We need to scroll to element and click
                        self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", card)
                        try:
                            card.click()
                        except ElementClickInterceptedException:
                            # Try JS click
                            self.driver.execute_script("arguments[0].click();", card)
                            
                        random_sleep(1, 2) # Wait for details pane to load
                        
                        # Parse details
                        job_details = self._extract_job_details_pane(job_title)
                        
                        if job_details:
                            # Use LLM to structure the description
                            # To save tokens/time, we can optionally skip LLM if just grabbing raw text is enough initially
                            # But requirement says "Use LLM to parse"
                            
                            logger.info(f"Parsing description for: {job_title}")
                            parsed_data = self.llm_analyzer.parse_job_description(job_details['raw_description'])
                            
                            # Merge parsed data
                            if "error" not in parsed_data:
                                job_details.update(parsed_data)
                            
                            scraped_jobs.append(job_details)
                            
                            # Save immediately to DB if user_id is set
                            if self.user_id:
                                save_job_listings(self.user_id, [job_details])
                                
                    except Exception as e:
                        logger.warning(f"Failed to scrape a job card: {e}")
                        continue
                
                # Pagination
                # Look for "Next" button
                # Button usually has aria-label="Page 2" etc or "Next" text
                try:
                    next_button = self.driver.find_element(By.CSS_SELECTOR, "button[aria-label*='Next']")
                    self.driver.execute_script("arguments[0].scrollIntoView();", next_button)
                    next_button.click()
                    page += 1
                    random_sleep(3, 5)
                except NoSuchElementException:
                    logger.info("No more pages found.")
                    break
                    
            except TimeoutException:
                logger.warning("Timeout waiting for job list.")
                break
            except Exception as e:
                logger.error(f"Error during scraping loop: {e}")
                break
                
        return scraped_jobs

    def _extract_job_details_pane(self, job_title_fallback):
        """Extract info from the right-hand details pane."""
        try:
            # Wait for details container
            details_selector = ".jobs-search__job-details--container, .job-view-layout"
            self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, details_selector)))
            
            # URL
            try:
                # Sometimes the URL is in a 'share' button or the title link in the pane
                link_elem = self.driver.find_element(By.CSS_SELECTOR, ".job-details-jobs-unified-top-card__job-title a, .jobs-unified-top-card__job-title a")
                job_url = link_elem.get_attribute("href").split('?')[0] # Clean URL
            except:
                job_url = self.driver.current_url # Fallback
            
            # Company
            try:
                company = self.driver.find_element(By.CSS_SELECTOR, ".job-details-jobs-unified-top-card__company-name, .jobs-unified-top-card__company-name").text.strip()
            except:
                company = "Unknown"
                
            # Location
            try:
                location = self.driver.find_element(By.CSS_SELECTOR, ".job-details-jobs-unified-top-card__bullet, .jobs-unified-top-card__bullet").text.strip()
            except:
                location = "Unknown"
            
            # Full Description
            try:
                description_box = self.driver.find_element(By.ID, "job-details")
                description = description_box.text.strip()
                
                # Check for "Show more" button in description
                try:
                    show_more = description_box.find_element(By.CSS_SELECTOR, "button[aria-label*='Show more']")
                    show_more.click()
                    random_sleep(0.5, 1)
                    description = description_box.text.strip()
                except:
                    pass
            except:
                description = ""
                
            return {
                "job_title": job_title_fallback,
                "company_name": company,
                "location": location,
                "job_description": description, # Used for storage
                "raw_description": description, # Used for LLM
                "job_url": job_url,
                "match_percentage": 0 # To be calculated later
            }
            
        except Exception as e:
            logger.error(f"Error extracting job details pane: {e}")
            return None

    def scrape_recommended_jobs(self, user_id: int, limit: int = 10):
        """
        Automatically scrape jobs based on user's profile.
        """
        logger.info(f"Starting automated scrape for user {user_id}...")
        
        # 1. Try to get target role from gap analysis
        gap_analysis = get_skills_gap_analysis(user_id)
        # gap_analysis might be a list or direct dict depending on my earlier check
        # The DB function returns a list if limit > 1, or single item/None if limit=1. 
        # But wait, get_skills_gap_analysis signature in db.py: def get_skills_gap_analysis(user_id, limit=1...)
        # It returns results[0] if limit=1.
        
        target_role = None
        if gap_analysis:
            target_role = gap_analysis.get("target_role")
            
        # 2. If no target role, try to infer from resume analysis
        if not target_role:
            analysis = get_user_analysis(user_id)
            if analysis:
                # Naive inference: pop top skill or use a default
                # Ideally we'd ask LLM to infer job title from resume text, 
                # but for now let's assume if they haven't done gap analysis they might just want general "Software" jobs
                # or use the first technical skill
                skills = analysis.get("skills", {})
                tech_skills = skills.get("technical_skills", [])
                if tech_skills:
                    target_role = f"{tech_skills[0]} Developer"
        
        # 3. Default
        if not target_role:
            target_role = "Software Engineer"
            
        logger.info(f"inferred search keywords: {target_role}")
        
        # Location preference - placeholder (could be stored in user profile)
        location = "Remote" 
        
        # Execute search
        return self.search_jobs(target_role, location, limit=limit, filters={"remote": ["remote", "hybrid"]})

    def close(self):
        if self.driver:
            self.driver.quit()

# --------------------------------------------------
# Main Execution (Testing)
# --------------------------------------------------
if __name__ == "__main__":
    email = os.getenv("LINKEDIN_EMAIL")
    password = os.getenv("LINKEDIN_PASSWORD")
    
    if not email or not password:
        logger.error("Please set LINKEDIN_EMAIL and LINKEDIN_PASSWORD env vars.")
        exit(1)
        
    scraper = LinkedInJobScraper(user_id=1, headless=False)
    try:
        if scraper.login(email, password):
            jobs = scraper.search_jobs("Python Developer", "Remote", limit=5)
            logger.info(f"Scraped {len(jobs)} jobs.")
            # print(json.dumps(jobs, indent=2))
    finally:
        scraper.close()
