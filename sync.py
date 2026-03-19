import json
import urllib.request
import urllib.error
import urllib.parse
import sys
import re
import getpass
import time
import os
from dotenv import load_dotenv

load_dotenv()

CLIENT_ID = os.getenv("CLIENT_ID")
USERNAME = os.getenv("MANGADEX_USERNAME")
PASSWORD = os.getenv("MANGADEX_PASSWORD")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")

## can change the value to whatever you want, its the output text file
files_map = {
    "plan_to_read": "plan_to_reading.txt",
    "completed": "completed.txt",
    "re_reading": "re_reading.txt",
    "reading": "reading.txt",
    "dropped": "dropped.txt",
    "on_hold": "on_hold.txt"
}

API_BASE = "https://api.mangadex.org"

#sometimes, titles change caps (ex: __ no __ -> __ No __ ), so we normalize them to compare
def normalize_title(title):
    return re.sub(r'[\W_]+', '', title).lower()

def make_request(url, method="GET", data=None, token=None):
    req = urllib.request.Request(url, method=method)
    req.add_header('User-Agent', 'Mozilla/5.0')
    
    if token:
        req.add_header('Authorization', f'Bearer {token}')
        
    if data is not None:
        json_data = json.dumps(data).encode('utf-8')
        req.add_header('Content-Type', 'application/json')
        req.data = json_data
        
    try:
        with urllib.request.urlopen(req) as response:
            return json.loads(response.read())
    except urllib.error.HTTPError as e:
        print(f"HTTP Error: {e.code}")
        print(e.read().decode('utf-8'))
        raise e

def login(username, password, client_secret):
    print("logging in...")
    url = "https://auth.mangadex.org/realms/mangadex/protocol/openid-connect/token"
    
    data = urllib.parse.urlencode({
        "grant_type": "password",
        "username": username,
        "password": password,
        "client_id": CLIENT_ID,
        "client_secret": client_secret
    }).encode("utf-8")
    
    req = urllib.request.Request(url, method="POST", data=data)
    req.add_header('Content-Type', 'application/x-www-form-urlencoded')
    req.add_header('User-Agent', 'Mozilla/5.0')
    
    try:
        with urllib.request.urlopen(req) as response:
            res_data = json.loads(response.read())
            print("login success")
            return res_data["access_token"]
    except urllib.error.HTTPError as e:
        print(f"HTTP Error: {e.code}")
        print(e.read().decode('utf-8'))
        raise e

def get_manga_statuses(token):
    print("fetching reading list statuses...")
    url = f"{API_BASE}/manga/status"
    response = make_request(url, token=token)
    return response.get("statuses", {})

def fetch_manga_titles(ids):
    titles = []
    chunk_size = 100
    for i in range(0, len(ids), chunk_size):
        chunk = ids[i:i+chunk_size]
        query = "&".join([f"ids[]={m}" for m in chunk])
        url = f"{API_BASE}/manga?limit=100&{query}"
        
        response = make_request(url)
        
        for item in response.get("data", []):
            attributes = item.get("attributes", {})
            title_dict = attributes.get("title", {})
            
            ## get the japanese title first, if not found, get the english title, if not found, get the first title, can change this based on preference
            title = title_dict.get("ja-ro")
            if not title:
                title = title_dict.get("en") or (list(title_dict.values())[0] if title_dict else "Unknown Title")
            titles.append(title)
            
        if len(ids) > chunk_size:
            time.sleep(0.5)
    return titles

def update_file(filename, fetched_titles):
    normalized_existing = set()
    
    if os.path.exists(filename):
        with open(filename, "r", encoding="utf-8") as f:
            for line in f:
                title = line.strip()
                if title:
                    normalized_existing.add(normalize_title(title))
                    
    added_count = 0
    with open(filename, "a", encoding="utf-8") as f:
        for title in fetched_titles:
            norm_title = normalize_title(title)
            if norm_title not in normalized_existing:
                f.write(title + "\n")
                normalized_existing.add(norm_title)
                added_count += 1
                
    return added_count

def main():
    try:
        token = login(USERNAME, PASSWORD, CLIENT_SECRET)
    except Exception:
        print("login failed")
        return
        
    statuses = get_manga_statuses(token)
    print(f"found {len(statuses)} total manga in library")
    
    status_groups = {}
    for manga_id, status in statuses.items():
        if status not in status_groups:
            status_groups[status] = []
        status_groups[status].append(manga_id)
        
    for status, ids in status_groups.items():
        filename = files_map.get(status, f"{status}.txt")
        print(f"\nprocessing '{status}' ({len(ids)} manga)...")
        
        titles = fetch_manga_titles(ids)
        added = update_file(filename, titles)
        print(f"-> added {added} new titles to {filename}")
        
    print("\nsuccess")

if __name__ == "__main__":
    main()
