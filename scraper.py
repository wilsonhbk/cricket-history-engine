import requests
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import time
import io

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5'
}

STANDARD_COLUMNS = [
    'Player', 'format', 'Span', 'Mat', 'Runs', 'HS', 'Bat Av', '100', 'Wkts', 'BBI', 'Bowl Av', '5', 'Ct', 'St'
]

def fetch_with_retry(session, url, retries=2, delay=3):
    for attempt in range(retries + 1):
        try:
            r = session.get(url, headers=HEADERS, timeout=15)
            if r.status_code == 200:
                return r
            elif r.status_code == 429:
                print(f"Rate limited (429). Sleeping {delay * (attempt + 1)}s...")
                time.sleep(delay * (attempt + 1))
            else:
                time.sleep(1)
        except Exception:
            time.sleep(1)
    return None

def fetch_statsguru_table(session, class_id, format_name, max_pages=30):
    records = []
    print(f"\n--- Harvesting {format_name} (class={class_id}) ---")
    
    for page in range(1, max_pages + 1):
        url = f"https://stats.espncricinfo.com/ci/engine/stats/index.html?class={class_id};page={page};template=results;type=allround"
        r = fetch_with_retry(session, url)
        if not r:
            print(f"[{format_name}] Failed to fetch page {page}, moving to next format.")
            break
            
        try:
            dfs = pd.read_html(io.StringIO(r.text))
            table_found = False
            for d in dfs:
                if 'Player' in d.columns and 'Mat' in d.columns:
                    d['format'] = format_name
                    records.append(d)
                    table_found = True
                    print(f"[{format_name}] Page {page} scraped: {len(d)} players")
                    break
                    
            if not table_found:
                print(f"[{format_name}] Reached end of tables at page {page}.")
                break
        except Exception as e:
            print(f"[{format_name}] Error parsing page {page}: {e}")
            break
            
        time.sleep(1.2)  # Polite delay to prevent rate-limiting
        
    if records:
        return pd.concat(records, ignore_index=True)
    return pd.DataFrame()

def fetch_records_table(session, url, format_name):
    r = fetch_with_retry(session, url)
    if not r:
        return pd.DataFrame()
    try:
        dfs = pd.read_html(io.StringIO(r.text))
        for d in dfs:
            if 'Player' in d.columns and 'Mat' in d.columns:
                d['format'] = format_name
                return d
    except Exception:
        pass
    return pd.DataFrame()

def fetch_player_profiles(session):
    """
    Directly extracts complete 6-format career cards (FC, List A, T20, Test, ODI)
    for iconic domestic and international legends.
    """
    LEGENDS = {
        'Rahul Dravid': 28114,
        'Sachin Tendulkar': 35320,
        'Joe Root': 303669,
        'James Anderson': 8608,
        'Virat Kohli': 253802,
        'MS Dhoni': 28081,
        'Rohit Sharma': 34102,
        'Jacques Kallis': 45789,
        'Brian Lara': 52337,
        'Ricky Ponting': 7133,
        'Donald Bradman': 4188,
        'Muttiah Muralitharan': 49636,
        'Shane Warne': 8166,
        'Wasim Akram': 43555,
        'Wasim Jaffer': 29987,       # Ranji Trophy all-time highest run-scorer
        'Cheteshwar Pujara': 32540,
        'Amol Muzumdar': 31411,
        'Sunil Gavaskar': 28794,
        'Kapil Dev': 30024,
        'Kumar Sangakkara': 50710,
        'Steve Tikolo': 24718
    }
    
    rows = []
    print("\n--- Harvesting multi-format career profiles for legends ---")
    for name, pid in LEGENDS.items():
        url = f"https://stats.espncricinfo.com/ci/engine/player/{pid}.html"
        r = fetch_with_retry(session, url)
        if not r:
            continue
            
        try:
            dfs = pd.read_html(io.StringIO(r.text))
            batting_dict = {}
            bowling_dict = {}
            
            for d in dfs:
                first_col = d.columns[0]
                first_vals = [str(v).lower() for v in d[first_col].values[:5]]
                if any('test' in v or 'first-class' in v for v in first_vals):
                    if 'HS' in d.columns or 'Runs' in d.columns:
                        for _, row in d.iterrows():
                            fmt = str(row[first_col]).strip()
                            if fmt and fmt not in ['nan', 'Career summary']:
                                batting_dict[fmt] = row.to_dict()
                    elif 'BBI' in d.columns or 'Wkts' in d.columns:
                        for _, row in d.iterrows():
                            fmt = str(row[first_col]).strip()
                            if fmt and fmt not in ['nan', 'Career summary']:
                                bowling_dict[fmt] = row.to_dict()
                                
            all_fmts = set(list(batting_dict.keys()) + list(bowling_dict.keys()))
            for fmt in all_fmts:
                b = batting_dict.get(fmt, {})
                bw = bowling_dict.get(fmt, {})
                
                fmt_norm = fmt.upper().replace(' ', '_').replace('-', '_')
                if 'FIRST_CLASS' in fmt_norm:
                    fmt_norm = 'FIRST_CLASS'
                elif 'LIST_A' in fmt_norm:
                    fmt_norm = 'LIST_A'
                elif 'TEST' in fmt_norm:
                    fmt_norm = 'TEST'
                elif 'ODI' in fmt_norm:
                    fmt_norm = 'ODI'
                elif 'T20I' in fmt_norm:
                    fmt_norm = 'T20I'
                elif 'TWENTY20' in fmt_norm or 'T20S' in fmt_norm:
                    fmt_norm = 'TWENTY20'
                    
                rows.append({
                    'Player': f"{name} ({b.get('Span', bw.get('Span', ''))})".strip(),
                    'format': fmt_norm,
                    'Span': b.get('Span', bw.get('Span', '')),
                    'Mat': b.get('Mat', bw.get('Mat', '')),
                    'Runs': b.get('Runs', ''),
                    'HS': b.get('HS', ''),
                    'Bat Av': b.get('Ave', ''),
                    '100': b.get('100', ''),
                    'Wkts': bw.get('Wkts', ''),
                    'BBI': bw.get('BBI', ''),
                    'Bowl Av': bw.get('Ave', ''),
                    '5': bw.get('5w', ''),
                    'Ct': b.get('Ct', ''),
                    'St': b.get('St', '')
                })
            print(f"Profile: {name} ({len(all_fmts)} formats harvested)")
            time.sleep(0.8)
        except Exception as e:
            print(f"Error on profile {name}: {e}")
            
    return pd.DataFrame(rows)

