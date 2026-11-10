import io
import json
import zipfile
import requests
from bs4 import BeautifulSoup
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
}

# 1. Verified CSV2 Feeds
CSV2_LEAGUES = {
    'BBL': 'https://cricsheet.org/downloads/bbl_csv2.zip',
    'T20_BLAST': 'https://cricsheet.org/downloads/ntb_csv2.zip',
    'PSL': 'https://cricsheet.org/downloads/psl_csv2.zip',
    'CPL': 'https://cricsheet.org/downloads/cpl_csv2.zip',
    'BPL': 'https://cricsheet.org/downloads/bpl_csv2.zip',
    'SA20': 'https://cricsheet.org/downloads/sat_csv2.zip',
    'ILT20': 'https://cricsheet.org/downloads/ilt_csv2.zip',
    'MLC': 'https://cricsheet.org/downloads/mlc_csv2.zip',
    'SUPER_SMASH': 'https://cricsheet.org/downloads/ssm_csv2.zip'
}

def parse_cricsheet_json(zf, fname, league_name):
    rows = []
    try:
        with zf.open(fname) as f:
            data = json.load(f)
            info = data.get('info', {})
            season = str(info.get('season', ''))
            dates = info.get('dates', [''])
            start_date = str(dates[0]) if dates else ''
            venue = str(info.get('venue', ''))
            match_id = fname.replace('.json', '').split('/')[-1]
            
            for inn_idx, inn in enumerate(data.get('innings', [])):
                bat_team = str(inn.get('team', ''))
                for over_data in inn.get('overs', []):
                    over_num = over_data.get('over', 0)
                    for d_idx, d in enumerate(over_data.get('deliveries', [])):
                        runs = d.get('runs', {})
                        wickets = d.get('wickets', [])
                        w_type = wickets[0].get('kind', '') if wickets else ''
                        p_dismissed = wickets[0].get('player_out', '') if wickets else ''
                        
                        rows.append({
                            'match_id': match_id,
                            'season': season,
                            'start_date': start_date,
                            'venue': venue,
                            'innings': inn_idx + 1,
                            'ball': f"{over_num}.{d_idx + 1}",
                            'batting_team': bat_team,
                            'bowling_team': '',
                            'striker': str(d.get('batter', '')),
                            'non_striker': str(d.get('non_striker', '')),
                            'bowler': str(d.get('bowler', '')),
                            'runs_off_bat': str(runs.get('batter', 0)),
                            'extras': str(runs.get('extras', 0)),
                            'wicket_type': w_type,
                            'player_dismissed': p_dismissed,
                            'league': league_name
                        })
    except Exception:
        pass
    return rows

def get_dynamic_cricsheet_links():
    """
    Scrapes the exact live download URLs directly from Cricsheet's official table
    """
    targets = {
        'The Hundred': 'THE_HUNDRED',
        'CSA T20 Challenge': 'CSA_T20',
        'Syed Mushtaq Ali Trophy': 'SMAT'
    }
    extracted = []
    try:
        r = requests.get('https://cricsheet.org/downloads/', headers=HEADERS, timeout=20)
        soup = BeautifulSoup(r.text, 'html.parser')
        for tr in soup.find_all('tr'):
            tds = tr.find_all('td')
            if not tds:
                continue
            name = tds[0].get_text().strip()
            for target_name, league_code in targets.items():
                if target_name.lower() in name.lower():
                    for a in tr.find_all('a'):
                        txt = a.get_text().strip().upper()
                        href = a.get('href', '')
                        if 'JSON' in txt and href.endswith('.zip'):
                            full_url = href if href.startswith('http') else f"https://cricsheet.org{href}"
                            extracted.append((league_code, full_url))
                            print(f"Discovered feed: {league_code} -> {full_url}")
                            break
    except Exception as e:
        print(f"Error scraping Cricsheet download table: {e}")
    return extracted

def harvest_all_t20_tournaments():
    all_deliveries = []
    
    # 1. Harvest CSV2 Leagues
    print("\n--- 1. Harvesting CSV2 Leagues ---")
    for league_name, url in CSV2_LEAGUES.items():
        try:
            r = requests.get(url, headers=HEADERS, timeout=60)
            if r.status_code != 200:
                continue
            with zipfile.ZipFile(io.BytesIO(r.content)) as zf:
                if 'all_matches.csv' in zf.namelist():
                    with zf.open('all_matches.csv') as f:
                        df = pd.read_csv(f, low_memory=False)
                        df['league'] = league_name
                        all_deliveries.append(df)
                        print(f"Loaded {league_name}: {len(df):,} deliveries")
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
                        print(f"Loaded {league_name}: {len(df):,} deliveries")
        except Exception as e:
            print(f"Error on {league_name}: {e}")
            
    # 2. Harvest Dynamic JSON Tournaments (The Hundred, CSA T20, SMAT)
    print("\n--- 2. Harvesting Dynamically Discovered JSON Tournaments ---")
    dynamic_feeds = get_dynamic_cricsheet_links()
    
    for league_name, url in dynamic_feeds:
        try:
            print(f"Downloading {league_name} from {url}...")
            r = requests.get(url, headers=HEADERS, timeout=60)
            if r.status_code != 200:
                print(f"Failed to fetch {league_name} (HTTP {r.status_code})")
                continue
            with zipfile.ZipFile(io.BytesIO(r.content)) as zf:
                tourney_rows = []
                for fname in zf.namelist():
                    if fname.endswith('.json') and not fname.endswith('README.txt'):
                        rows = parse_cricsheet_json(zf, fname, league_name)
                        if rows:
                            tourney_rows.extend(rows)
                if tourney_rows:
                    df_json = pd.DataFrame(tourney_rows)
                    all_deliveries.append(df_json)
                    print(f"SUCCESS: Loaded {league_name}: {len(df_json):,} deliveries")
        except Exception as e:
            print(f"Error on {league_name}: {e}")
            
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
        print(f"Active Competitions:\n{master_t20['league'].value_counts()}")
        print(f"==========================================")

def main():
    harvest_all_t20_tournaments()

if __name__ == '__main__':
    main()
