import io
import time
import requests
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

HEADERS = {
    'User-Agent': 'CricketHistoryEngine/1.0 (contact@github.com) Mozilla/5.0'
}

def harvest_wikipedia_career_profiles():
    print("\n--- 1. Harvesting Official Career Infoboxes from Wikipedia ---")
    session = requests.Session()
    
    PLAYERS = [
        'Joe Root', 'Sachin Tendulkar', 'Rahul Dravid', 'Virat Kohli',
        'Rohit Sharma', 'MS Dhoni', 'Chris Gayle', 'Kieron Pollard',
        'David Warner', 'AB de Villiers', 'Steve Smith', 'Kane Williamson',
        'Babar Azam', 'Jos Buttler', 'Ben Stokes', 'James Anderson',
        'Stuart Broad', 'Ricky Ponting', 'Brian Lara', 'Jacques Kallis',
        'Donald Bradman', 'Kumar Sangakkara', 'Muttiah Muralitharan',
        'Shane Warne', 'Wasim Akram', 'Sunil Gavaskar', 'Kapil Dev',
        'Wasim Jaffer', 'Cheteshwar Pujara', 'Steve Tikolo'
    ]
    
    all_rows = []
    
    for player in PLAYERS:
        wiki_name = player.replace(' ', '_')
        url = f"https://en.wikipedia.org/api/rest_v1/page/html/{wiki_name}"
        try:
            r = session.get(url, headers=HEADERS, timeout=15)
            if r.status_code != 200:
                continue
                
            dfs = pd.read_html(io.StringIO(r.text))
            stat_df = None
            for d in dfs:
                cols = [str(c).lower() for c in d.columns]
                if any('test' in c or 'odi' in c or 't20' in c or 'first-class' in c for c in cols):
                    first_col = d.columns[0]
                    vals = [str(v).lower() for v in d[first_col].values[:10]]
                    if any('matches' in v or 'runs' in v for v in vals):
                        stat_df = d.copy()
                        break
                        
            if stat_df is not None:
                first_col = stat_df.columns[0]
                stat_df.set_index(first_col, inplace=True)
                stat_df = stat_df.T.reset_index()
                stat_df.rename(columns={'index': 'format_raw'}, inplace=True)
                
                format_map = {
                    'Test': 'TEST', 'Tests': 'TEST',
                    'ODI': 'ODI', 'ODIs': 'ODI',
                    'T20I': 'T20I', 'T20Is': 'T20I',
                    'FC': 'FIRST_CLASS', 'First-class': 'FIRST_CLASS',
                    'LA': 'LIST_A', 'List A': 'LIST_A',
                    'T20': 'TWENTY20', 'T20s': 'TWENTY20'
                }
                stat_df['format'] = stat_df['format_raw'].map(format_map)
                stat_df = stat_df[stat_df['format'].notnull()]
                stat_df['player'] = player
                
                # Remove duplicate columns from Wikipedia table
                stat_df = stat_df.loc[:, ~stat_df.columns.duplicated()].copy()
                
                col_rename = {}
                for c in stat_df.columns:
                    c_low = str(c).lower()
                    if 'matches' in c_low and 'matches' not in col_rename.values():
                        col_rename[c] = 'matches'
                    elif 'runs' in c_low and 'conceded' not in c_low and 'runs' not in col_rename.values():
                        col_rename[c] = 'runs'
                    elif 'average' in c_low and 'bowl' not in c_low and 'batting_average' not in col_rename.values():
                        col_rename[c] = 'batting_average'
                    elif ('100' in c_low or 'centuries' in c_low) and 'centuries' not in col_rename.values():
                        col_rename[c] = 'centuries'
                    elif 'wickets' in c_low and 'wickets' not in col_rename.values():
                        col_rename[c] = 'wickets'
                        
                stat_df.rename(columns=col_rename, inplace=True)
                
                for required in ['player', 'format', 'matches', 'runs', 'batting_average', 'centuries', 'wickets']:
                    if required not in stat_df.columns:
                        stat_df[required] = ''
                        
                clean_slice = stat_df[['player', 'format', 'matches', 'runs', 'batting_average', 'centuries', 'wickets']].copy()
                clean_slice = clean_slice.loc[:, ~clean_slice.columns.duplicated()]
                all_rows.extend(clean_slice.to_dict('records'))
                print(f"Harvested {player}: {len(clean_slice)} formats")
            time.sleep(0.3)
        except Exception as e:
            print(f"Error on {player}: {e}")
            
    if all_rows:
        df_out = pd.DataFrame(all_rows)
        for c in ['matches', 'runs', 'centuries', 'wickets']:
            if c in df_out.columns:
                df_out[c] = df_out[c].astype(str).str.replace(',', '').str.replace('*', '').str.strip()
                df_out[c] = pd.to_numeric(df_out[c], errors='coerce').fillna(0)
                
        out_file = 'official_career_profiles.parquet'
        table = pa.Table.from_pandas(df_out)
        pq.write_table(table, out_file)
        print(f"\nSUCCESS: Saved {len(df_out)} career profile rows to {out_file}!")

def main():
    harvest_wikipedia_career_profiles()

if __name__ == '__main__':
    main()
