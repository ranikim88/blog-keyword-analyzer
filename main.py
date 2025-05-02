from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import HttpUrl
from bs4 import BeautifulSoup
from collections import Counter, defaultdict
import re
import statistics
import requests

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 강화된 불용어 필터
STOPWORDS = set([
    "진짜", "정말", "안녕하세요", "이번", "이제", "여기", "그냥", "또한", "그리고", "하는", "해서", "하게",
    "것을", "이런", "저런", "합니다", "했다", "있다", "없다", "입니다", "좋은", "있는", "없는", "매콤한", "차가운",
    "먹을", "같은", "이후", "지금", "먼저", "계속", "보통", "자주", "더욱", "하지만", "그런", "하고", "하기",
    "되며", "되는", "되어", "된다", "의", "은", "는", "을", "를", "이", "가", "고", "로", "과", "도"
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

def filter_nouns(words):
    return [w for w in words if w not in STOPWORDS and len(w) > 1 and not re.search(r"[는은을이가의다한고게같]$", w)]

def extract_keywords(text):
    words = re.findall(r"[가-힣]{2,}", text)
    filtered = filter_nouns(words)
    counts = Counter(filtered)
    return filtered, counts.most_common(10), counts

def extract_combinations(filtered_list, freq_dict):
    valid_bases = {word for word, count in freq_dict.items() if count >= 5}
    combo2 = Counter()
    combo3 = Counter()
    for i in range(len(filtered_list)):
        if filtered_list[i] not in valid_bases:
            continue
        for j in range(i+1, min(i+10, len(filtered_list))):
            if filtered_list[j] in valid_bases:
                combo2[f"{filtered_list[i]} {filtered_list[j]}"] += 1
            if j+1 < len(filtered_list) and filtered_list[j+1] in valid_bases:
                combo3[f"{filtered_list[i]} {filtered_list[j]} {filtered_list[j+1]}"] += 1
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
        filtered, top_keywords, full_counts = extract_keywords(text)
        combos2, combos3 = extract_combinations(filtered, full_counts)
        media = count_media(soup, text)
        return {
            "url": url,
            "keywords": top_keywords,
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

    lengths = [r["media"]["text_length"] for r in results if "media" in r]
    images = [r["media"]["images"] for r in results if "media" in r]

    summary = f"{len(results)}개의 블로그 글을 분석한 결과, "
    if lengths:
        summary += f"평균 글자 수는 약 {int(statistics.mean(lengths))}자, "
    if images:
        summary += f"평균 사진 수는 약 {round(statistics.mean(images), 1)}장, "
    if common_keywords:
        summary += f"공통 키워드는 {', '.join(common_keywords[:5])}, "
    if common_combos:
        summary += f"대표 키워드 조합은 '{common_combos[0]}' 등입니다."

    return {
        "summary": summary.strip(),
        "common_keywords": common_keywords[:10],
        "common_combos": common_combos[:10],
        "each": results
    }