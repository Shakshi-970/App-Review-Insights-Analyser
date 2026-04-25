import requests
import feedparser
from src.phase0_foundations.config import settings

def check_raw():
    app_id = "1404115162" # Groww
    url = f"https://itunes.apple.com/in/rss/customerreviews/id={app_id}/sortby=mostrecent/xml"
    res = requests.get(url)
    feed = feedparser.parse(res.content)
    print(f"Total entries in RSS: {len(feed.entries)}")
    if len(feed.entries) > 1:
        print(f"First review title: {feed.entries[1].title}")
        print(f"First review content: {feed.entries[1].content[0].value[:50]}...")

if __name__ == "__main__":
    check_raw()