def main():
    session = requests.Session()
    dfs = []
    
    # 1. Statsguru Automated Pagination (Tests, ODIs, T20Is, Twenty20)
    formats = [
        (1, 'TEST', 30),        # Up to 1,500 Test players
        (2, 'ODI', 30),         # Up to 1,500 ODI players
        (3, 'T20I', 25),        # Up to 1,250 T20I players
        (6, 'TWENTY20', 20)     # Up to 1,000 Twenty20 players
    ]
    
    for cid, fname, pages in formats:
        df = fetch_statsguru_table(session, cid, fname, max_pages=pages)
        if not df.empty:
            dfs.append(df)
            
    # 2. First-Class & List A All-Time Records (Runs & Wickets)
    df_fc_runs = fetch_records_table(session, 'https://stats.espncricinfo.com/ci/content/records/284248.html', 'FIRST_CLASS')
    if not df_fc_runs.empty:
        dfs.append(df_fc_runs)
        
    df_fc_wkts = fetch_records_table(session, 'https://stats.espncricinfo.com/ci/content/records/283838.html', 'FIRST_CLASS')
    if not df_fc_wkts.empty:
        dfs.append(df_fc_wkts)
        
    df_la_runs = fetch_records_table(session, 'https://stats.espncricinfo.com/ci/content/records/284257.html', 'LIST_A')
    if not df_la_runs.empty:
        dfs.append(df_la_runs)
        
    df_la_wkts = fetch_records_table(session, 'https://stats.espncricinfo.com/ci/content/records/283842.html', 'LIST_A')
    if not df_la_wkts.empty:
        dfs.append(df_la_wkts)
        
    # 3. Multi-Format Legend Profiles (Dravid, Sachin, Root, Kohli, Dhoni, Jaffer, Tikolo)
    df_profiles = fetch_player_profiles(session)
    if not df_profiles.empty:
        dfs.append(df_profiles)
        
    if dfs:
        combined = pd.concat(dfs, ignore_index=True)
    else:
        combined = pd.DataFrame(columns=STANDARD_COLUMNS)
        
    for col in STANDARD_COLUMNS:
        if col not in combined.columns:
            combined[col] = ''
            
    cols_to_drop = [c for c in combined.columns if 'Unnamed' in str(c) or c == 'Ave Diff']
    combined.drop(columns=cols_to_drop, errors='ignore', inplace=True)
    
    for col in combined.columns:
        combined[col] = combined[col].astype(str)
        
    combined.drop_duplicates(subset=['Player', 'format'], inplace=True)
    
    out_file = 'official_cricinfo_player_careers.parquet'
    table = pa.Table.from_pandas(combined)
    pq.write_table(table, out_file)
    print(f"\n==========================================")
    print(f"SUCCESS: Saved {len(combined)} rows across all formats to {out_file}")
    print(f"Format counts:\n{combined['format'].value_counts()}")
    print(f"==========================================")

if __name__ == '__main__':
    main()
