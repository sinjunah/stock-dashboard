
import os, re, json, time, math
from datetime import datetime, date, timedelta
import pandas as pd
import streamlit as st
import requests
import yfinance as yf

st.set_page_config(page_title="주식 감시 대시보드 V3", page_icon="📈", layout="wide")

STOCKS_FILE = "stocks.json"
LOG_FILE = "prediction_log.csv"

DEFAULT_STOCKS = {
    "삼성전자": "005930.KS",
    "SK하이닉스": "000660.KS",
    "엔비디아": "NVDA",
    "테슬라": "TSLA",
    "AMD": "AMD",
    "SOXL": "SOXL"
}

GOOD_WORDS = [
    "beat","beats","surge","surges","rise","rises","rally","record","growth","upgrade","upgraded",
    "profit","contract","deal","launch","approved","approval","supply","strong","bullish","buy",
    "상승","급등","호재","수주","계약","흑자","성장","상향","매수","실적","공급","승인","개발","성공","강세","반등","최대","신고가"
]
BAD_WORDS = [
    "miss","falls","fall","drop","drops","plunge","lawsuit","recall","downgrade","downgraded","sell",
    "loss","delay","ban","weak","risk","probe","cut","bearish","tariff",
    "하락","급락","악재","소송","리콜","적자","지연","금지","약세","위험","조사","감산","매도","하향","부진","경고","실패"
]

