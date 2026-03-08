import feedparser

# This is a reliable public RSS feed from NASA
RSS_URL = "https://www.nasa.gov/rss/dyn/lg_image_of_the_day.rss"

def automate_content():
    feed = feedparser.parse(RSS_URL)
    
    # Check if we got data
    if not feed.entries:
        print("No entries found.")
        return

    # Create a filename
    filename = "latest_content.md"

    # Open the file in 'w' (write) mode
    with open(filename, "w", encoding="utf-8") as f:
        # Write a Header
        f.write(f"# Content Report: {feed.feed.title}\n")
        f.write(f"Generated on: {feed.headers.get('date', 'Today')}\n\n")
        f.write("---\n\n")

        # Loop through entries and write them to the file
        for entry in feed.entries[:5]:
            f.write(f"## {entry.title}\n")
            f.write(f"**Source:** {entry.link}  \n")
            f.write(f"**Published:** {entry.published}  \n\n")
            # Some feeds include a summary or description
            if 'summary' in entry:
                f.write(f"{entry.summary}\n\n")
            f.write("---\n\n")

    print(f"✅ Success! Content saved to {filename}")

# So para ter a certeza

if __name__ == "__main__":
    automate_content()