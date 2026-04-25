import json
import os
import sqlite3
import pandas as pd
from src.phase1_ingestion.appstore_scraper import AppStoreScraper
from src.phase1_ingestion.playstore_scraper import PlayStoreScraper
from src.phase1_ingestion.title_generator import TitleGenerator
from src.phase0_foundations.config import settings

def main():
    print("=== Phase 1: Ingestion Run (Target: Groww) ===")
    
    app_scraper = AppStoreScraper()
    play_scraper = PlayStoreScraper()
    title_gen = TitleGenerator()
    
    product = "Groww"
    print(f"\nProcessing product: {product}")
    
    # Fetch reviews
    as_reviews = app_scraper.fetch_reviews(product)
    ps_reviews = play_scraper.fetch_reviews(product)
    
    all_reviews = (as_reviews + ps_reviews)[:2400]
    total = len(all_reviews)
    print(f"Total cleaned reviews for {product} (capped at 2400): {total}")
    
    if total > 0:
        data_dir = "src/phase1_ingestion/data"
        os.makedirs(data_dir, exist_ok=True)
        
        # Step 1: Generate LLM-based summary titles
        print("\nGenerating AI summary titles...")
        review_texts = [r.text for r in all_reviews]
        titles = title_gen.generate_all_titles(review_texts)
        
        # Step 2: Serialize reviews, EXCLUDE 'date', REPLACE 'title' with LLM title
        serialized_reviews = []
        for r, ai_title in zip(all_reviews, titles):
            d = r.model_dump(mode='json')
            d.pop('date', None)       # Remove date
            d['title'] = ai_title     # LLM-generated title
            serialized_reviews.append(d)
        
        # 1. Save JSON
        json_path = os.path.join(data_dir, f"reviews_{product}.json")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(serialized_reviews, f, indent=4, ensure_ascii=False)
        print(f"  Saved JSON: {json_path}")
        
        # 2. Save CSV
        df = pd.DataFrame(serialized_reviews)
        csv_path = os.path.join(data_dir, f"reviews_{product}.csv")
        df.to_csv(csv_path, index=False)
        print(f"  Saved CSV:  {csv_path}")
        
        # 3. Save SQLite
        sqlite_path = os.path.join(data_dir, "reviews.sqlite")
        conn = sqlite3.connect(sqlite_path)
        conn.execute("DROP TABLE IF EXISTS reviews")
        df.to_sql("reviews", conn, index=False)
        conn.close()
        print(f"  Saved SQLite: {sqlite_path}")
        
        # 4. Save HTML table
        html_path = os.path.join(data_dir, "view_reviews.html")
        df.to_html(html_path, index=False)
        print(f"  Saved HTML: {html_path}")
        
        print("\nIngestion complete. All reviews processed and saved.")

if __name__ == "__main__":
    main()
