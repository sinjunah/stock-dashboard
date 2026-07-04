
import os, re, json
from datetime import datetime, date, timedelta
import pandas as pd
import requests
import streamlit as st
import yfinance as yf

st.set_page_config(page_title="AI 주식 레이더 V5", page_icon="🚨", layout="wide")

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

GOOD=["상승","급등","호재","수주","계약","흑자","성장","상향","매수","공급","승인","성공","강세","반등","신고가","수혜","실적 개선","목표가 상향","beat","surge","rally","record","growth","upgrade","profit","contract","approved","strong","bullish","buy"]
BAD=["하락","급락","악재","소송","리콜","적자","지연","금지","약세","위험","조사","감산","매도","하향","부진","경고","실패","목표가 하향","miss","fall","drop","plunge","lawsuit","recall","downgrade","sell","loss","delay","ban","weak","risk","bearish"]
HOT=["HBM","AI","엔비디아","NVIDIA","반도체","실적","FOMC","CPI","금리","환율","관세","중국","대만","스페이스X","SpaceX","발사","스타십","Starship","테슬라","인도량","ETF","편입"]

CSS="""
<style>
.block-container{padding-top:1rem;max-width:1280px}
h1{font-size:2.1rem!important}
.hero{padding:18px;border-radius:22px;background:linear-gradient(135deg,rgba(0,210,255,.18),rgba(120,0,255,.12));border:1px solid rgba(160,160,160,.25);margin-bottom:16px}
.card{border:1px solid rgba(140,140,140,.23);border-radius:20px;padding:16px;background:rgba(255,255,255,.045);margin-bottom:12px;box-shadow:0 6px 18px rgba(0,0,0,.10)}
.good{background:linear-gradient(135deg,rgba(0,210,120,.20),rgba(0,120,255,.08))}
.bad{background:linear-gradient(135deg,rgba(255,55,80,.22),rgba(255,160,0,.08))}
.mid{background:rgba(150,150,150,.08)}
.big{font-size:34px;font-weight:900}
.tiny{opacity:.72;font-size:13px}
.news{border:1px solid rgba(140,140,140,.22);border-radius:15px;padding:12px 14px;margin:8px 0;background:rgba(255,255,255,.045)}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

def rjson(p,d):
    if os.path.exists(p):
        try:
            with open(p,"r",encoding="utf-8") as f:return json.load(f)
        except Exception:pass
    return d

def wjson(p,d):
    with open(p,"w",encoding="utf-8") as f:json.dump(d,f,ensure_ascii=False,indent=2)

def load_stocks():
    s=rjson(STOCKS_FILE,DEFAULT_STOCKS.copy())
    if not isinstance(s,dict) or not s:
        s=DEFAULT_STOCKS.copy(); wjson(STOCKS_FILE,s)
    return s

@st.cache_data(ttl=60)
def price(ticker):
    try:
        h=yf.Ticker(ticker).history(period="6mo",interval="1d")
        if h is None or h.empty:return None
        c=h["Close"].dropna()
        last=float(c.iloc[-1]); prev=float(c.iloc[-2]) if len(c)>1 else last
        chg=(last-prev)/prev*100 if prev else 0
        ma5=float(c.tail(5).mean())
        ma20=float(c.tail(20).mean()) if len(c)>=20 else float(c.mean())
        ma60=float(c.tail(60).mean()) if len(c)>=60 else float(c.mean())
        hi20=float(c.tail(20).max()); lo20=float(c.tail(20).min())
        vol=float(h["Volume"].dropna().iloc[-1]) if "Volume" in h and len(h["Volume"].dropna()) else 0
        avgv=float(h["Volume"].dropna().tail(20).mean()) if "Volume" in h and len(h["Volume"].dropna()) else 0
        return {"hist":h,"last":last,"chg":chg,"ma5":ma5,"ma20":ma20,"ma60":ma60,"hi20":hi20,"lo20":lo20,"vol":vol,"avgv":avgv}
    except Exception:
        return None

@st.cache_data(ttl=180)
def get_news(q,limit=12):
    try:
        r=requests.get("https://news.google.com/rss/search",params={"q":q,"hl":"ko","gl":"KR","ceid":"KR:ko"},timeout=8)
        r.raise_for_status()
        items=re.findall(r"<item>(.*?)</item>",r.text,flags=re.S)
        out=[]
        for it in items[:limit]:
            title=re.search(r"<title><!\[CDATA\[(.*?)\]\]></title>|<title>(.*?)</title>",it,flags=re.S)
            link=re.search(r"<link>(.*?)</link>",it,flags=re.S)
            pub=re.search(r"<pubDate>(.*?)</pubDate>",it,flags=re.S)
            tt=(title.group(1) or title.group(2) or "").strip() if title else ""
            tt=re.sub("<.*?>","",tt)
            out.append({"title":tt,"link":link.group(1).strip() if link else "","published":pub.group(1).strip() if pub else ""})
        return out
    except Exception:
        return []

def score_news(title):
    t=title.lower(); s=50; g=[]; b=[]; hot=[]
    for w in GOOD:
        if w.lower() in t:s+=9;g.append(w)
    for w in BAD:
        if w.lower() in t:s-=10;b.append(w)
    for w in HOT:
        if w.lower() in t:s+=4;hot.append(w)
    s=max(0,min(100,int(s)))
    lab="호재" if s>=65 else "악재" if s<=40 else "중립"
    reasons=[]
    if g:reasons.append("호재 "+",".join(g[:3]))
    if b:reasons.append("악재 "+",".join(b[:3]))
    if hot:reasons.append("핵심 "+",".join(hot[:3]))
    return s,lab," / ".join(reasons) if reasons else "강한 키워드 없음"

def ai_signal(news_score, info):
    s=news_score; why=[]
    if info:
        chg=info["chg"]
        if chg>4:s+=12;why.append("당일 급등")
        elif chg>1:s+=6;why.append("당일 상승세")
        elif chg<-4:s-=12;why.append("당일 급락")
        elif chg<-1:s-=6;why.append("당일 하락세")
        if info["ma5"]>info["ma20"]>info["ma60"]:s+=12;why.append("이평선 정배열")
        elif info["ma5"]>info["ma20"]:s+=7;why.append("단기 추세 양호")
        elif info["ma5"]<info["ma20"]<info["ma60"]:s-=12;why.append("이평선 역배열")
        elif info["ma5"]<info["ma20"]:s-=7;why.append("단기 추세 약함")
        if info["last"]>=info["hi20"]*0.98:s+=5;why.append("20일 고점 근처")
        if info["last"]<=info["lo20"]*1.02:s-=5;why.append("20일 저점 근처")
        if info["avgv"] and info["vol"]>info["avgv"]*1.8:
            s+=5 if chg>0 else -5
            why.append("거래량 급증")
    s=max(0,min(100,int(s)))
    up=s; down=100-s
    if s>=75:return "강한 상승",up,down,"관심↑ 단 추격매수 조심",why
    if s>=60:return "상승 우세",up,down,"눌림/분할 접근 쪽",why
    if s<=30:return "강한 하락",up,down,"관망 우선",why
    if s<=42:return "하락 우세",up,down,"악재 확인 전 매수 금지",why
    return "관망",up,down,"방향 애매함",why

def load_log():
    if os.path.exists(LOG_FILE):
        try:return pd.read_csv(LOG_FILE)
        except Exception:pass
    return pd.DataFrame(columns=["date","name","ticker","signal","up_pct","down_pct","price","next_result_pct","correct"])

def save_log(rows):
    df=load_log(); today=date.today().isoformat(); tick=[r["ticker"] for r in rows]
    if not df.empty: df=df[~((df["date"]==today)&(df["ticker"].isin(tick)))]
    df=pd.concat([df,pd.DataFrame(rows)],ignore_index=True)
    df.to_csv(LOG_FILE,index=False,encoding="utf-8-sig")

def update_log():
    df=load_log()
    if df.empty:return df
    changed=False
    for i,r in df.iterrows():
        if str(r.get("correct","")) not in ["","nan","None"]:continue
        d=pd.to_datetime(r["date"]).date()
        if d>=date.today():continue
        try:
            h=yf.Ticker(r["ticker"]).history(start=d.isoformat(),end=(d+timedelta(days=7)).isoformat())
            c=h["Close"].dropna()
            if len(c)>=2:
                pct=(float(c.iloc[1])-float(c.iloc[0]))/float(c.iloc[0])*100
                df.loc[i,"next_result_pct"]=round(pct,2)
                sig=str(r["signal"])
                if "상승" in sig:df.loc[i,"correct"]=bool(pct>0)
                elif "하락" in sig:df.loc[i,"correct"]=bool(pct<0)
                else:df.loc[i,"correct"]="관망"
                changed=True
        except Exception:pass
    if changed:df.to_csv(LOG_FILE,index=False,encoding="utf-8-sig")
    return df

stocks=load_stocks()

with st.sidebar:
    st.header("⚙️ 설정")
    auto=st.toggle("자동 새로고침",value=True)
    sec=st.slider("간격(초)",30,300,60,30)
    if auto:st.markdown(f"<meta http-equiv='refresh' content='{sec}'>",unsafe_allow_html=True)
    st.divider()
    st.subheader("⭐ 관심종목")
    nm=st.text_input("종목 이름",placeholder="예: 삼성전자")
    tk=st.text_input("티커",placeholder="005930.KS / NVDA")
    if st.button("추가/저장",use_container_width=True):
        if nm and tk:
            stocks[nm.strip()]=tk.strip().upper(); wjson(STOCKS_FILE,stocks); st.success("저장됨")
    rm=st.selectbox("삭제",["선택 안 함"]+list(stocks.keys()))
    if st.button("삭제",use_container_width=True) and rm!="선택 안 함":
        stocks.pop(rm,None); wjson(STOCKS_FILE,stocks); st.success("삭제됨")

st.markdown("<div class='hero'><h1>🚨 AI 주식 레이더 V5</h1><div>뉴스 · 호재/악재 · 상승확률 · 신호랭킹 · 예측정확도</div></div>",unsafe_allow_html=True)
st.caption(f"업데이트: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

tab0,tab1,tab2,tab3,tab4=st.tabs(["🚨 레이더","📊 대시보드","📰 뉴스","📈 차트","🎯 기록"])
cache={}; rows=[]; radar=[]; all_news=[]

for n,t in stocks.items():
    info=price(t); cache[t]=info
    ns=get_news(f"{n} {t} 주식 OR stock",12)
    scored=[(*score_news(x["title"]),x) for x in ns]
    avg=int(sum(x[0] for x in scored)/len(scored)) if scored else 50
    sig,up,down,memo,why=ai_signal(avg,info)
    radar.append({"종목":n,"티커":t,"신호":sig,"상승확률":up,"하락확률":down,"뉴스점수":avg,"등락률":round(info["chg"],2) if info else 0,"메모":memo,"근거":", ".join(why)})
    rows.append({"date":date.today().isoformat(),"name":n,"ticker":t,"signal":sig,"up_pct":up,"down_pct":down,"price":round(info["last"],2) if info else "","next_result_pct":"","correct":""})
    for x in scored: all_news.append((n,)+x)

with tab0:
    df=pd.DataFrame(radar).sort_values("상승확률",ascending=False)
    c1,c2,c3=st.columns(3)
    if len(df):
        top=df.iloc[0]; weak=df.sort_values("하락확률",ascending=False).iloc[0]
        c1.metric("오늘 가장 강한 종목",top["종목"],f'{top["상승확률"]}점')
        c2.metric("주의 종목",weak["종목"],f'{weak["하락확률"]}점')
        c3.metric("감시 종목 수",len(df))
    st.dataframe(df,use_container_width=True)
    hot=df[(df["상승확률"]>=75)|(df["하락확률"]>=70)]
    if not hot.empty:
        st.warning("🚨 강한 신호 감지\n\n"+"\n".join([f'{r["종목"]}: {r["신호"]} ({r["상승확률"]}/{r["하락확률"]})' for _,r in hot.iterrows()]))
    if st.button("오늘 예측 저장",use_container_width=True):
        save_log(rows); st.success("저장 완료")

with tab1:
    cols=st.columns(3)
    for idx,(n,t) in enumerate(stocks.items()):
        info=cache.get(t)
        with cols[idx%3]:
            if info:
                cls="good" if info["chg"]>=0 else "bad"
                st.markdown(f"<div class='card {cls}'><div class='tiny'>{n} · {t}</div><div class='big'>{info['last']:,.2f}</div><div>{info['chg']:+.2f}%</div><div class='tiny'>5MA {info['ma5']:,.2f} / 20MA {info['ma20']:,.2f} / 60MA {info['ma60']:,.2f}</div></div>",unsafe_allow_html=True)
            else:
                st.markdown(f"<div class='card bad'><b>{n}</b><br>데이터 실패</div>",unsafe_allow_html=True)

with tab2:
    for stock,sc,lab,reason,x in sorted(all_news,key=lambda z:z[1],reverse=True):
        emoji="🟢" if lab=="호재" else "🔴" if lab=="악재" else "⚪"
        st.markdown(f"<div class='news'>{emoji} <b>{stock} · {lab} {sc}점</b><br><a href='{x['link']}' target='_blank'>{x['title']}</a><br><span class='tiny'>{reason}</span></div>",unsafe_allow_html=True)

with tab3:
    pick=st.selectbox("차트 종목",list(stocks.keys()))
    info=cache.get(stocks[pick])
    if info:
        chart=info["hist"][["Close"]].copy()
        chart["MA5"]=chart["Close"].rolling(5).mean()
        chart["MA20"]=chart["Close"].rolling(20).mean()
        chart["MA60"]=chart["Close"].rolling(60).mean()
        st.line_chart(chart)

with tab4:
    log=update_log()
    if log.empty:st.info("아직 기록 없음. 레이더 탭에서 오늘 예측 저장 눌러.")
    else:
        st.dataframe(log,use_container_width=True)
        valid=log[log["correct"].isin([True,False])]
        if len(valid):st.metric("누적 정확도",f"{valid['correct'].mean()*100:.1f}%")
        st.download_button("CSV 다운로드",log.to_csv(index=False,encoding="utf-8-sig"),"prediction_log.csv")
