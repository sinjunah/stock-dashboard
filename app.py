
import os, re, json
from datetime import datetime, date, timedelta
import pandas as pd
import requests
import streamlit as st
import yfinance as yf

st.set_page_config(page_title="주식 감시 대시보드 V4", page_icon="📈", layout="wide")

STOCKS_FILE="stocks.json"
LOG_FILE="prediction_log.csv"

DEFAULT_STOCKS={
    "삼성전자":"005930.KS",
    "SK하이닉스":"000660.KS",
    "엔비디아":"NVDA",
    "테슬라":"TSLA",
    "AMD":"AMD",
    "SOXL":"SOXL",
}

GOOD=["상승","급등","호재","수주","계약","흑자","성장","상향","매수","공급","승인","성공","강세","반등","신고가","수혜","실적 개선","beat","surge","rally","record","growth","upgrade","profit","contract","approved","strong","bullish","buy"]
BAD=["하락","급락","악재","소송","리콜","적자","지연","금지","약세","위험","조사","감산","매도","하향","부진","경고","실패","miss","fall","drop","plunge","lawsuit","recall","downgrade","sell","loss","delay","ban","weak","risk","bearish"]
IMPORTANT=["HBM","AI","엔비디아","NVIDIA","반도체","실적","FOMC","CPI","금리","환율","관세","중국","대만","스페이스X","SpaceX","발사","테슬라","인도량"]

st.markdown("""
<style>
.block-container{padding-top:1.2rem;max-width:1250px}
.card{border:1px solid rgba(130,130,130,.25);border-radius:18px;padding:16px;margin-bottom:12px;background:rgba(255,255,255,.05)}
.good{background:linear-gradient(135deg,rgba(0,200,120,.16),rgba(0,120,255,.08))}
.bad{background:linear-gradient(135deg,rgba(255,70,70,.18),rgba(255,150,0,.08))}
.scorebig{font-size:34px;font-weight:900}
.small{opacity:.72;font-size:13px}
.newsitem{border:1px solid rgba(130,130,130,.22);border-radius:14px;padding:11px 13px;margin:8px 0;background:rgba(255,255,255,.045)}
</style>
""", unsafe_allow_html=True)

def read_json(path, default):
    if os.path.exists(path):
        try:
            with open(path,"r",encoding="utf-8") as f: return json.load(f)
        except Exception: pass
    return default

def write_json(path, data):
    with open(path,"w",encoding="utf-8") as f: json.dump(data,f,ensure_ascii=False,indent=2)

def load_stocks():
    data=read_json(STOCKS_FILE, DEFAULT_STOCKS.copy())
    if not isinstance(data,dict) or not data:
        data=DEFAULT_STOCKS.copy()
        write_json(STOCKS_FILE,data)
    return data

@st.cache_data(ttl=60)
def price_info(ticker):
    try:
        h=yf.Ticker(ticker).history(period="3mo", interval="1d")
        if h is None or h.empty: return None
        c=h["Close"].dropna()
        last=float(c.iloc[-1])
        prev=float(c.iloc[-2]) if len(c)>1 else last
        chg=(last-prev)/prev*100 if prev else 0
        ma5=float(c.tail(5).mean())
        ma20=float(c.tail(20).mean()) if len(c)>=20 else float(c.mean())
        hi=float(c.tail(20).max())
        lo=float(c.tail(20).min())
        return {"last":last,"chg":chg,"hist":h,"ma5":ma5,"ma20":ma20,"hi":hi,"lo":lo}
    except Exception:
        return None

@st.cache_data(ttl=180)
def news(query, limit=10):
    try:
        r=requests.get("https://news.google.com/rss/search",
            params={"q":query,"hl":"ko","gl":"KR","ceid":"KR:ko"}, timeout=8)
        r.raise_for_status()
        items=re.findall(r"<item>(.*?)</item>", r.text, flags=re.S)
        out=[]
        for it in items[:limit]:
            title=re.search(r"<title><!\[CDATA\[(.*?)\]\]></title>|<title>(.*?)</title>",it,flags=re.S)
            link=re.search(r"<link>(.*?)</link>",it,flags=re.S)
            pub=re.search(r"<pubDate>(.*?)</pubDate>",it,flags=re.S)
            tt=(title.group(1) or title.group(2) or "").strip() if title else ""
            tt=re.sub("<.*?>","",tt)
            out.append({"title":tt,"link":link.group(1).strip() if link else "", "published":pub.group(1).strip() if pub else ""})
        return out
    except Exception:
        return []

