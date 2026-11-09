import time
import requests
import pandas as pd
from io import StringIO

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

# Key player IDs on ESPNcricinfo
PLAYER_REGISTRY = {
    "James Anderson": 8608,
    "Stuart Broad": 9253,
    "Muttiah Muralitharan": 49636,
    "Shane Warne": 8180,
    "Glenn McGrath": 6565,
    "Wasim Akram": 43555,
    "Sachin Tendulkar": 35320,
    "Virat Kohli": 253802,
    "MS Dhoni": 28081,
    "Rohit Sharma": 34102,
    "Jasprit Bumrah": 625383,
    "Ravichandran Ashwin": 26421
}

def harvest_player_careers():
    print("🚀 Harvesting Complete Career Profiles (Test, ODI, T20I, First-Class, List A, T20)...")
    all_player_data = []

    for player_name, player_id in PLAYER_REGISTRY.items():
        print(f"   -> Fetching full career profile for {player_name} (ID: {player_id})...")
        url = f"https://stats.espncricinfo.com/ci/engine/player/{player_id}.html?template=results;type=bowling"
        
        try:
            resp = requests.get(url, headers=HEADERS, timeout=15)
            if resp.status_code == 200:
                tables = pd.read_html(StringIO(resp.text))
                for df in tables:
                    # Look for the career summary table with format rows
                    if len(df) >= 3 and any("Test" in str(x) for x in df.iloc[:, 0].values):
                        # Clean and format table
                        df.columns = [str(c).strip() for c in df.columns]
                        df = df.rename(columns={df.columns[0]: "format", "Mat": "matches", "Wkts": "wickets", "Runs": "runs_conceded", "Ave": "bowling_average"})
                        df["player_name"] = player_name
                        df["cricinfo_id"] = str(player_id)
                        
                        # Filter to standard format rows
                        valid_formats = ["Test matches", "One-Day Internationals", "Twenty20 Internationals", "First-class matches", "List A matches", "Twenty20 matches"]
                        df_filtered = df[df["format"].isin(valid_formats)].copy()
                        
                        if not df_filtered.empty:
                            all_player_data.append(df_filtered)
                            break
            time.sleep(1)
        except Exception as e:
            print(f"      Error fetching {player_name}: {e}")

    if all_player_data:
        combined_df = pd.concat(all_player_data, ignore_index=True)
        for col in combined_df.columns:
            combined_df[col] = combined_df[col].astype(str)
        combined_df.to_parquet("official_player_full_profiles.parquet", index=False)
        print("✅ Saved: official_player_full_profiles.parquet with ALL formats!")

if __name__ == "__main__":
    harvest_player_careers()
