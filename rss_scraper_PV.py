#!/usr/bin/env python3
import requests
import anthropic
import xml.etree.ElementTree as ET
import re
import html
from datetime import datetime, timezone

FR_RSS = "https://news.instant-gaming.com/fr/rss.xml"
EN_RSS = "https://news.instant-gaming.com/en/rss.xml"
PT_RSS = "https://news.instant-gaming.com/pt/rss.xml"
TODAY_UTC = datetime.now(timezone.utc).strftime("%Y-%m-%d")
MODEL = "claude-sonnet-4-6"
HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}

TRANSLATION_SYSTEM_PROMPT = """You are a professional translator and blog editor for a pop culture website.
Translate the provided news article into European Portuguese (Portugal).

════════════════════════════════════════
1. LANGUAGE — EUROPEAN PORTUGUESE ONLY
════════════════════════════════════════
Brazilian Portuguese is completely unacceptable under any circumstance. When in doubt, always choose the European Portuguese form.
- NEVER use "você" — use "tu" or rephrase entirely
- NEVER use gerunds: "estou fazendo" → "estou a fazer", "foi anunciando" → "foi anunciado"
- NEVER use "ônibus", "celular", "time" (team), "legal" (cool) → "autocarro", "telemóvel", "equipa", "fixe"
- NEVER use "baixar" for download → "transferir" or "descarregar"
- NEVER use "assistir o jogo" → "ver o jogo"
- Clitic pronouns follow European rules: "diz-se", "convida-nos" — never "se diz" at the start of a clause
- Use AO90 orthography: "ativo", "objetivo", "coleção", "facto"
- "fim de semana" without hyphens
- "ecrã" for screen, "consolas" for consoles
- "franquia" for franchise/IP, "plantel" for roster
- Euro format: 9,99€

════════════════════════════════════════
2. FORMATTING — PRESERVE EXACTLY
════════════════════════════════════════
Keep exactly the same formatting as the original (Markdown, lists, headings, bold, italics, links, quotes, line breaks).
Do not add, remove, or alter any formatting elements.
- **Bold** only on VIDEO GAME titles and GAME STUDIO/PUBLISHER names
- Do NOT bold platforms, media outlets, social networks, or general brand names
- ## for section subtitles if the original has them
- Paragraphs separated by one blank line
- No H1 inside the body

════════════════════════════════════════
3. QUOTES
════════════════════════════════════════
- All quotes must use angle quotes: « »
- If the original uses italics for a quote, keep the italics: *«quoted text»*
- Standalone block quotes (tweets, direct statements): > *«quoted text»*
- Inline quotes within a paragraph: *«quoted text»*

════════════════════════════════════════
4. STYLE AND TONE
════════════════════════════════════════
- Always maintain a neutral journalistic tone (informative, factual)
- Do not invent information, do not editorialize
- Reproduce the intent of the original faithfully
- The output must ALWAYS be in European Portuguese — never accidentally return the source language

════════════════════════════════════════
5. LINKS AND MEDIA
════════════════════════════════════════
- All links, videos, tweets, and external references must be preserved without changes
- Exception: any Instant Gaming links must have the language segment replaced with PT
  e.g. instant-gaming.com/fr/ → instant-gaming.com/pt/
  e.g. instant-gaming.com/en/ → instant-gaming.com/pt/

════════════════════════════════════════
6. OFFICIAL NAMES AND TERMS
════════════════════════════════════════
- NEVER translate names of games, studios, brands, or official terms
  e.g. "Hollow Knight: Silksong", "Xbox Game Pass Ultimate", "SteamDB" stay exactly as-is
- ALL titles (games, movies, TV series) must use the official English release name — never the French or Portuguese translated title
  e.g. "Maléfique" → "Maleficent", "Le Transporteur" → "The Transporter"
- Platform and service names are FEMININE in Portuguese:
  a PlayStation, a Xbox, a Steam, a Twitch, a Switch
- Only translate the body/descriptive text, never the proper names

════════════════════════════════════════
7. FINAL OUTPUT
════════════════════════════════════════
The response must contain ONLY the translation. No comments, notes, explanations, or preamble.
Return EXACTLY this format, nothing before or after:

{plain text title on one line}

{body in markdown}"""


def fetch_rss(url):
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        r.raise_for_status()
        root = ET.fromstring(r.content)
    except Exception as e:
        print(f"   Could not fetch {url}: {e}")
        return []
    channel = root.find("channel")
    raw_items = channel.findall("item") if channel else root.findall(".//item")
    items = []
    for item in raw_items:
        pub_date = item.findtext("pubDate", "")
        content = (item.findtext("{http://purl.org/rss/1.0/modules/content/}encoded") or
                   item.findtext("description", ""))
        img_match = re.search(r'<img[^>]+src=["\']([^"\'> ]+)["\']', content or "")
        image_url = img_match.group(1).strip() if img_match else ""
        items.append({
            "title": item.findtext("title", "").strip(),
            "link": item.findtext("link", "").strip(),
            "body": clean_html(content),
            "image": image_url,
            "date": parse_date(pub_date),
        })
    return items


def parse_date(date_str):
    try:
        dt = datetime.strptime(date_str.strip(), "%a, %d %b %Y %H:%M:%S %z")
        return dt.astimezone(timezone.utc).strftime("%Y-%m-%d")
    except Exception:
        return date_str[:10]


