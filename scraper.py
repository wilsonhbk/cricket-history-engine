import requests
from bs4 import BeautifulSoup
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import time
import io

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

def fetch_statsguru_allround(class_id, format_name, max_pages=15):
    """
    Crawls Statsguru allround career records page-by-page.
    Each page contains 50 players with both batting and bowling figures.
    """
    records = []
    print(f"\n--- Harvesting {format_name} (class={class_id}) up to {max_pages} pages ---")
    
    for page in range(1, max_pages + 1):
        url = f"https://stats.espncricinfo.com/ci/engine/stats/index.html?class={class_id};page={page};template=results;type=allround"
        try:
            r = requests.get(url, headers=HEADERS, timeout=15)
            if r.status_code != 200:
                print(f"[{format_name}] Page {page} returned status {r.status_code}, stopping.")
                break
                
            soup = BeautifulSoup(r.text, 'html.parser')
            tables = soup.find_all('table', class_='engineTable')
            if len(tables) < 3:
                print(f"[{format_name}] No data table on page {page}, finished format.")
                break
                
            # The 3rd table is the actual stats table
            df_page = pd.read_html(io.StringIO(str(tables[2])))[0]
            if df_page.empty or 'Player' not in df_page.columns:
                print(f"[{format_name}] Empty table on page {page}, stopping.")
                break
                
            df_page['format'] = format_name
            records.append(df_page)
            print(f"[{format_name}] Page {page} scraped: {len(df_page)} players")
            time.sleep(0.8)  # Polite delay
        except Exception as e:
            print(f"[{format_name}] Error on page {page}: {e}")
            break
            
    if records:
        return pd.concat(records, ignore_index=True)
    return pd.DataFrame()

def fetch_player_profiles():
    """
    Crawls full 6-format career breakdown (First-Class, List A, Tests, ODIs, T20s)
    for iconic domestic and international legends.
    """
    LEGENDS = {
        'Sachin Tendulkar': 35320,
        'James Anderson': 8608,
        'Muttiah Muralitharan': 49636,
        'Shane Warne': 8166,
        'Wasim Akram': 43555,
        'Virat Kohli': 253802,
        'MS Dhoni': 28081,
        'Rohit Sharma': 34102,
        'Jacques Kallis': 45789,
        'Brian Lara': 52337,
        'Ricky Ponting': 7133,
        'Donald Bradman': 4188,
        'Wasim Jaffer': 29987,       # Ranji Trophy all-time record run-scorer
        'Cheteshwar Pujara': 32540,
        'Amol Muzumdar': 31411,
        'Sunil Gavaskar': 28794,
        'Kapil Dev': 30024,
        'Kumar Sangakkara': 50710
    }
    
    rows = []
    print("\n--- Harvesting multi-format career profiles for legends ---")
    
    for name, pid in LEGENDS.items():
        url = f"https://stats.espncricinfo.com/ci/engine/player/{pid}.html"
        try:
            r = requests.get(url, headers=HEADERS, timeout=15)
            if r.status_code != 200:
                continue
                
            soup = BeautifulSoup(r.text, 'html.parser')
            tables = soup.find_all('table', class_='engineTable')
            
            # Find Career Summary table (batting & fielding)
            batting_dict = {}
            for t in tables:
                caption = t.find('caption')
                caption_text = caption.get_text() if caption else ''
                if 'Career summary' in caption_text and 'batting' in caption_text.lower():
                    df_bat = pd.read_html(io.StringIO(str(t)))[0]
                    if 'Unnamed: 0' in df_bat.columns:
                        df_bat.rename(columns={'Unnamed: 0': 'format_raw'}, inplace=True)
                    for _, row in df_bat.iterrows():
                        fmt = str(row.get('format_raw', '')).strip()
                        if fmt and fmt not in ['nan', 'Career summary']:
                            batting_dict[fmt] = row.to_dict()
                            
            # Find Career Summary table (bowling)
            bowling_dict = {}
            for t in tables:
                caption = t.find('caption')
                caption_text = caption.get_text() if caption else ''
                if 'Career summary' in caption_text and 'bowling' in caption_text.lower():
                    df_bowl = pd.read_html(io.StringIO(str(t)))[0]
                    if 'Unnamed: 0' in df_bowl.columns:
                        df_bowl.rename(columns={'Unnamed: 0': 'format_raw'}, inplace=True)
                    for _, row in df_bowl.iterrows():
                        fmt = str(row.get('format_raw', '')).strip()
                        if fmt and fmt not in ['nan', 'Career summary']:
                            bowling_dict[fmt] = row.to_dict()
                            
            # Merge batting & bowling for each format
            all_fmts = set(list(batting_dict.keys()) + list(bowling_dict.keys()))
            for fmt in all_fmts:
                b_stat = batting_dict.get(fmt, {})
                bw_stat = bowling_dict.get(fmt, {})
                
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
                elif fmt_norm in ['T20S', 'TWENTY20']:
                    fmt_norm = 'TWENTY20'
                    
                row = {
                    'Player': f"{name} ({b_stat.get('Span', '')})".strip(),
                    'Span': b_stat.get('Span', bw_stat.get('Span', '')),
                    'Mat': b_stat.get('Mat', bw_stat.get('Mat', '')),
                    'Runs': b_stat.get('Runs', ''),
                    'HS': b_stat.get('HS', ''),
                    'Bat Av': b_stat.get('Ave', ''),
                    '100': b_stat.get('100', ''),
                    'Wkts': bw_stat.get('Wkts', ''),
                    'BBI': bw_stat.get('BBI', ''),
                    'Bowl Av': bw_stat.get('Ave', ''),
                    '5': bw_stat.get('5w', ''),
                    'Ct': b_stat.get('Ct', ''),
                    'St': b_stat.get('St', ''),
                    'format': fmt_norm
                }
                rows.append(row)
            print(f"Profile harvested: {name} ({len(all_fmts)} formats)")
            time.sleep(0.6)
        except Exception as e:
            print(f"Error on profile {name}: {e}")
            
    return pd.DataFrame(rows)

