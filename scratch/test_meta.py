import urllib.request
import re

def scrape_metagame_archetypes(html: str):
    tiles = html.split("<div class='archetype-tile'")
    results = []
    for tile in tiles[1:]:
        link_m = re.search(r'href="(/archetype/[^"#]*#paper)"[^>]*>([^<]+)</a>', tile)
        if not link_m:
            continue
        url = "https://www.mtggoldfish.com" + link_m.group(1)
        name = link_m.group(2).strip()
        
        pct_m = re.search(r'metagame-percentage[\s\S]*?statistic-value[^>]*>\s*([0-9.]+\s*%)', tile)
        pct = pct_m.group(1).strip() if pct_m else "0.0%"
        
        results.append({
            'name': name,
            'url': url,
            'pct': pct
        })
    return results

def test_full():
    url = "https://www.mtggoldfish.com/metagame/standard/full"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    }
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req) as response:
            html = response.read().decode('utf-8')
            res = scrape_metagame_archetypes(html)
            print("Total archetypes parsed:", len(res))
            for i, r in enumerate(res[:25]):
                print(f"#{i+1}: {r['name']} - {r['pct']} ({r['url']})")
    except Exception as e:
        print("Error:", e)

if __name__ == "__main__":
    test_full()
