import requests
import json
import time
import csv
import pandas as pd
from dotenv import load_dotenv
import os
from playwright.sync_api import sync_playwright

# Load credentials
load_dotenv()
NAUKRI_EMAIL = os.getenv("NAUKRI_EMAIL")
NAUKRI_PASSWORD = os.getenv("NAUKRI_PASSWORD")

# Ask the user for a job keyword
job_keyword = input("Enter the job keyword (e.g., Python Developer, Data Scientist): ").strip()

# Define base API endpoint
BASE_URL = "https://www.naukri.com/jobapi/v3/search"
HEADERS = {
    "accept": "application/json",
    "appid": "109",
    "SystemId": "Naukri",
    "clientid": "d3skt0p",
    "content-type": "application/json",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36"
}

CSV_FILE = "job_links.csv"
STORAGE_FILE = "storage_state.json"  # File to save session
PAGES_TO_FETCH = 10  # Adjust as needed


def scrape_job_links():
    """Fetches job links from Naukri based on user input and saves them to a CSV file."""
    total_job_links = []

    for page in range(1, PAGES_TO_FETCH + 1):
        url = f"{BASE_URL}?noOfResults=100&urlType=search_by_keyword&searchType=adv&keyword={job_keyword.replace(' ', '%20')}&pageNo={page}&experience=0"
        response = requests.get(url, headers=HEADERS)
        
        if response.status_code == 200:
            data = response.json()
            jobs = data.get("jobDetails", [])
            
            for job in jobs:
                if job.get("jdURL"):
                    job_url = f'https://www.naukri.com{job["jdURL"]}'
                    total_job_links.append([job_url])
            
            print(f"Fetched {len(jobs)} jobs from page {page} (Total links: {len(total_job_links)})")
        else:
            print(f"Failed to fetch page {page}. Status: {response.status_code}")
        
        time.sleep(1)  # Pause to avoid rate limiting

    with open(CSV_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Job Link"])
        writer.writerows(total_job_links)
    
    print(f"\nTotal job links saved: {len(total_job_links)}")


def save_login_state():
    """Logs in once and saves session state."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()
        
        page.goto("https://www.naukri.com/nlogin/login")
        page.fill('input[placeholder="Enter Email ID / Username"]', NAUKRI_EMAIL)
        page.fill('input[placeholder="Enter Password"]', NAUKRI_PASSWORD)
        page.get_by_role("button", name="Login", exact=True).click()
        
        page.wait_for_url("https://www.naukri.com/mnjuser/homepage", timeout=20000)
        print("✅ Login successful! Saving session...")
        
        page.context.storage_state(path=STORAGE_FILE)
        print(f"📁 Session saved to {STORAGE_FILE}")
        browser.close()


def apply_for_jobs():
    """Uses saved session to apply for jobs and removes links immediately after processing."""
    if not os.path.exists(CSV_FILE):
        print("⚠️ No job links found!")
        return
    
    df = pd.read_csv(CSV_FILE)
    job_links = df["Job Link"].tolist()
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        
        if os.path.exists(STORAGE_FILE):
            print(f"🔄 Using saved session: {STORAGE_FILE}")
            context = browser.new_context(storage_state=STORAGE_FILE)
        else:
            print("⚠️ No session found! Logging in again...")
            save_login_state()
            context = browser.new_context(storage_state=STORAGE_FILE)
        
        page = context.new_page()
        page.goto("https://www.naukri.com/mnjuser/homepage", wait_until="networkidle")
        
        if "nlogin/login" in page.url:
            print("❌ Session invalid! Logging in again...")
            save_login_state()
            context = browser.new_context(storage_state=STORAGE_FILE)
            page = context.new_page()
            page.goto("https://www.naukri.com/mnjuser/homepage", wait_until="networkidle")
        
        print("✅ Logged in with session. Now applying to jobs...")
        
        for index, job_link in enumerate(job_links, start=1):
            print(f"🔗 Opening job {index}: {job_link}")
            page.goto(job_link, wait_until="networkidle")
            time.sleep(5)
            
            if "naukri.com/mnjuser/homepage" in page.url:
                print(f"⚠️ Redirected back to homepage! Skipping job {index}...")
            else:
                try:
                    page.wait_for_selector("#apply-button", timeout=5000)
                    apply_button = page.locator("#apply-button").first
                    
                    if apply_button.is_visible():
                        apply_button.click()
                        print(f"✅ Applied for job {index}")
                    else:
                        print(f"❌ Apply button not found for job {index}")
                except Exception as e:
                    print(f"❌ Error applying for job {index}: {e}")
            
            df = df[df["Job Link"] != job_link]
            df.to_csv(CSV_FILE, index=False)
            print(f"✅ Removed job link {index} from CSV")
            time.sleep(3)
        
        print("🎯 Application process completed!")
        time.sleep(10)
        browser.close()


if __name__ == "__main__":
    scrape_job_links()  # First scrape job links
    apply_for_jobs()    # Then apply for jobs
