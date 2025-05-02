from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import HttpUrl
from bs4 import BeautifulSoup
from collections import Counter
import re
import requests

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

STOPWORDS = set([
    "진짜", "정말", "안녕하세요", "이번", "이제", "여기", "그냥", "맛있게", "또한", "그리고", 
    "하는", "해서", "하게", "것을", "이런", "저런", "합니다", "했다", "있다", "없다", "입니다"
])

def extract_text_and_media(url: str):
    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(url, headers=headers, timeout=10)
    soup = BeautifulSoup(response.text, "html.parser")

    iframe = soup.select_one("iframe#mainFrame")
    if iframe and "naver" in url:
        frame_url = iframe["src"]
        if frame_url.startswith("/"):
            frame_url = "https://blog.naver.com" + frame_url
        response = requests.get(frame_url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, "html.parser")

    selectors = ["div.se-main-container", "div.postViewArea", "div#content"]
    for selector in selectors:
        content = soup.select_one(selector)
        if content:
            text = content.get_text(separator=" ", strip=True)
            return text, soup
    return soup.get_text(), soup

def filter_keywords(words):
    return [word for word in words if word not in STOPWORDS and len(word) > 1]

def extract_keywords(text):
    words = re.findall(r"[가-힣]{2,}", text)
    filtered = filter_keywords(words)
    return filtered, Counter(filtered).most_common(30)

def extract_combinations(filtered):
    combo2 = Counter()
    combo3 = Counter()
    for i in range(len(filtered)):
        if i + 1 < len(filtered):
            combo2[f"{filtered[i]} {filtered[i+1]}"] += 1
        if i + 2 < len(filtered):
            combo3[f"{filtered[i]} {filtered[i+1]} {filtered[i+2]}"] += 1
    return combo2.most_common(5), combo3.most_common(5)

def count_media(soup, text):
    return {
        "images": len(soup.select("img")),
        "videos": len(soup.select("video")),
        "gifs": len([img for img in soup.select("img") if '.gif' in img.get("src", "")]),
        "stickers": len(soup.select("span.se-emoticon")),
        "text_length": len(text)
    }

def analyze_single(url: str):
    try:
        text, soup = extract_text_and_media(url)
        filtered, keywords = extract_keywords(text)
        combos2, combos3 = extract_combinations(filtered)
        media = count_media(soup, text)
        return {
            "url": url,
            "keywords": keywords,
            "combos_2": combos2,
            "combos_3": combos3,
            "media": media
        }
    except Exception as e:
        return {"url": url, "error": str(e)}

@app.get("/analyze")
def analyze(url1: str = "", url2: str = "", url3: str = ""):
    urls = [url for url in [url1, url2, url3] if url.strip()]
    results = [analyze_single(url) for url in urls]

    all_keywords = [set(k for k, _ in r["keywords"]) for r in results if "keywords" in r]
    all_combos2 = [set(k for k, _ in r["combos_2"]) for r in results if "combos_2" in r]
    all_combos3 = [set(k for k, _ in r["combos_3"]) for r in results if "combos_3" in r]

    common_keywords = list(set.intersection(*all_keywords)) if len(all_keywords) > 1 else []
    common_combos = list(set.intersection(*all_combos2, *all_combos3)) if len(all_combos2 + all_combos3) > 1 else []

    summary = f"총 {len(results)}개의 블로그 글을 분석했고, 공통 키워드는 {', '.join(common_keywords[:5])} 등이 있습니다."

    return {
        "summary": summary,
        "common_keywords": common_keywords[:10],
        "common_combos": common_combos[:10],
        "each": results
    }