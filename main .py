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

def extract_text_from_url(url: str):
    headers = {
        "User-Agent": "Mozilla/5.0"
    }
    response = requests.get(url, headers=headers, timeout=10)
    soup = BeautifulSoup(response.text, "html.parser")

    # 네이버 블로그 iframe 대응
    iframe = soup.select_one("iframe#mainFrame")
    if iframe and "naver" in url:
        frame_url = iframe["src"]
        if frame_url.startswith("/"):
            base = "https://blog.naver.com"
            frame_url = base + frame_url
        response = requests.get(frame_url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, "html.parser")

    # 본문 추출 시도
    candidates = ["div.se-main-container", "div.postViewArea", "div#content"]
    for selector in candidates:
        content = soup.select_one(selector)
        if content:
            return content.get_text(separator=" ", strip=True)
    return soup.get_text()

def extract_keywords(text):
    words = re.findall(r"[가-힣]{2,}", text)
    counter = Counter(words)
    return counter.most_common(30)

@app.get("/analyze")
def analyze(url: HttpUrl = Query(...)):
    try:
        raw_text = extract_text_from_url(str(url))
        keywords = extract_keywords(raw_text)
        return {"url": url, "keywords": [{"word": w, "count": c} for w, c in keywords]}
    except Exception as e:
        return {"error": str(e)}