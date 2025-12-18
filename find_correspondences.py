#!/usr/bin/env python3
"""
Helper script to find correspondences between Aromanian and Romanian articles.
Articles are considered corresponding if they share the same image URL.
"""

import os
import json
import subprocess
from pathlib import Path

# Directories
AROMANIAN_ARTICLES_DIR = "output/articles"
ROMANIAN_ARTICLES_DIR = "output_actualitate/articles"
OUTPUT_FILE = "correspondences.json"


def find_romanian_articles_with_image(image_url: str, romanian_dir: str) -> list[str]:
    """
    Find Romanian article filenames that contain the given image URL.
    Uses grep for efficient searching.
    """
    if not image_url or image_url.startswith("data:"):
        return []
    
    try:
        # Use grep to search for the image URL in Romanian articles
        result = subprocess.run(
            ["grep", "-rl", image_url, romanian_dir],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode == 0 and result.stdout.strip():
            # Extract just the filenames from the full paths
            matches = []
            for line in result.stdout.strip().split('\n'):
                if line:
                    filename = os.path.basename(line)
                    matches.append(filename)
            return matches
        return []
    except subprocess.TimeoutExpired:
        print(f"Timeout searching for: {image_url}")
        return []
    except Exception as e:
        print(f"Error searching for {image_url}: {e}")
        return []


def main():
    correspondences = []
    
    aromanian_dir = Path(AROMANIAN_ARTICLES_DIR)
    romanian_dir = Path(ROMANIAN_ARTICLES_DIR)
    
    if not aromanian_dir.exists():
        print(f"Error: Aromanian articles directory not found: {aromanian_dir}")
        return
    
    if not romanian_dir.exists():
        print(f"Error: Romanian articles directory not found: {romanian_dir}")
        return
    
    # Get all Aromanian article files
    aromanian_files = sorted(aromanian_dir.glob("*.json"))
    total = len(aromanian_files)
    
    print(f"Processing {total} Aromanian articles...")
    
    for i, article_path in enumerate(aromanian_files, 1):
        try:
            with open(article_path, 'r', encoding='utf-8') as f:
                article = json.load(f)
            
            image_urls = article.get("image_urls", [])
            aromanian_filename = article_path.name
            
            # Collect all Romanian matches for this Aromanian article
            romanian_matches = set()
            
            for image_url in image_urls:
                # Skip empty strings and data URLs
                if not image_url or image_url.startswith("data:"):
                    continue
                
                matches = find_romanian_articles_with_image(image_url, str(romanian_dir))
                romanian_matches.update(matches)
            
            # Only add if we found correspondences
            if romanian_matches:
                correspondences.append({
                    "aromanian_article": aromanian_filename,
                    "romanian_articles": sorted(list(romanian_matches))
                })
                print(f"[{i}/{total}] {aromanian_filename}: found {len(romanian_matches)} Romanian match(es)")
            else:
                if i % 100 == 0:
                    print(f"[{i}/{total}] Processing...")
                    
        except json.JSONDecodeError as e:
            print(f"Error parsing {article_path}: {e}")
        except Exception as e:
            print(f"Error processing {article_path}: {e}")
    
    # Save results
    print(f"\nFound {len(correspondences)} Aromanian articles with Romanian correspondences")
    
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(correspondences, f, ensure_ascii=False, indent=2)
    
    print(f"Results saved to {OUTPUT_FILE}")
    
    # Print summary statistics
    total_pairs = sum(len(c["romanian_articles"]) for c in correspondences)
    print(f"Total article pairs: {total_pairs}")


if __name__ == "__main__":
    main()
