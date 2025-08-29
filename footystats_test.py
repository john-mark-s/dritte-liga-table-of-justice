# This version is fully working. It maps from the soccerway spieltag to the footystats spieltag.
# It stores it as a csv.
# Will test in the vers2 scripts the next steps:
    # 1. move into the main script and have it integrated with the spieltag mapper
    # First problem: when I delete all files it doesn't have the html.

import random
import time
import csv
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
import chromedriver_autoinstaller



USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) Gecko/20100101 Firefox/124.0",
]

URL = "https://footystats.org/germany/3-liga/fixtures"

def soccerway_to_footystats_spieltag(soccerway_spieltag):
    """
    Maps Soccerway Spieltag (1-37) to Footystats Spieltag (37-1).
    """
    return 38 - soccerway_spieltag

def get_selenium_html(url, keywords):
    chromedriver_autoinstaller.install()
    user_agent = random.choice(USER_AGENTS)
    chrome_options = Options()
    chrome_options.add_argument('--headless')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument(f'user-agent={user_agent}')
    
    # Mask referer and other headers via Chrome arguments
    chrome_options.add_argument('--disable-blink-features=AutomationControlled')
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)

    driver = webdriver.Chrome(options=chrome_options)
    driver.execute_cdp_cmd('Network.setExtraHTTPHeaders', {
        'headers': {
            'Referer': 'https://www.google.com/',
            'Accept-Language': 'en-US,en;q=0.9',
            'DNT': '1'
        }
    })
    driver.get(url)
    time.sleep(3)  # Wait for page to load

    # Screenshot
    screenshot_path = 'footystats_test_selenium.png'
    driver.save_screenshot(screenshot_path)
    print(f"Selenium screenshot saved to {screenshot_path}")

    # Save HTML
    html_path = 'footystats_test_selenium.html'
    with open(html_path, 'w', encoding='utf-8') as f:
        f.write(driver.page_source)
    print(f"Selenium HTML saved to {html_path}")

    # Filter elements containing keywords
    filtered = []
    for keyword in keywords:
        elements = driver.find_elements(By.XPATH, f"//*[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{keyword.lower()}')]")
        for el in elements:
            text = el.get_attribute('outerHTML')
            # Ignore betting-related lines
            if "win" in text.lower():
                continue
            filtered.append(text)

    # Also find links to "Tomorrow's Fixtures", "Weekend's Fixtures", or past fixtures
    extra_links = driver.find_elements(By.XPATH, "//a[contains(@class, 'rdBlock')]")
    for a in extra_links:
        link_text = a.text.lower()
        if any(x in link_text for x in ["tomorrow", "weekend", "past", "previous"]):
            filtered.append(a.get_attribute('outerHTML'))

    driver.quit()
    return filtered

def main():
    # --- Extract all matches from one game week ---
    try:
        soccerway_spieltag = 1
        footystats_spieltag = soccerway_to_footystats_spieltag(soccerway_spieltag)
        print(f"Mapping Soccerway Spieltag {soccerway_spieltag} to Footystats Spieltag {footystats_spieltag}")
        
        html_path = 'footystats_test_selenium.html'
        with open(html_path, 'r', encoding='utf-8') as f:
            html = f.read()
        soup = BeautifulSoup(html, 'html.parser')
        week_div = soup.find('div', {'data-game-week': str(footystats_spieltag)})
        print(week_div)
        if not week_div:
            print(f'No game week {footystats_spieltag} found!')
            return
        matches = []
        for match_ul in week_div.select('ul.match.row'):
            home_a = match_ul.select_one('a.team.home')
            home_team = None
            if home_a:
                home_span = home_a.select_one('span.hover-modal-parent')
                if home_span:
                    home_team = home_span.get_text(strip=True)
            away_a = match_ul.select_one('a.team.away')
            away_team = None
            if away_a:
                away_span = away_a.select_one('span.hover-modal-parent')
                if away_span:
                    away_team = away_span.get_text(strip=True)
            h2h_a = match_ul.select_one('a.h2h-link')
            score_home = None
            score_away = None
            url = None
            if h2h_a:
                score_span = h2h_a.select_one('span.ft-score')
                if score_span:
                    score_text = score_span.get_text(strip=True)
                    if score_text and '-' in score_text:
                        parts = score_text.split('-')
                        if len(parts) == 2:
                            score_home = parts[0].strip()
                            score_away = parts[1].strip()
                url = 'https://footystats.org' + h2h_a['href']
            matches.append({
                'home_team': home_team,
                'away_team': away_team,
                'score_home': score_home,
                'score_away': score_away,
                'url': url
            })
        print(f"Found {len(matches)} matches in game week {footystats_spieltag}:")
        for match in matches:
            print(f"Home: {match['home_team']}")
            print(f"Away: {match['away_team']}")
            print(f"Score Home: {match['score_home']}")
            print(f"Score Away: {match['score_away']}")
            print(f"URL: {match['url']}")
            print()
        csv_path = f'matches_gameweek_{soccerway_spieltag}.csv'
        with open(csv_path, 'w', newline='', encoding='utf-8') as csvfile:
            fieldnames = ['home_team', 'away_team', 'score_home', 'score_away', 'url']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            for match in matches:
                writer.writerow(match)
        print(f"Matches exported to {csv_path}")
    except Exception as e:
        print(f"Error in main(): {e}")

if __name__ == "__main__":
    main()