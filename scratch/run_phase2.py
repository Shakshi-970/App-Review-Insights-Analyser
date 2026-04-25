import json
import os
import pandas as pd
import numpy as np
from src.phase2_clustering.embedder import Embedder
from src.phase2_clustering.clusterer import Clusterer
from src.phase0_foundations.models import CleanReview, Cluster
from datetime import datetime

def main():
    print("=== Phase 2: Clustering Run (Target: Groww) ===")
    
    # 1. Load the data from Phase 1
    data_path = "src/phase1_ingestion/data/reviews_Groww.json"
    if not os.path.exists(data_path):
        print(f"Error: Phase 1 data not found at {data_path}")
        return
    
    with open(data_path, "r", encoding="utf-8") as f:
        reviews_data = json.load(f)
    
    # Reconstruct CleanReview objects
    # Note: Phase 1 saved with 'date' missing, so we'll add a dummy date for model validation if needed
    # but the clusterer mainly uses 'text'.
    reviews = []
    for r in reviews_data:
        r['date'] = r.get('date', datetime.now().isoformat())
        reviews.append(CleanReview(**r))
    
    print(f"Loaded {len(reviews)} reviews.")

    # 2. Embedding
    print("\nGenerating embeddings...")
    embedder = Embedder()
    review_texts = [r.text for r in reviews]
    embeddings = embedder.embed(review_texts)
    print(f"Embeddings generated. Shape: {embeddings.shape}")

    # 3. Clustering
    print("\nClustering reviews...")
    clusterer = Clusterer(
        umap_n_neighbors=15,
        umap_min_dist=0.1,
        umap_n_components=5,
        hdbscan_min_cluster_size=10 # Increased for larger dataset
    )
    clusters = clusterer.cluster(embeddings, reviews)
    
    # 4. Save Results
    output_dir = "src/phase2_clustering/data"
    os.makedirs(output_dir, exist_ok=True)
    
    results = []
    for c in clusters:
        label = c.label if c.label else f"Cluster {c.cluster_id}"
        if c.cluster_id == -1:
            label = "Other / Noise"
            
        # Save metadata
        results.append({
            "cluster_id": c.cluster_id,
            "label": label,
            "count": len(c.reviews),
            "representative_samples": [c.reviews[i].text for i in c.centroid_indices[:5]]
        })

    # Save to JSON
    output_path = os.path.join(output_dir, "clusters_Groww.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=4, ensure_ascii=False)
    print(f"\nSaved cluster summaries to: {output_path}")

    # 5. Show Summary
    print(f"\nFound {len(clusters)} clusters (including noise).")
    for r in results:
        print(f"  - {r['label']}: {r['count']} reviews")

if __name__ == "__main__":
    main()