def score_title(title):
    t=title.lower()
    score=50; good=[]; bad=[]; imp=[]
    for w in GOOD:
        if w.lower() in t: score+=9; good.append(w)
    for w in BAD:
        if w.lower() in t: score-=10; bad.append(w)
    for w in IMPORTANT:
        if w.lower() in t: score+=3; imp.append(w)
    score=max(0,min(100,int(score)))
    label="호재" if score>=65 else "악재" if score<=40 else "중립"
    reason=[]
    if good: reason.append("호재:"+",".join(good[:3]))
    if bad: reason.append("악재:"+",".join(bad[:3]))
    if imp: reason.append("중요:"+",".join(imp[:3]))
    return score,label," / ".join(reason) if reason else "강한 키워드 없음"

def predict(news_score, info):
    s=news_score; reasons=[]
    if info:
        chg=info["chg"]
        if chg>3: s+=10; reasons.append("당일 강상승")
        elif chg>0: s+=4; reasons.append("당일 상승")
        elif chg<-3: s-=10; reasons.append("당일 급락")
        elif chg<0: s-=4; reasons.append("당일 하락")
        if info["ma5"]>info["ma20"]: s+=7; reasons.append("5일선>20일선")
        else: s-=7; reasons.append("5일선<20일선")
        if info["last"]>=info["hi"]*0.98: s+=4; reasons.append("20일 고점 근처")
        if info["last"]<=info["lo"]*1.02: s-=4; reasons.append("20일 저점 근처")
    s=max(0,min(100,int(s)))
    if s>=72: return "강한 상승 예상",s,"강세. 추격매수는 조심.",reasons
    if s>=60: return "상승 예상",s,"상승 쪽 우세.",reasons
    if s<=32: return "강한 하락/주의",s,"위험 신호 큼.",reasons
    if s<=43: return "하락/주의",s,"약세 쪽.",reasons
    return "관망",s,"방향 애매함.",reasons

def load_log():
    if os.path.exists(LOG_FILE):
        try: return pd.read_csv(LOG_FILE)
        except Exception: pass
    return pd.DataFrame(columns=["date","name","ticker","prediction","confidence","price","next_result_pct","correct"])

def save_preds(rows):
    df=load_log()
    today=date.today().isoformat()
    tickers=[r["ticker"] for r in rows]
    if not df.empty: df=df[~((df["date"]==today)&(df["ticker"].isin(tickers)))]
    df=pd.concat([df,pd.DataFrame(rows)], ignore_index=True)
    df.to_csv(LOG_FILE,index=False,encoding="utf-8-sig")
    return df

def update_results():
    df=load_log()
    if df.empty: return df
    changed=False
    for i,r in df.iterrows():
        if str(r.get("correct","")) not in ["","nan","None"]: continue
        d=pd.to_datetime(r["date"]).date()
        if d>=date.today(): continue
        try:
            h=yf.Ticker(r["ticker"]).history(start=d.isoformat(), end=(d+timedelta(days=7)).isoformat())
            c=h["Close"].dropna()
            if len(c)>=2:
                pct=(float(c.iloc[1])-float(c.iloc[0]))/float(c.iloc[0])*100
                df.loc[i,"next_result_pct"]=round(pct,2)
                pred=str(r["prediction"])
                if "상승" in pred: df.loc[i,"correct"]=bool(pct>0)
                elif "하락" in pred or "주의" in pred: df.loc[i,"correct"]=bool(pct<0)
                else: df.loc[i,"correct"]="관망"
                changed=True
        except Exception: pass
    if changed: df.to_csv(LOG_FILE,index=False,encoding="utf-8-sig")
    return df

