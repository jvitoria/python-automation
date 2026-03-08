import feedparser

# 1. The sources you want to scan
SOURCES = [
    "https://news.ycombinator.com/rss",
    "https://feeds.feedburner.com/TechCrunch/",
    "https://www.nasa.gov/rss/dyn/lg_image_of_the_day.rss"
]

# 2. Your target keywords (Automation is better when it's specific!)
KEYWORDS = ["AI", "Python", "Space", "Apple", "Robot"]

def run_smart_aggregator():
    filename = "filtered_content.md"
    found_count = 0
    
    print("🚀 Starting Content Scan...")

    with open(filename, "w", encoding="utf-8") as f:
        f.write("# 🎯 Automated Content Digest\n")
        f.write(f"**Keywords:** {', '.join(KEYWORDS)}\n\n---\n")

        for url in SOURCES:
            feed = feedparser.parse(url)
            source_name = getattr(feed.feed, 'title', url)
            print(f"Scanning {source_name}...")

            for entry in feed.entries:
                # We convert the title to lowercase so 'AI' matches 'ai' or 'Ai'
                title = entry.title.lower()
                
                # The 'Magic' Line: Checks if ANY of your keywords are in the title
                if any(word.lower() in title for word in KEYWORDS):
                    f.write(f"### {entry.title}\n")
                    f.write(f"* **Source:** {source_name}\n")
                    f.write(f"* [Read Full Article]({entry.link})\n\n")
                    found_count += 1
                    print(f"   ✅ Found: {entry.title[:50]}...")

    print(f"\n✨ Done! Found {found_count} matching articles.")
    print(f"📁 Open '{filename}' in VS Code to see your results.")

if __name__ == "__main__":
    run_smart_aggregator()