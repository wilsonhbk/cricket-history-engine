import requests
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import time
import io

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

STANDARD_COLUMNS = [
    'Player', 'format', 'Span', 'Mat', 'Runs', 'HS', 'Bat Av', '100', 'Wkts', 'BBI', 'Bowl Av', '5', 'Ct', 'St'
]

def fetch_statsguru_table(class_id, format_name, max_pages=15):
    """
    Crawls Statsguru allround records using robust pd.read_html.
    Finds the table containing 'Player' automatically.
    """
    records = []
    print(f"\n--- Harvesting {format_name} (class={class_id}) ---")
    
    for page in range(1, max_pages + 1):
        url = f"https://stats.espncricinfo.com/ci/engine/stats/index.html?class={class_id};page={page};template=results;type=allround"
        try:
            r = requests.get(url, headers=HEADERS, timeout=15)
            if r.status_code != 200:
                print(f"[{format_name}] Page {page} returned HTTP {r.status_code}, finishing format.")
                break
                
            dfs = pd.read_html(io.StringIO(r.text))
            table_found = False
            for d in dfs:
                if 'Player' in d.columns and 'Mat' in d.columns:
                    d['format'] = format_name
                    records.append(d)
                    table_found = True
                    print(f"[{format_name}] Page {page} harvested: {len(d)} players")
                    break
                    
            if not table_found:
                print(f"[{format_name}] Reached end of tables at page {page}.")
                break
                
            time.sleep(0.6)
        except Exception as e:
            print(f"[{format_name}] Error on page {page}: {e}")
            break
            
    if records:
        return pd.concat(records, ignore_index=True)
    return pd.DataFrame()

def fetch_records_table(url, format_name):
    """
    Harvests all-time records for First-Class and List A
    """
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        if r.status_code != 200:
            return pd.DataFrame()
        dfs = pd.read_html(io.StringIO(r.text))
        for d in dfs:
            if 'Player' in d.columns and 'Mat' in d.columns:
                d['format'] = format_name
                return d
    except Exception as e:
        print(f"Error fetching {url}: {e}")
    return pd.DataFrame()

def main():
    dfs = []
    
    # 1. International & League Formats (Tests, ODIs, T20Is, Twenty20)
    formats = [
        (1, 'TEST', 15),
        (2, 'ODI', 15),
        (3, 'T20I', 15),
        (6, 'TWENTY20', 10)
    ]
    
    for cid, fname, pages in formats:
        df = fetch_statsguru_table(cid, fname, max_pages=pages)
        if not df.empty:
            dfs.append(df)
            
    # 2. First-Class All-Time Records (Runs & Wickets)
    df_fc_runs = fetch_records_table('https://stats.espncricinfo.com/ci/content/records/284248.html', 'FIRST_CLASS')
    if not df_fc_runs.empty:
        dfs.append(df_fc_runs)
        
    df_fc_wkts = fetch_records_table('https://stats.espncricinfo.com/ci/content/records/283838.html', 'FIRST_CLASS')
    if not df_fc_wkts.empty:
        dfs.append(df_fc_wkts)
        
    # 3. List A All-Time Records (Runs & Wickets)
    df_la_runs = fetch_records_table('https://stats.espncricinfo.com/ci/content/records/284257.html', 'LIST_A')
    if not df_la_runs.empty:
        dfs.append(df_la_runs)
        
    df_la_wkts = fetch_records_table('https://stats.espncricinfo.com/ci/content/records/283842.html', 'LIST_A')
    if not df_la_wkts.empty:
        dfs.append(df_la_wkts)
        
    if dfs:
        combined = pd.concat(dfs, ignore_index=True)
    else:
        combined = pd.DataFrame(columns=STANDARD_COLUMNS)
        
    # Guarantee standard schema always exists
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
    print(f"\nSaved {len(combined)} total rows to {out_file} with columns: {table.column_names}")

if __name__ == '__main__':
    main()