def main():
    dfs = []
    
    # 1. Statsguru Automated Pagination (Tests, ODIs, T20Is, Twenty20)
    formats = [
        (1, 'TEST', 15),       # ~750 Test players
        (2, 'ODI', 15),        # ~750 ODI players
        (3, 'T20I', 15),       # ~750 T20I players
        (6, 'TWENTY20', 10)    # ~500 Twenty20 players (IPL & leagues)
    ]
    
    for cid, fname, pages in formats:
        df = fetch_statsguru_allround(cid, fname, max_pages=pages)
        if not df.empty:
            dfs.append(df)
            
    # 2. Multi-Format Legend Deep Harvest (First-Class, List A, Tests, ODIs, T20s)
    df_legends = fetch_player_profiles()
    if not df_legends.empty:
        dfs.append(df_legends)
        
    if not dfs:
        print("No data collected!")
        return
        
    combined = pd.concat(dfs, ignore_index=True)
    
    # Clean unwanted artifacts
    cols_to_drop = [c for c in combined.columns if 'Unnamed' in str(c) or c == 'Ave Diff']
    combined.drop(columns=cols_to_drop, errors='ignore', inplace=True)
    
    # Ensure all string columns for clean Parquet serialization
    for col in combined.columns:
        combined[col] = combined[col].astype(str)
        
    # Deduplicate
    combined.drop_duplicates(subset=['Player', 'format'], inplace=True)
    
    out_file = 'official_cricinfo_player_careers.parquet'
    table = pa.Table.from_pandas(combined)
    pq.write_table(table, out_file)
    print(f"\n==========================================")
    print(f"SUCCESS: Saved {len(combined)} rows to {out_file}")
    print(f"Format distribution:\n{combined['format'].value_counts()}")
    print(f"==========================================")

if __name__ == '__main__':
    main()