stocks=load_stocks()
with st.sidebar:
    st.header("🎛 조종 패널")
    auto=st.toggle("자동 새로고침", value=True)
    sec=st.slider("새로고침 초",30,300,60,30)
    if auto: st.markdown(f"<meta http-equiv='refresh' content='{sec}'>", unsafe_allow_html=True)
    st.divider()
    st.subheader("➕ 종목 추가")
    nm=st.text_input("종목 이름", placeholder="예: 삼성전자")
    tk=st.text_input("티커", placeholder="예: 005930.KS / NVDA")
    if st.button("저장", use_container_width=True):
        if nm.strip() and tk.strip():
            stocks[nm.strip()]=tk.strip().upper()
            write_json(STOCKS_FILE,stocks)
            st.success("저장됨. 새로고침하면 반영.")
    delete=st.selectbox("삭제",["선택 안 함"]+list(stocks.keys()))
    if st.button("삭제", use_container_width=True) and delete!="선택 안 함":
        stocks.pop(delete,None)
        write_json(STOCKS_FILE,stocks)
        st.success("삭제됨. 새로고침하면 반영.")

st.title("📈 주식 감시 대시보드 V4")
st.caption(f"LIVE · {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} · 뉴스 자동감시 / 호재악재 / 예측기록")

tab1,tab2,tab3,tab4=st.tabs(["📊 대시보드","📰 뉴스·호재악재","🚨 신호","🔮 예측 기록"])
cache={}; today_rows=[]; rank=[]

with tab1:
    cols=st.columns(3)
    for idx,(n,t) in enumerate(stocks.items()):
        info=price_info(t); cache[t]=info
        with cols[idx%3]:
            if not info:
                st.markdown(f"<div class='card bad'><b>{n}</b><br>데이터 실패<br><span class='small'>{t}</span></div>", unsafe_allow_html=True)
            else:
                cls="good" if info["chg"]>=0 else "bad"
                st.markdown(f"<div class='card {cls}'><div class='small'>{n} · {t}</div><div class='scorebig'>{info['last']:,.2f}</div><div>{info['chg']:+.2f}%</div><div class='small'>5MA {info['ma5']:,.2f} / 20MA {info['ma20']:,.2f}</div></div>", unsafe_allow_html=True)
    pick=st.selectbox("차트 종목", list(stocks.keys()))
    inf=cache.get(stocks[pick]) or price_info(stocks[pick])
    if inf: st.line_chart(inf["hist"]["Close"])

with tab2:
    alerts=[]
    for n,t in stocks.items():
        info=cache.get(t) or price_info(t)
        ns=news(f"{n} {t} 주식 OR stock",10)
        scored=[(*score_title(x["title"]),x) for x in ns]
        avg=int(sum(s[0] for s in scored)/len(scored)) if scored else 50
        pred,conf,action,reasons=predict(avg,info)
        today_rows.append({"date":date.today().isoformat(),"name":n,"ticker":t,"prediction":pred,"confidence":conf,"price":round(info["last"],2) if info else "","next_result_pct":"","correct":""})
        rank.append([n,t,pred,conf,info["chg"] if info else 0,action])
        if conf>=72 and "상승" in pred: alerts.append(f"🟢 {n}: 상승 신호 {conf}점")
        if conf<=38 or "주의" in pred: alerts.append(f"🔴 {n}: 하락/주의 신호 {conf}점")
        with st.expander(f"{n} · 뉴스점수 {avg}/100 · {pred} · 확신 {conf}점"):
            st.info(f"{action} / 근거: {', '.join(reasons) if reasons else '뚜렷한 근거 부족'}")
            for sc,lab,reason,x in scored:
                emoji="🟢" if lab=="호재" else "🔴" if lab=="악재" else "⚪"
                st.markdown(f"<div class='newsitem'>{emoji} <b>{lab} {sc}점</b> · <a href='{x['link']}' target='_blank'>{x['title']}</a><br><span class='small'>{reason}</span></div>", unsafe_allow_html=True)
    if alerts:
        st.warning("\n".join(alerts))
        st.toast(alerts[0])
    if st.button("📌 오늘 예측 저장", use_container_width=True):
        save_preds(today_rows); st.success("저장 완료.")

with tab3:
    if rank:
        df=pd.DataFrame(rank, columns=["종목","티커","판단","확신점수","등락률","메모"]).sort_values("확신점수", ascending=False)
        st.dataframe(df,use_container_width=True)
    else:
        st.info("뉴스 탭을 먼저 열면 신호가 계산됨.")

with tab4:
    df=update_results()
    if df.empty: st.info("아직 기록 없음. 뉴스 탭에서 오늘 예측 저장 눌러.")
    else:
        st.dataframe(df,use_container_width=True)
        valid=df[df["correct"].isin([True,False])]
        if len(valid): st.metric("누적 정확도", f"{valid['correct'].mean()*100:.1f}%")
