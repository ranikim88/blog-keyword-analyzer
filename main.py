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

# 불용어 리스트
STOPWORDS = set([
    "진짜", "정말", "안녕하세요", "이번", "이제", "여기", "그냥", "맛있게", "또한", "그리고", 
    "하는", "해서", "하게", "것을", "이런", "저런", "합니다", "했다", "있다", "없다", "입니다"
])

def extract_text_from_url(url: str):
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
            return content.get_text(separator=" ", strip=True), soup
    return soup.get_text(), soup

def filter_keywords(words):
    return [word for word in words if word not in STOPWORDS and len(word) > 1]

def extract_keywords(text):
    words = re.findall(r"[가-힣]{2,}", text)
    filtered = filter_keywords(words)
    return Counter(filtered).most_common(30)

def extract_compound_keywords(words):
    compound_2 = Counter()
    compound_3 = Counter()
    for i in range(len(words)):
        if i + 1 < len(words):
            pair = f"{words[i]} {words[i+1]}"
            compound_2[pair] += 1
        if i + 2 < len(words):
            triple = f"{words[i]} {words[i+1]} {words[i+2]}"
            compound_3[triple] += 1
    return compound_2.most_common(5), compound_3.most_common(5)

def count_media(soup):
    return {
        "images": len(soup.select("img")),
        "videos": len(soup.select("video")),
        "gifs": len([img for img in soup.select("img") if '.gif' in img.get("src", "")]),
        "stickers": len(soup.select("span.se-emoticon"))  # 네이버 스티커는 이런 식으로 표현됨
    }

@app.get("/analyze")
def analyze(url: HttpUrl = Query(...)):
    try:
        raw_text, soup = extract_text_from_url(str(url))
        words = re.findall(r"[가-힣]{2,}", raw_text)
        filtered = filter_keywords(words)

        keyword_counts = Counter(filtered).most_common(30)
        combo2, combo3 = extract_compound_keywords(filtered)
        media = count_media(soup)

        summary = "이 블로그는 '" + (combo2[0][0] if combo2 else "") + "' 및 '" + (combo3[0][0] if combo3 else "") + "' 키워드를 중심으로 작성된 것으로 보입니다."

        return {
            "url": url,
            "summary": summary,
            "keywords": [{"word": w, "count": c} for w, c in keyword_counts],
            "combos_2": [{"phrase": w, "count": c} for w, c in combo2],
            "combos_3": [{"phrase": w, "count": c} for w, c in combo3],
            "media": media
        }
    except Exception as e:
        return {"error": str(e)}