CSS = """
<style>
.block-container {padding-top: 1.5rem;}
.big-card {
  border:1px solid rgba(255,255,255,.15);
  border-radius:18px;
  padding:18px;
  background:linear-gradient(135deg, rgba(44,255,152,.13), rgba(0,125,255,.08));
  min-height:125px;
}
.bad-card {
  border:1px solid rgba(255,100,100,.25);
  border-radius:18px;
  padding:18px;
  background:linear-gradient(135deg, rgba(255,44,44,.16), rgba(255,143,0,.07));
}
.neutral-card {
  border:1px solid rgba(255,255,255,.14);
  border-radius:18px;
  padding:18px;
  background:rgba(255,255,255,.06);
}
.score {
  font-size:34px; font-weight:800;
}
.small {opacity:.75; font-size:13px;}
.news {
  padding:12px 14px; border-radius:14px; margin:8px 0;
  border:1px solid rgba(255,255,255,.11); background:rgba(255,255,255,.045);
}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

def load_stocks():
    if os.path.exists(STOCKS_FILE):
        try:
            with open(STOCKS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict) and data:
                return data
        except Exception:
            pass
    save_stocks(DEFAULT_STOCKS)
    return DEFAULT_STOCKS.copy()

def save_stocks(data):
    with open(STOCKS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def price_info(ticker):
    try:
        hist = yf.Ticker(ticker).history(period="2mo", interval="1d")
        if hist is None or hist.empty:
            return None
        close = hist["Close"].dropna()
        last = float(close.iloc[-1])
        prev = float(close.iloc[-2]) if len(close) > 1 else last
        chg = (last - prev) / prev * 100 if prev else 0
        ma5 = float(close.tail(5).mean())
        ma20 = float(close.tail(20).mean()) if len(close) >= 20 else float(close.mean())
        return {"last": last, "chg": chg, "hist": hist, "ma5": ma5, "ma20": ma20}
    except Exception:
        return None

def google_news(query, limit=8):
    url = "https://news.google.com/rss/search"
    params = {"q": query, "hl": "ko", "gl": "KR", "ceid": "KR:ko"}
    try:
        r = requests.get(url, params=params, timeout=8)
        r.raise_for_status()
        txt = r.text
        items = re.findall(r"<item>(.*?)</item>", txt, flags=re.S)
        out = []
        for it in items[:limit]:
            title = re.search(r"<title><!\[CDATA\[(.*?)\]\]></title>|<title>(.*?)</title>", it, flags=re.S)
            link = re.search(r"<link>(.*?)</link>", it, flags=re.S)
            pub = re.search(r"<pubDate>(.*?)</pubDate>", it, flags=re.S)
            title_text = ""
            if title:
                title_text = (title.group(1) or title.group(2) or "").strip()
            title_text = re.sub("<.*?>", "", title_text)
            out.append({
                "title": title_text,
                "link": link.group(1).strip() if link else "",
                "published": pub.group(1).strip() if pub else ""
            })
        return out
    except Exception:
        return []

def score_title(title):
    t = title.lower()
    score = 50
    good_hits, bad_hits = [], []
    for w in GOOD_WORDS:
        if w.lower() in t:
            score += 9
            good_hits.append(w)
    for w in BAD_WORDS:
        if w.lower() in t:
            score -= 10
            bad_hits.append(w)
    score = max(0, min(100, int(score)))
    if score >= 65:
        label = "호재"
    elif score <= 40:
        label = "악재"
    else:
        label = "중립"
    reason = []
    if good_hits:
        reason.append("호재 키워드: " + ", ".join(good_hits[:3]))
    if bad_hits:
        reason.append("악재 키워드: " + ", ".join(bad_hits[:3]))
    if not reason:
        reason.append("강한 키워드 없음")
    return score, label, " / ".join(reason)

def combined_prediction(news_score, chg, ma5, ma20):
    s = news_score
    if chg > 2: s += 8
    elif chg > 0: s += 3
    elif chg < -2: s -= 8
    elif chg < 0: s -= 3
    if ma5 > ma20: s += 6
    elif ma5 < ma20: s -= 6
    s = max(0, min(100, int(s)))
    if s >= 66:
        return "상승 예상", s, "매수보단 관망 후 눌림 확인"
    if s <= 39:
        return "하락/주의", s, "추격매수 금지, 악재 확인"
    return "관망", s, "방향 애매함, 뉴스 추가 확인"

def load_log():
    if os.path.exists(LOG_FILE):
        try:
            return pd.read_csv(LOG_FILE)
        except Exception:
            pass
    return pd.DataFrame(columns=["date","name","ticker","prediction","confidence","price","next_result_pct","correct"])

def save_predictions(rows):
    df = load_log()
    today = date.today().isoformat()
    tickers = [r["ticker"] for r in rows]
    if not df.empty:
        df = df[~((df["date"] == today) & (df["ticker"].isin(tickers)))]
    df = pd.concat([df, pd.DataFrame(rows)], ignore_index=True)
    df.to_csv(LOG_FILE, index=False, encoding="utf-8-sig")
    return df

def update_results():
    df = load_log()
    if df.empty:
        return df
    changed = False
    for i, r in df.iterrows():
        if str(r.get("correct", "")) not in ["", "nan", "None"]:
            continue
        d = pd.to_datetime(r["date"]).date()
        if d >= date.today():
            continue
        try:
            hist = yf.Ticker(r["ticker"]).history(start=d.isoformat(), end=(d + timedelta(days=7)).isoformat())
            close = hist["Close"].dropna()
            if len(close) >= 2:
                pct = (float(close.iloc[1]) - float(close.iloc[0])) / float(close.iloc[0]) * 100
                df.loc[i, "next_result_pct"] = round(pct, 2)
                pred = str(r["prediction"])
                if "상승" in pred:
                    df.loc[i, "correct"] = bool(pct > 0)
                elif "하락" in pred or "주의" in pred:
                    df.loc[i, "correct"] = bool(pct < 0)
                else:
                    df.loc[i, "correct"] = "관망"
                changed = True
        except Exception:
            pass
    if changed:
        df.to_csv(LOG_FILE, index=False, encoding="utf-8-sig")
    return df

stocks = load_stocks()

with st.sidebar:
    st.header("🎛 조종 패널")
    refresh_on = st.toggle("자동 새로고침", value=False)
    refresh_sec = st.slider("초", 10, 180, 30, step=10)
    if refresh_on:
        st.markdown(f"<meta http-equiv='refresh' content='{refresh_sec}'>", unsafe_allow_html=True)
    st.divider()
    st.subheader("➕ 종목 추가")
    name = st.text_input("종목 이름", placeholder="예: 삼성전자")
    ticker = st.text_input("티커", placeholder="예: 005930.KS / NVDA")
    if st.button("저장"):
        if name.strip() and ticker.strip():
            stocks[name.strip()] = ticker.strip().upper()
            save_stocks(stocks)
            st.success("저장됨. 새로고침하면 보여.")
        else:
            st.warning("이름이랑 티커 둘 다 써.")
    del_pick = st.selectbox("삭제", ["선택 안 함"] + list(stocks.keys()))
    if st.button("삭제") and del_pick != "선택 안 함":
        stocks.pop(del_pick, None)
        save_stocks(stocks)
        st.success("삭제됨. 새로고침하면 반영.")
    st.divider()
    st.caption("한국 주식: 삼성전자 005930.KS / 하이닉스 000660.KS")

st.title("📈 주식 감시 대시보드 V3")
st.caption(f"LIVE · {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} · 뉴스/호재악재/예측기록 버전")

tab_dash, tab_news, tab_log, tab_help = st.tabs(["📊 대시보드", "📰 뉴스·호재악재", "🔮 예측 기록", "📱 사용법"])

cache = {}
today_rows = []

with tab_dash:
    st.subheader("관심종목 현재 흐름")
    cols = st.columns(3)
    for idx, (n, t) in enumerate(stocks.items()):
        info = price_info(t)
        cache[t] = info
        with cols[idx % 3]:
            if not info:
                st.markdown(f"<div class='bad-card'><b>{n}</b><br>데이터 실패<br><span class='small'>{t}</span></div>", unsafe_allow_html=True)
                continue
            cls = "big-card" if info["chg"] >= 0 else "bad-card"
            st.markdown(
                f"<div class='{cls}'><div class='small'>{n} · {t}</div>"
                f"<div class='score'>{info['last']:,.2f}</div>"
                f"<div>{info['chg']:+.2f}%</div></div>",
                unsafe_allow_html=True
            )
    st.divider()
    pick = st.selectbox("차트 종목", list(stocks.keys()))
    inf = cache.get(stocks[pick]) or price_info(stocks[pick])
    if inf:
        st.line_chart(inf["hist"]["Close"])

with tab_news:
    st.subheader("뉴스창 + 자동 판단")
    alerts = []
    for n, t in stocks.items():
        info = cache.get(t) or price_info(t)
        news = google_news(f"{n} {t} 주식 OR stock", limit=8)
        scored = []
        for x in news:
            sc, lab, reason = score_title(x["title"])
            scored.append((sc, lab, reason, x))
        avg = int(sum([s[0] for s in scored]) / len(scored)) if scored else 50
        chg = info["chg"] if info else 0
        ma5 = info["ma5"] if info else 0
        ma20 = info["ma20"] if info else 0
        pred, conf, action = combined_prediction(avg, chg, ma5, ma20)

        today_rows.append({
            "date": date.today().isoformat(),
            "name": n,
            "ticker": t,
            "prediction": pred,
            "confidence": conf,
            "price": round(info["last"], 2) if info else "",
            "next_result_pct": "",
            "correct": ""
        })

        if conf >= 75 and "상승" in pred:
            alerts.append(f"🚨 {n}: 강한 상승 쪽 신호 {conf}점")
        if conf <= 35 or "주의" in pred:
            alerts.append(f"⚠️ {n}: 악재/주의 신호 {conf}점")

        with st.expander(f"{n} · 뉴스점수 {avg}/100 · {pred} · 확신 {conf}점", expanded=False):
            c1, c2, c3 = st.columns(3)
            c1.metric("뉴스 점수", f"{avg}/100")
            c2.metric("오늘 등락", f"{chg:+.2f}%")
            c3.metric("판단", pred)
            st.info(f"센스 판단: {action}")
            if not scored:
                st.warning("뉴스를 못 불러왔어. 인터넷/구글뉴스 연결 문제일 수 있음.")
            for sc, lab, reason, x in scored:
                emoji = "🟢" if lab == "호재" else "🔴" if lab == "악재" else "⚪"
                st.markdown(
                    f"<div class='news'>{emoji} <b>{lab} {sc}점</b> · "
                    f"<a href='{x['link']}' target='_blank'>{x['title']}</a><br>"
                    f"<span class='small'>{reason}</span></div>",
                    unsafe_allow_html=True
                )
    if alerts:
        st.warning("\n".join(alerts))
        st.toast(alerts[0])
    if st.button("📌 오늘 예측 저장"):
        save_predictions(today_rows)
        st.success("저장 완료. 다음 거래일 이후 예측 기록 탭에서 맞았는지 자동 판정.")

with tab_log:
    st.subheader("예측 기록 / 정확도")
    df = update_results()
    if df.empty:
        st.info("아직 기록 없음. 뉴스 탭에서 '오늘 예측 저장' 눌러.")
    else:
        st.dataframe(df, use_container_width=True)
        valid = df[df["correct"].isin([True, False])]
        if len(valid):
            st.metric("누적 정확도", f"{valid['correct'].mean()*100:.1f}%")
        else:
            st.caption("아직 판정 가능한 다음 거래일 결과가 없어.")
        st.download_button("기록 CSV 다운로드", df.to_csv(index=False, encoding="utf-8-sig"), "prediction_log.csv")

with tab_help:
    st.subheader("실행/사용법")
    st.code("python -m streamlit run app.py")
    st.write("V3인지 확인하는 법: 위에 탭이 `대시보드 / 뉴스·호재악재 / 예측 기록 / 사용법` 이렇게 보여야 함.")
    st.write("폰으로 보려면 CMD에 나오는 Network URL을 폰 브라우저에 입력. PC랑 폰은 같은 와이파이.")
    st.warning("투자 보조용임. 실제 매수/매도 책임은 본인에게 있음.")
