#!/usr/bin/env python3
import os
import requests
from google import genai
from google.genai import types
import xml.etree.ElementTree as ET
import re
import html
from datetime import datetime, timezone

# --- CONFIGURATION ---
FR_RSS = "https://news.instant-gaming.com/fr/rss.xml"
EN_RSS = "https://news.instant-gaming.com/en/rss.xml"
PT_RSS = "https://news.instant-gaming.com/pt/rss.xml"
TODAY_UTC = datetime.now(timezone.utc).strftime("%Y-%m-%d")
MODEL_ID = "gemini-3-flash" # Optimized for speed and translation accuracy
HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}

# Use the same high-quality PT-PT prompt from your friend
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

{body in markdown}
"""

# Initialize Gemini Client
client = genai.Client(api_key=os.environ.get("GOOGLE_API_KEY"))

def fetch_rss(url):
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        r.raise_for_status()
        root = ET.fromstring(r.content)
    except Exception as e:
        print(f"    Could not fetch {url}: {e}")
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
    if not text: return ""
    text = html.unescape(text)
    # Tweet replacement logic
    def replace_tweet(m):
        url_match = re.search(r'href="(https://twitter\.com/\S+?/status/\d+)[^"]*"', m.group(0))
        if url_match:
            return f"\n{url_match.group(1).replace('twitter.com', 'x.com')}\n"
        return ""
    text = re.sub(r'<blockquote[^>]*class="[^"]*twitter[^"]*"[^>]*>.*?</blockquote>', replace_tweet, text, flags=re.DOTALL|re.IGNORECASE)
    # YouTube replacement logic
    def replace_youtube(m):
        url_match = re.search(r'(?:src|href)="(https://(?:www\.)?(?:youtube\.com|youtu\.be)/\S+?)"', m.group(0))
        return f"\n{url_match.group(1)}\n" if url_match else ""
    text = re.sub(r'<iframe[^>]*(?:youtube\.com|youtu\.be)[^>]*>.*?</iframe>', replace_youtube, text, flags=re.DOTALL|re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r'\n{3,}', '\n\n', text.strip())
    return text

def article_id(url):
    match = re.search(r"/art(?:icles|igos)/(\d+)-", url)
    return match.group(1) if match else None

def main():
    # ... [Same feed fetching and comparison logic as the original script] ...
    
    # --- The Gemini Translation Loop ---
    for i, m in enumerate(to_translate, 1):
        fr, en = m["fr"], m["en"]
        source = en if (en and en["body"]) else fr
        source_lang = "English" if (en and en["body"]) else "French"

        print(f"[{i}/{len(to_translate)}] Translating ({source_lang}): {fr['title'][:50]}...")

        try:
            # Gemini-specific generation call
            response = client.models.generate_content(
                model=MODEL_ID,
                config=types.GenerateContentConfig(
                    system_instruction=TRANSLATION_SYSTEM_PROMPT,
                    temperature=0.3 # Lower temperature for more factual translation
                ),
                contents=f"Translate this {source_lang} article:\n\nTITLE: {source['title']}\n\nBODY:\n{source['body']}"
            )
            
            result = response.text.strip()
            # ... [Handle image and output as in the original script] ...
            
        except Exception as e:
            print(f"   Error calling Gemini: {e}\n")

if __name__ == "__main__":
    main()