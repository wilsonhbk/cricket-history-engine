import requests
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import time
import io
import re

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5'
}

STANDARD_COLUMNS = [
    'Player', 'format', 'Span', 'Mat', 'Runs', 'HS', 'Bat Av', '100', 'Wkts', 'BBI', 'Bowl Av', '5', 'Ct', 'St'
]

def clean_player_name(series):
    """
    Strips country/team tags like (ICC/IND), (Asia/IND), (ENG)
    so R Dravid, SR Tendulkar, etc. are unified across all formats.
    """
    return series.astype(str).str.replace(r'\s*\(.*?\)', '', regex=True).str.strip()

def fetch_with_retry(session, url, retries=2, delay=2):
    for attempt in range(retries + 1):
        try:
            r = session.get(url, headers=HEADERS, timeout=15)
            if r.status_code == 200:
                return r
            elif r.status_code == 429:
                time.sleep(delay * (attempt + 1))
            else:
                time.sleep(0.8)
        except Exception:
            time.sleep(0.8)
    return None

def fetch_statsguru_table(session, class_id, format_name, max_pages=30):
    records = []
    print(f"\n--- Harvesting {format_name} (class={class_id}) up to {max_pages} pages ---")
    
    for page in range(1, max_pages + 1):
        url = f"https://stats.espncricinfo.com/ci/engine/stats/index.html?class={class_id};page={page};template=results;type=allround"
        r = fetch_with_retry(session, url)
        if not r:
            print(f"[{format_name}] Failed to fetch page {page}, finishing format.")
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
            print(f"[{format_name}] Error on page {page}: {e}")
            break
            
        time.sleep(1.0)
        
    if records:
        return pd.concat(records, ignore_index=True)
    return pd.DataFrame()

def fetch_record_table(session, url, format_name, table_type='batting'):
    """
    Harvests direct all-time record tables for First-Class, List A, and Twenty20
    """
    print(f"Harvesting {format_name} ({table_type}): {url}")
    r = fetch_with_retry(session, url)
    if not r:
        return pd.DataFrame()
        
    try:
        dfs = pd.read_html(io.StringIO(r.text))
        for d in dfs:
            if 'Player' in d.columns and 'Mat' in d.columns:
                d['format'] = format_name
                if table_type == 'batting':
                    if 'Ave' in d.columns:
                        d.rename(columns={'Ave': 'Bat Av'}, inplace=True)
                elif table_type == 'bowling':
                    if 'Ave' in d.columns:
                        d.rename(columns={'Ave': 'Bowl Av'}, inplace=True)
                    if 'Runs' in d.columns:
                        d.drop(columns=['Runs'], inplace=True)
                return d
    except Exception as e:
        print(f"Error parsing record table: {e}")
    return pd.DataFrame()

def main():
    session = requests.Session()
    dfs = []
    
    # 1. International Statsguru Automated Pagination (Tests, ODIs, T20Is)
    formats = [
        (1, 'TEST', 30),        # Up to 1,500 Test players
        (2, 'ODI', 30),         # Up to 1,500 ODI players
        (3, 'T20I', 25)         # Up to 1,250 T20I players
    ]
    
    for cid, fname, pages in formats:
        df = fetch_statsguru_table(session, cid, fname, max_pages=pages)
        if not df.empty:
            dfs.append(df)
            
    # 2. First-Class All-Time Records (Most Runs & Most Wickets in Career)
    df_fc_runs = fetch_record_table(session, 'https://stats.espncricinfo.com/ci/content/records/284248.html', 'FIRST_CLASS', 'batting')
    if not df_fc_runs.empty:
        dfs.append(df_fc_runs)
        
    df_fc_wkts = fetch_record_table(session, 'https://stats.espncricinfo.com/ci/content/records/283838.html', 'FIRST_CLASS', 'bowling')
    if not df_fc_wkts.empty:
        dfs.append(df_fc_wkts)
        
    # 3. List A All-Time Records (Most Runs & Most Wickets in Career)
    df_la_runs = fetch_record_table(session, 'https://stats.espncricinfo.com/ci/content/records/284257.html', 'LIST_A', 'batting')
    if not df_la_runs.empty:
        dfs.append(df_la_runs)
        
    df_la_wkts = fetch_record_table(session, 'https://stats.espncricinfo.com/ci/content/records/283842.html', 'LIST_A', 'bowling')
    if not df_la_wkts.empty:
        dfs.append(df_la_wkts)
        
    # 4. Twenty20 Overall All-Time Records (IPL, Leagues & Internationals)
    df_t20_runs = fetch_record_table(session, 'https://stats.espncricinfo.com/ci/content/records/284262.html', 'TWENTY20', 'batting')
    if not df_t20_runs.empty:
        dfs.append(df_t20_runs)
        
    df_t20_wkts = fetch_record_table(session, 'https://stats.espncricinfo.com/ci/content/records/283846.html', 'TWENTY20', 'bowling')
    if not df_t20_wkts.empty:
        dfs.append(df_t20_wkts)
        
    if dfs:
        combined = pd.concat(dfs, ignore_index=True)
    else:
        combined = pd.DataFrame(columns=STANDARD_COLUMNS)
        
    # Clean player names (unify R Dravid, SR Tendulkar, etc. across all formats)
    combined['Player'] = clean_player_name(combined['Player'])
    
    # Guarantee standard schema
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
    print(f"SUCCESS: Saved {len(combined)} rows to {out_file}")
    print(f"Format counts:\n{combined['format'].value_counts()}")
    print(f"==========================================")

if __name__ == '__main__':
    main()
