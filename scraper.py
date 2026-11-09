import requests
from bs4 import BeautifulSoup
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import re
import time
import io

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

def fetch_player_full_profile(player_id, player_name):
    """
    Visits a player's profile URL dynamically and extracts
    their exact 6-format breakdown (First-Class, List A, T20s, Tests, ODIs).
    """
    url = f"https://stats.espncricinfo.com/ci/engine/player/{player_id}.html"
    try:
        r = requests.get(url, headers=HEADERS, timeout=12)
        if r.status_code != 200:
            return []
            
        soup = BeautifulSoup(r.text, 'html.parser')
        tables = soup.find_all('table', class_='engineTable')
        
        batting_dict = {}
        bowling_dict = {}
        
        for t in tables:
            cap = t.find('caption')
            cap_text = cap.get_text().lower() if cap else ''
            if 'career summary' in cap_text and 'batting' in cap_text:
                df = pd.read_html(io.StringIO(str(t)))[0]
                first_col = df.columns[0]
                for _, row in df.iterrows():
                    fmt = str(row[first_col]).strip()
                    if fmt and fmt not in ['nan', 'Career summary']:
                        batting_dict[fmt] = row.to_dict()
                        
            if 'career summary' in cap_text and 'bowling' in cap_text:
                df = pd.read_html(io.StringIO(str(t)))[0]
                first_col = df.columns[0]
                for _, row in df.iterrows():
                    fmt = str(row[first_col]).strip()
                    if fmt and fmt not in ['nan', 'Career summary']:
                        bowling_dict[fmt] = row.to_dict()
                        
        rows = []
        all_fmts = set(list(batting_dict.keys()) + list(bowling_dict.keys()))
        for fmt in all_fmts:
            b = batting_dict.get(fmt, {})
            bw = bowling_dict.get(fmt, {})
            
            fmt_clean = fmt.upper().replace(' ', '_').replace('-', '_')
            if 'FIRST_CLASS' in fmt_clean:
                fmt_clean = 'FIRST_CLASS'
            elif 'LIST_A' in fmt_clean:
                fmt_clean = 'LIST_A'
            elif 'TEST' in fmt_clean:
                fmt_clean = 'TEST'
            elif 'ODI' in fmt_clean:
                fmt_clean = 'ODI'
            elif 'T20I' in fmt_clean:
                fmt_clean = 'T20I'
            elif 'TWENTY20' in fmt_clean or 'T20S' in fmt_clean:
                fmt_clean = 'TWENTY20'
                
            rows.append({
                'Player': player_name,
                'format': fmt_clean,
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
        return rows
    except Exception:
        return []

def main():
    all_rows = []
    seen_ids = set()
    
    # Harvest top players across Tests (class 1), ODIs (class 2), T20Is (class 3)
    # Extracts player IDs dynamically from the page links
    formats = [(1, 'TEST', 10), (2, 'ODI', 10), (3, 'T20I', 8)]
    
    print("--- 1. Discovering players dynamically from Statsguru ---")
    player_queue = []
    
    for cid, fname, max_pages in formats:
        for page in range(1, max_pages + 1):
            url = f"https://stats.espncricinfo.com/ci/engine/stats/index.html?class={cid};page={page};template=results;type=allround"
            try:
                r = requests.get(url, headers=HEADERS, timeout=15)
                if r.status_code != 200:
                    break
                soup = BeautifulSoup(r.text, 'html.parser')
                tables = soup.find_all('table', class_='engineTable')
                if len(tables) < 3:
                    break
                    
                table = tables[2]
                links = table.find_all('a', href=re.compile(r'/ci/content/player/\d+\.html'))
                for a in links:
                    pid = re.search(r'/player/(\d+)\.html', a['href']).group(1)
                    pname = a.get_text().strip()
                    if pid not in seen_ids:
                        seen_ids.add(pid)
                        player_queue.append((pid, pname))
                print(f"[{fname}] Page {page}: discovered {len(player_queue)} total unique players so far")
                time.sleep(0.5)
            except Exception as e:
                print(f"Error on {fname} page {page}: {e}")
                break
                
    print(f"\n--- 2. Crawling 6-format career splits for all {len(player_queue)} discovered players ---")
    for i, (pid, pname) in enumerate(player_queue):
        profile_rows = fetch_player_full_profile(pid, pname)
        if profile_rows:
            all_rows.extend(profile_rows)
        if (i + 1) % 25 == 0:
            print(f"Harvested {i + 1}/{len(player_queue)} player profiles...")
        time.sleep(0.4)
        
    df = pd.DataFrame(all_rows)
    for col in df.columns:
        df[col] = df[col].astype(str)
        
    df.drop_duplicates(subset=['Player', 'format'], inplace=True)
    out_file = 'official_cricinfo_player_careers.parquet'
    table = pa.Table.from_pandas(df)
    pq.write_table(table, out_file)
    print(f"\nDone! Saved {len(df)} career rows covering FC, List A, T20s, Tests & ODIs to {out_file}")

if __name__ == '__main__':
    main()