def clean_html(text):
    if not text:
        return ""
    text = html.unescape(text)
    # Extract tweet URLs and replace block with plain x.com URL
    def replace_tweet(m):
        url_match = re.search(r'href="(https://twitter\.com/\S+?/status/\d+)[^"]*"', m.group(0))
        if url_match:
            url = url_match.group(1).replace("twitter.com", "x.com")
            return f"\n{url}\n"
        return ""
    text = re.sub(r'<blockquote[^>]*class="[^"]*twitter[^"]*"[^>]*>.*?</blockquote>',
                  replace_tweet, text, flags=re.DOTALL|re.IGNORECASE)
    # Extract YouTube URLs
    def replace_youtube(m):
        url_match = re.search(r'(?:src|href)="(https://(?:www\.)?(?:youtube\.com|youtu\.be)/\S+?)"', m.group(0))
        if url_match:
            return f"\n{url_match.group(1)}\n"
        return ""
    text = re.sub(r'<iframe[^>]*(?:youtube\.com|youtu\.be)[^>]*>.*?</iframe>',
                  replace_youtube, text, flags=re.DOTALL|re.IGNORECASE)
    # Strip all remaining HTML tags
    text = re.sub(r"<[^>]+>", "", text)
    # Clean leftover social media artifacts
    text = re.sub(r'.*pic\.twitter\.com\S*.*', '', text)
    text = re.sub(r'—\s*@\w+.*', '', text)
    text = re.sub(r'^@\w+.*$', '', text, flags=re.MULTILINE)
    text = re.sub(r'\n{3,}', '\n\n', text.strip())
    return text


def article_id(url):
    match = re.search(r"/art(?:icles|igos)/(\d+)-", url)
    return match.group(1) if match else None


def main():
    print("\n" + "=" * 58)
    print("  IG NEWS PT — DAILY TRANSLATOR")
    print(f"  {TODAY_UTC}")
    print("=" * 58 + "\n")

    print("Fetching FR feed (source of truth)...")
    fr_items = fetch_rss(FR_RSS)
    print(f"   {len(fr_items)} items\n")

    print("Fetching EN feed (preferred translation source)...")
    en_items = fetch_rss(EN_RSS)
    print(f"   {len(en_items)} items\n")

    print("Fetching PT feed (already translated — will skip these)...")
    pt_items = fetch_rss(PT_RSS)
    print(f"   {len(pt_items)} items\n")

    if not fr_items:
        print("FR feed empty. Check your connection.")
        return

    today_fr = [a for a in fr_items if a["date"] == TODAY_UTC]
    if not today_fr:
        print(f"No articles for today ({TODAY_UTC}).")
        if fr_items:
            print(f"Latest in feed: {fr_items[0]['date']}")
        return

    en_by_id = {article_id(i["link"]): i for i in en_items if article_id(i["link"])}
    pt_ids = {article_id(i["link"]) for i in pt_items if article_id(i["link"])}

    to_translate = []
    already_done = []

    for fr in today_fr:
        aid = article_id(fr["link"])
        if aid in pt_ids:
            already_done.append(fr)
        else:
            en = en_by_id.get(aid)
            to_translate.append({"fr": fr, "en": en, "id": aid})

    print(f"Today's articles: {len(today_fr)} total\n")

    if already_done:
        print(f"  ✅ Already in PT ({len(already_done)}) — skipping:")
        for a in already_done:
            print(f"     • {a['title'][:60]}")
        print()

    if not to_translate:
        print("Nothing left to translate today. All done!")
        return

    print(f"  🔄 Need translation ({len(to_translate)}):")
    for m in to_translate:
        source = "EN" if m["en"] else "FR"
        print(f"     • [{source}] {m['fr']['title'][:55]}")
    print()

    client = anthropic.Anthropic()
    all_output = []

    for i, m in enumerate(to_translate, 1):
        fr, en = m["fr"], m["en"]
        source = en if (en and en["body"]) else fr
        source_lang = "en" if (en and en["body"]) else "fr"

        print(f"[{i}/{len(to_translate)}] Translating ({source_lang.upper()}): {fr['title'][:50]}...")

        if not source["body"]:
            print("   Empty body, skipping.\n")
            continue

        try:
            lang_label = "English" if source_lang == "en" else "French"
            msg = client.messages.create(
                model=MODEL,
                max_tokens=2048,
                system=TRANSLATION_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": f"Translate this {lang_label} article:\n\nTITLE: {source['title']}\n\nBODY:\n{source['body']}"}]
            )
            result = msg.content[0].text.strip()
            image = source.get("image", "")
            if image:
                result = f"🖼  {image}\n\n{result}"
            all_output.append(result)
            print("   Done\n")
        except Exception as e:
            print(f"   Error: {e}\n")

    if not all_output:
        print("Nothing to output.")
        return

    print("=" * 58)
    print("  COPY-PASTE READY")
    print("=" * 58)
    for i, block in enumerate(all_output, 1):
        print(f"\n── Article {i} of {len(all_output)} ──\n")
        print(block)
    print("\n" + "=" * 58)
    print(f"  {len(all_output)} article(s) translated — {MODEL}")
    print("=" * 58 + "\n")


if __name__ == "__main__":
    main()