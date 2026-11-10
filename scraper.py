import io
import zipfile
import requests
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
}

# Master Global T20 League Feeds
T20_CANDIDATE_FEEDS = [
    # Already verified & active
    ('BBL', 'https://cricsheet.org/downloads/bbl_csv2.zip'),
    ('T20_BLAST', 'https://cricsheet.org/downloads/ntb_csv2.zip'),
    ('PSL', 'https://cricsheet.org/downloads/psl_csv2.zip'),
    ('CPL', 'https://cricsheet.org/downloads/cpl_csv2.zip'),
    ('BPL', 'https://cricsheet.org/downloads/bpl_csv2.zip'),
    ('SA20', 'https://cricsheet.org/downloads/sat_csv2.zip'),
    ('ILT20', 'https://cricsheet.org/downloads/ilt_csv2.zip'),
    ('MLC', 'https://cricsheet.org/downloads/mlc_csv2.zip'),
    ('SUPER_SMASH', 'https://cricsheet.org/downloads/ssm_csv2.zip'),
    
    # Champions League T20 (CLT20 - Pollard 649 runs)
    ('CLT20', 'https://cricsheet.org/downloads/clt_csv2.zip'),
    ('CLT20', 'https://cricsheet.org/downloads/clt20_csv2.zip'),
    ('CLT20', 'https://cricsheet.org/downloads/champions_league_twenty20_csv2.zip'),
    
    # The Hundred (Pollard 270 runs)
    ('THE_HUNDRED', 'https://cricsheet.org/downloads/the_hundred_csv2.zip'),
    ('THE_HUNDRED', 'https://cricsheet.org/downloads/thh_csv2.zip'),
    ('THE_HUNDRED', 'https://cricsheet.org/downloads/hundred_csv2.zip'),
    
    # CSA T20 Challenge / Ram Slam (South Africa domestic)
    ('CSA_T20', 'https://cricsheet.org/downloads/csa_csv2.zip'),
    ('CSA_T20', 'https://cricsheet.org/downloads/cst_csv2.zip'),
    ('CSA_T20', 'https://cricsheet.org/downloads/csa_t20_challenge_csv2.zip')
]

def harvest_global_t20_leagues():
    all_deliveries = []
    harvested_leagues = set()
    print("\n--- Harvesting Expanded Global T20 Tournaments from Cricsheet ---")
    
    for league_name, url in T20_CANDIDATE_FEEDS:
        if league_name in harvested_leagues and league_name in ['CLT20', 'THE_HUNDRED', 'CSA_T20']:
            continue
            
        try:
            print(f"Checking {league_name} ({url})...")
            r = requests.get(url, headers=HEADERS, timeout=45)
            if r.status_code != 200:
                print(f"Skipping {league_name} (HTTP {r.status_code})")
                continue
                
            with zipfile.ZipFile(io.BytesIO(r.content)) as zf:
                if 'all_matches.csv' in zf.namelist():
                    with zf.open('all_matches.csv') as f:
                        df = pd.read_csv(f, low_memory=False)
                        df['league'] = league_name
                        all_deliveries.append(df)
                        harvested_leagues.add(league_name)
                        print(f"SUCCESS: Loaded {league_name}: {len(df):,} deliveries")
                else:
                    sub_dfs = []
                    for fname in zf.namelist():
                        if fname.endswith('.csv') and not fname.endswith('_info.csv'):
                            with zf.open(fname) as f:
                                try:
                                    sub_df = pd.read_csv(f, low_memory=False)
                                    if 'striker' in sub_df.columns:
                                        sub_dfs.append(sub_df)
                                except Exception:
                                    pass
                    if sub_dfs:
                        df = pd.concat(sub_dfs, ignore_index=True)
                        df['league'] = league_name
                        all_deliveries.append(df)
                        harvested_leagues.add(league_name)
                        print(f"SUCCESS: Loaded {league_name} ({len(sub_dfs)} matches): {len(df):,} deliveries")
        except Exception as e:
            print(f"Error checking {league_name}: {e}")
            
    if all_deliveries:
        master_t20 = pd.concat(all_deliveries, ignore_index=True)
        
        cols = ['match_id', 'season', 'start_date', 'venue', 'innings', 'ball', 'batting_team', 'bowling_team', 'striker', 'non_striker', 'bowler', 'runs_off_bat', 'extras', 'wicket_type', 'player_dismissed', 'league']
        existing_cols = [c for c in cols if c in master_t20.columns]
        master_t20 = master_t20[existing_cols]
        
        for col in master_t20.columns:
            master_t20[col] = master_t20[col].astype(str)
            
        out_file = 'global_t20_leagues.parquet'
        table = pa.Table.from_pandas(master_t20)
        pq.write_table(table, out_file)
        print(f"\n==========================================")
        print(f"SAVED {len(master_t20):,} TOTAL DELIVERIES TO {out_file}!")
        print(f"Active Leagues:\n{master_t20['league'].value_counts()}")
        print(f"==========================================")
    else:
        print("No deliveries collected!")

def main():
    harvest_global_t20_leagues()

if __name__ == '__main__':
    main()
