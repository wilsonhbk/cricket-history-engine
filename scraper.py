import io
import zipfile
import requests
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import time

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
}

# 1. Global T20 Leagues to Harvest (Open Cricsheet delivery feeds)
T20_LEAGUES = {
    'BBL': 'https://cricsheet.org/downloads/bbl_csv.zip',
    'T20_BLAST': 'https://cricsheet.org/downloads/ntb_csv.zip',
    'PSL': 'https://cricsheet.org/downloads/psl_csv.zip',
    'CPL': 'https://cricsheet.org/downloads/cpl_csv.zip',
    'SA20': 'https://cricsheet.org/downloads/sat_csv.zip',
    'MLC': 'https://cricsheet.org/downloads/mlc_csv.zip'
}

def harvest_global_t20_leagues():
    all_deliveries = []
    print("\n--- Harvesting Global T20 Leagues from Cricsheet ---")
    
    for league_name, url in T20_LEAGUES.items():
        try:
            print(f"Downloading {league_name} from {url}...")
            r = requests.get(url, headers=HEADERS, timeout=60)
            if r.status_code != 200:
                print(f"Failed to download {league_name} (HTTP {r.status_code})")
                continue
                
            with zipfile.ZipFile(io.BytesIO(r.content)) as zf:
                league_dfs = []
                for fname in zf.namelist():
                    # Every match delivery file has ball data
                    if fname.endswith('.csv') and not fname.endswith('_info.csv'):
                        with zf.open(fname) as f:
                            try:
                                df = pd.read_csv(f, low_memory=False)
                                if 'striker' in df.columns and 'runs_off_bat' in df.columns:
                                    league_dfs.append(df)
                            except Exception:
                                pass
                                
                if league_dfs:
                    combined_league = pd.concat(league_dfs, ignore_index=True)
                    combined_league['league'] = league_name
                    all_deliveries.append(combined_league)
                    print(f"Parsed {league_name}: {len(combined_league):,} deliveries across {len(league_dfs)} matches")
        except Exception as e:
            print(f"Error processing {league_name}: {e}")
            
    if all_deliveries:
        master_t20 = pd.concat(all_deliveries, ignore_index=True)
        
        # Clean data types for clean Parquet export
        for col in ['match_id', 'innings', 'runs_off_bat', 'extras']:
            if col in master_t20.columns:
                master_t20[col] = pd.to_numeric(master_t20[col], errors='coerce').fillna(0).astype(int)
                
        for col in master_t20.columns:
            if col not in ['match_id', 'innings', 'runs_off_bat', 'extras']:
                master_t20[col] = master_t20[col].astype(str)
                
        out_file = 'global_t20_leagues.parquet'
        table = pa.Table.from_pandas(master_t20)
        pq.write_table(table, out_file)
        print(f"\nSUCCESS: Saved {len(master_t20):,} deliveries to {out_file}!")
        print(f"League breakdown:\n{master_t20['league'].value_counts()}")
    else:
        print("No league deliveries collected.")

def main():
    harvest_global_t20_leagues()

if __name__ == '__main__':
    main()
