#!/usr/bin/env python3
# Chrome utilities for web scraping with stability in Azure/Docker

import os
import sys
import time
import random
import logging
import platform
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(name)s - %(message)s'
)
logger = logging.getLogger(__name__)

def setup_chrome_driver(headless=True, download_dir=None):
    try:
        logger.info("Setting up Chrome driver for cloud/Docker environment...")

        is_azure = os.environ.get('WEBSITE_SITE_NAME') is not None
        is_container = is_azure or 'DOCKER_CONTAINER' in os.environ or os.path.exists('/.dockerenv')
        is_macos = platform.system() == "Darwin"

        logger.info(f"Environment detection: Azure={is_azure}, Container={is_container}, macOS={is_macos}")

        if is_container and not headless:
            logger.info("Running in container environment - forcing headless mode")
            headless = True

        logger.info(f"Using headless mode: {headless}")

        options = Options()
        
        # Critical core stability flags for all environments
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--disable-setuid-sandbox")
        options.add_argument("--disable-extensions")
        options.add_argument("--disable-background-networking")
        options.add_argument("--disable-default-apps")
        options.add_argument("--disable-sync")
        options.add_argument("--disable-translate")
        options.add_argument("--metrics-recording-only")
        options.add_argument("--mute-audio")
        options.add_argument("--no-first-run")
        
        # Performance settings
        options.add_argument("--disable-background-timer-throttling")
        options.add_argument("--disable-backgrounding-occluded-windows")
        options.add_argument("--disable-client-side-phishing-detection")
        options.add_argument("--disable-popup-blocking")
        
        # User agent and window settings
        options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36")
        options.add_argument("--window-size=1920,1080")
        
        # Initialize preferences dictionary
        prefs = {
            "download.default_directory": download_dir if download_dir else "/tmp",
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
            "safebrowsing.enabled": False,
            "plugins.always_open_pdf_externally": True,
            # Performance preferences
            "profile.default_content_setting_values.images": 2,  # Don't load images for better performance
            "profile.default_content_setting_values.cookies": 1,  # Accept cookies
            "profile.managed_default_content_settings.javascript": 1,  # Enable JavaScript
            # Network timeouts
            "network.tcp.connect_timeout_ms": 30000  # 30 seconds for more stability
        }
        
        # Special configuration for Azure
        if is_azure:
            logger.info("Using Azure-specific Chrome configuration")
            options.page_load_strategy = 'eager'
            
            # Critical for Azure stability
            options.add_argument("--disable-gpu-sandbox")
            options.add_argument("--disable-web-security")
            
            # Add more critical rendering settings
            options.add_argument("--disable-hang-monitor")
            options.add_argument("--disable-crash-reporter")
            
            # Network and loading optimizations for Azure
            options.add_argument("--disable-features=NetworkService,NetworkServiceInProcess")
            options.add_argument("--disk-cache-size=33554432")  # 32MB disk cache
            options.add_argument("--media-cache-size=33554432")  # 32MB media cache

            # Headless mode for Azure
            if headless:
                options.add_argument("--headless=new")
            
            # Azure-specific environment variables
            logger.info("Setting special environment variables for Azure")
            os.environ['CHROME_HEADLESS'] = '1'
            os.environ['PYTHONUNBUFFERED'] = '1'
            os.environ['PYTHONASYNCIODEBUG'] = '0'
        
        # Container but not Azure (like local Docker on Mac M2)
        elif is_container:
            logger.info("Using general container Chrome configuration")
            if headless:
                options.add_argument("--headless=new")
                
                # Additional flags for stability on ARM64 emulation (Mac M2)
                if is_macos:
                    options.add_argument("--single-process")  # More stable for emulation
                    options.add_argument("--incognito")  # Prevents profile issues
        
        # Apply download directory settings if provided
        if download_dir:
            download_dir = os.path.abspath(download_dir)
            os.makedirs(download_dir, exist_ok=True)
            if is_container:
                try:
                    os.chmod(download_dir, 0o777)
                except Exception as e:
                    logger.warning(f"Could not set permissions on download directory: {e}")

            prefs["download.default_directory"] = download_dir

        # Apply preferences to options
        options.add_experimental_option("prefs", prefs)

        # Log all configuration options
        logger.info("Chrome Options:")
        for arg in options.arguments:
            logger.info(f"  {arg}")

        # Configure service with appropriate path
        service = Service(executable_path="/usr/bin/chromedriver") if is_container else None
        
        # Set service arguments for logging
        if is_container and service:
            service.service_args = ['--log-level=INFO']
        
        # Create Chrome driver
        driver = webdriver.Chrome(service=service, options=options)
        
        # Set window size in a try-except block for stability
        try:
            driver.set_window_size(1920, 1080)
        except Exception as e:
            logger.warning(f"Could not set window size, but continuing: {e}")
        
        # Set timeouts in a try-except block for stability
        try:
            driver.set_page_load_timeout(120)  # 2 minutes for stability
            driver.set_script_timeout(60)      # 1 minute for stability
        except Exception as e:
            logger.warning(f"Could not set timeouts, but continuing: {e}")

        # Configure download behavior in headless mode
        if headless and download_dir:
            try:
                driver.execute_cdp_cmd('Page.setDownloadBehavior', {
                    'behavior': 'allow',
                    'downloadPath': download_dir
                })
            except Exception as e:
                logger.warning(f"CDP download behavior setup failed: {e}")

        logger.info("Chrome WebDriver initialized successfully")
        return driver

    except Exception as e:
        logger.error(f"Chrome setup failed: {e}")
        import traceback
        logger.error(traceback.format_exc())
        
        # Return None instead of exiting so the calling code can handle the failure
        return None


def random_wait(min_seconds=0.5, max_seconds=2):
    wait_time = min_seconds + random.random() * (max_seconds - min_seconds)
    time.sleep(wait_time)
    return wait_time

def create_wait(driver, timeout=10):
    return WebDriverWait(driver, timeout)

if __name__ == "__main__":
    driver = setup_chrome_driver(headless=True)
    try:
        driver.get("https://www.google.com")
        logger.info(f"Test successful: {driver.title}")
    except Exception as e:
        logger.error(f"Test failed: {e}")
    finally:
        driver.quit()