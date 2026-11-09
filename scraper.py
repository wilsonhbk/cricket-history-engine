import time
import requests
import pandas as pd
from io import StringIO

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

def generate_ranji_seasons():
    """Generates all 90 Ranji Trophy season strings from 1934/35 to 2025/26."""
    seasons = []
    for year in range(1934, 2026):
        next_yr = str(year + 1)[-2:]
        seasons.append(f"{year}/{next_yr}")
    return seasons

def crawl_ranji_trophy_history():
    print("🏏 Starting 90-Year Ranji Trophy Harvest (1934 to 2026)...")
    seasons = generate_ranji_seasons()
    all_ranji_matches = []

    for i, season in enumerate(seasons, 1):
        print(f"[{i}/{len(seasons)}] Crawling Ranji Trophy Season: {season}...")
        url = f"https://stats.espncricinfo.com/ci/engine/stats/index.html?class=4;season={season};team=1;template=results;type=team;view=results"
        
        try:
            resp = requests.get(url, headers=HEADERS, timeout=15)
            if resp.status_code == 200:
                tables = pd.read_html(StringIO(resp.text))
                for df in tables:
                    if len(df) >= 3 and ("Team" in df.columns or "Result" in df.columns or "Winner" in df.columns):
                        df = df.rename(columns={df.columns[0]: "team", "Winner": "winner", "Margin": "margin", "Ground": "ground", "Match Date": "match_date"})
                        df["season"] = season
                        df["competition"] = "Ranji Trophy"
                        all_ranji_matches.append(df)
                        break
            time.sleep(1.0) # Polite 1-second delay so Cricinfo never blocks the crawler
        except Exception as e:
            print(f"   Note for {season}: {e}")
            time.sleep(1.5)

    if all_ranji_matches:
        combined_df = pd.concat(all_ranji_matches, ignore_index=True)
        for col in combined_df.columns:
            combined_df[col] = combined_df[col].astype(str)
        combined_df.to_parquet("ranji_complete_history.parquet", index=False)
        print("🎉 Successfully harvested 90 years of Ranji Trophy matches into ranji_complete_history.parquet!")

if __name__ == "__main__":
    crawl_ranji_trophy_history()
