
import os, re, json
from datetime import datetime, date, timedelta
import pandas as pd
import requests
import streamlit as st
import yfinance as yf

st.set_page_config(page_title="AI 주식 레이더", page_icon="📈", layout="wide", initial_sidebar_state="expanded")

STOCKS_FILE="stocks.json"
LOG_FILE="prediction_log.csv"

DEFAULT_STOCKS={"삼성전자":"005930.KS","SK하이닉스":"000660.KS","엔비디아":"NVDA","테슬라":"TSLA","AMD":"AMD","SOXL":"SOXL"}

SEARCH_MAP={
    "삼성":"삼성전자|005930.KS","삼성전자":"삼성전자|005930.KS","005930":"삼성전자|005930.KS",
    "하이닉스":"SK하이닉스|000660.KS","sk하이닉스":"SK하이닉스|000660.KS","000660":"SK하이닉스|000660.KS",
    "엔비":"엔비디아|NVDA","엔비디아":"엔비디아|NVDA","nvidia":"엔비디아|NVDA","nvda":"엔비디아|NVDA",
    "테슬라":"테슬라|TSLA","tesla":"테슬라|TSLA","tsla":"테슬라|TSLA",
    "amd":"AMD|AMD","에이엠디":"AMD|AMD",
    "soxl":"SOXL|SOXL",
    "애플":"애플|AAPL","apple":"애플|AAPL","aapl":"애플|AAPL",
    "마소":"마이크로소프트|MSFT","마이크로소프트":"마이크로소프트|MSFT","msft":"마이크로소프트|MSFT",
    "구글":"알파벳|GOOGL","알파벳":"알파벳|GOOGL","googl":"알파벳|GOOGL",
    "아마존":"아마존|AMZN","amazon":"아마존|AMZN","amzn":"아마존|AMZN",
    "메타":"메타|META","meta":"메타|META",
    "tsmc":"TSMC|TSM","티에스엠씨":"TSMC|TSM",
    "브로드컴":"브로드컴|AVGO","avgo":"브로드컴|AVGO",
    "팔란티어":"팔란티어|PLTR","pltr":"팔란티어|PLTR",
    "코스피":"KOSPI|^KS11","나스닥":"NASDAQ|^IXIC","s&p":"S&P500|^GSPC","sp500":"S&P500|^GSPC",
}

GOOD=["상승","급등","호재","수주","계약","흑자","성장","상향","매수","공급","승인","성공","강세","반등","신고가","수혜","실적 개선","목표가 상향","beat","surge","rally","record","growth","upgrade","profit","contract","approved","strong","bullish","buy"]
BAD=["하락","급락","악재","소송","리콜","적자","지연","금지","약세","위험","조사","감산","매도","하향","부진","경고","실패","목표가 하향","miss","fall","drop","plunge","lawsuit","recall","downgrade","sell","loss","delay","ban","weak","risk","bearish"]
HOT=["HBM","AI","엔비디아","NVIDIA","반도체","실적","earnings","FOMC","CPI","금리","환율","관세","중국","대만","스페이스X","SpaceX","발사","스타십","Starship","테슬라","인도량","ETF","편입"]

CSS="""
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;600;700;900&display=swap');
html, body, [class*="css"] {font-family:'Noto Sans KR', sans-serif;}
.stApp {background: radial-gradient(circle at top left,#101d37 0,#070a10 42%,#03050a 100%); color:#f3f6ff;}
.block-container{padding-top:.8rem;max-width:1280px}
.hero{padding:20px;border-radius:26px;background:linear-gradient(135deg,rgba(0,180,255,.20),rgba(80,60,255,.13));border:1px solid rgba(160,180,255,.18);margin-bottom:14px;box-shadow:0 14px 40px rgba(0,0,0,.25)}
.hero h1{font-size:2rem!important;margin-bottom:.15rem}
.card{border:1px solid rgba(180,190,220,.15);border-radius:22px;padding:17px;background:rgba(255,255,255,.052);margin-bottom:13px;box-shadow:0 10px 28px rgba(0,0,0,.18)}
.green{background:linear-gradient(135deg,rgba(0,210,120,.20),rgba(0,120,255,.08))}
.red{background:linear-gradient(135deg,rgba(255,55,80,.22),rgba(255,160,0,.07))}
.orange{background:linear-gradient(135deg,rgba(255,165,0,.18),rgba(255,255,255,.045))}
.blue{background:linear-gradient(135deg,rgba(0,140,255,.17),rgba(255,255,255,.045))}
.big{font-size:34px;font-weight:900;letter-spacing:-.5px}
.midtitle{font-size:18px;font-weight:800}
.tiny{opacity:.72;font-size:13px;line-height:1.45}
.badge{display:inline-block;padding:5px 10px;border-radius:999px;background:rgba(255,255,255,.12);font-size:12px;margin-right:6px}
.news{border:1px solid rgba(180,190,220,.15);border-radius:16px;padding:13px 15px;margin:9px 0;background:rgba(255,255,255,.052)}
.rankrow{border:1px solid rgba(180,190,220,.15);border-radius:18px;padding:14px 15px;margin:9px 0;background:rgba(255,255,255,.052)}
.barbg{height:8px;border-radius:99px;background:rgba(255,255,255,.13);margin-top:8px;overflow:hidden}
.barg{height:8px;background:#00d084;border-radius:99px}
.barr{height:8px;background:#ff4d5d;border-radius:99px}
[data-testid="stDataFrame"] {background: rgba(255,255,255,.03); border-radius:18px; overflow:hidden}
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

def resolve_stock(text):
    q=text.strip().lower()
    if not q:return None
    if q in SEARCH_MAP:
        name,ticker=SEARCH_MAP[q].split("|")
        return name,ticker
    if re.fullmatch(r"[A-Za-z.^]{1,8}", text.strip()):
        return text.strip().upper(), text.strip().upper()
    if re.fullmatch(r"\d{6}", text.strip()):
        return text.strip(), text.strip()+".KS"
    return None

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
    except Exception:return None

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
    except Exception:return []

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
    if g:reasons.append("긍정 이슈 "+",".join(g[:3]))
    if b:reasons.append("부정 이슈 "+",".join(b[:3]))
    if hot:reasons.append("핵심 키워드 "+",".join(hot[:3]))
    return s,lab," / ".join(reasons) if reasons else "강한 키워드 없음"

def stars(v):
    x=max(1,min(5,round(v/20)))
    return "★"*x+"☆"*(5-x)

def ai_signal(news_score, info):
    s=news_score; why=[]
    if info:
        chg=info["chg"]
        if chg>4:s+=12;why.append("오늘 매수세가 꽤 강함")
        elif chg>1:s+=6;why.append("최근 흐름이 위쪽으로 기울어짐")
        elif chg<-4:s-=12;why.append("오늘 매도 압력이 강함")
        elif chg<-1:s-=6;why.append("최근 흐름이 약해짐")
        if info["ma5"]>info["ma20"]>info["ma60"]:s+=12;why.append("단기·중기 흐름이 모두 좋아짐")
        elif info["ma5"]>info["ma20"]:s+=7;why.append("짧은 기간 흐름이 회복 중")
        elif info["ma5"]<info["ma20"]<info["ma60"]:s-=12;why.append("전체 흐름이 아직 무거움")
        elif info["ma5"]<info["ma20"]:s-=7;why.append("짧은 기간 힘이 약함")
        if info["last"]>=info["hi20"]*0.98:s+=5;why.append("최근 고점 근처까지 올라옴")
        if info["last"]<=info["lo20"]*1.02:s-=5;why.append("최근 저점 근처라 불안정함")
        if info["avgv"] and info["vol"]>info["avgv"]*1.8:
            s+=5 if chg>0 else -5
            why.append("평소보다 거래가 활발함")
    s=max(0,min(100,int(s)))
    if s>=75:return "강한 상승",s,100-s,"관심 높게. 단, 급하게 따라 사는 건 조심.",why
    if s>=60:return "상승 우세",s,100-s,"상승 쪽이 조금 더 유리함.",why
    if s<=30:return "강한 하락",s,100-s,"위험 신호가 강해서 관망 우선.",why
    if s<=42:return "하락 우세",s,100-s,"약세 쪽이라 새 매수는 신중.",why
    return "관망",s,100-s,"방향이 애매해서 추가 확인 필요.",why

def period_text():
    s=date.today()+timedelta(days=1); e=date.today()+timedelta(days=4)
    return f"{s.strftime('%m/%d')} ~ {e.strftime('%m/%d')} 기준"

def market_calendar():
    today=date.today()
    fixed=[
        [today+timedelta(days=1),"미국 CPI / 물가 관련 일정 확인","시장 전체 흔들릴 수 있음","경제"],
        [today+timedelta(days=3),"FOMC·금리 발언 체크","반도체·성장주 영향 큼","경제"],
        [today+timedelta(days=5),"주요 빅테크 실적 시즌 감시","엔비디아·AMD·테슬라 영향 가능","실적"],
        [today+timedelta(days=7),"반도체 공급망 뉴스 체크","삼성·하이닉스·TSMC 관련","산업"],
        [today+timedelta(days=10),"ETF 리밸런싱/편입 이슈 확인","테마 ETF 변동 가능","ETF"],
        [today+timedelta(days=14),"우주·방산 테마 뉴스 체크","SpaceX/발사/위성 관련주","테마"],
    ]
    earnings = []
    names=["엔비디아","테슬라","AMD","애플","마이크로소프트","구글","아마존","메타","TSMC","브로드컴","삼성전자","SK하이닉스"]
    for i,n in enumerate(names):
        earnings.append([today+timedelta(days=2+i*2),f"{n} 실적 발표/가이던스 확인","정확한 날짜는 기업 공시 기준으로 재확인 필요","실적"])
    return sorted(fixed+earnings, key=lambda x:x[0])

def load_log():
    if os.path.exists(LOG_FILE):
        try:return pd.read_csv(LOG_FILE)
        except Exception:pass
    return pd.DataFrame(columns=["date","period","name","ticker","signal","up_pct","down_pct","price","next_result_pct","correct"])

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
    st.caption("자동 새로고침은 화면 전체를 심하게 깜빡이지 않게 기본 간격을 길게 잡았어.")
    auto=st.toggle("자동 새로고침",value=True)
    sec=st.slider("간격(초)",60,600,180,30)
    if auto:st.markdown(f"<meta http-equiv='refresh' content='{sec}'>",unsafe_allow_html=True)
    st.divider()
    st.subheader("⭐ 종목 찾기")
    q=st.text_input("종목 이름만 입력",placeholder="삼성전자 / 엔비디아 / 테슬라 / AAPL")
    found=resolve_stock(q) if q else None
    if found:
        st.success(f"찾음: {found[0]} · {found[1]}")
    elif q:
        st.warning("못 찾으면 티커를 직접 입력해도 됨. 예: NVDA, 005930")
    if st.button("추가/저장",use_container_width=True):
        if found:
            stocks[found[0]]=found[1]; wjson(STOCKS_FILE,stocks); st.success("저장됨")
        else:
            st.warning("종목을 못 찾았어.")
    rm=st.selectbox("삭제",["선택 안 함"]+list(stocks.keys()))
    if st.button("삭제",use_container_width=True) and rm!="선택 안 함":
        stocks.pop(rm,None); wjson(STOCKS_FILE,stocks); st.success("삭제됨")

st.markdown("<div class='hero'><h1>📈 AI 주식 레이더</h1><div>오늘 시장에서 중요한 흐름, 뉴스, 일정, 관심 종목을 한눈에 확인하세요.</div></div>",unsafe_allow_html=True)
st.caption(f"업데이트: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} · 예측기간: {period_text()}")

tabs=st.tabs(["🏠 브리핑","🚨 긴급 속보","📅 전체 캘린더","📊 종목 카드","📰 뉴스","📈 차트","🎯 기록"])
cache={}; rows=[]; radar=[]; all_news=[]

for n,t in stocks.items():
    info=price(t); cache[t]=info
    ns=get_news(f"{n} {t} 주식 OR stock",12)
    scored=[(*score_news(x["title"]),x) for x in ns]
    avg=int(sum(x[0] for x in scored)/len(scored)) if scored else 50
    sig,up,down,memo,why=ai_signal(avg,info)
    radar.append({"종목":n,"티커":t,"신호":sig,"상승확률":up,"하락확률":down,"뉴스점수":avg,"등락률":round(info["chg"],2) if info else 0,"메모":memo,"근거":" · ".join(why),"기간":period_text()})
    rows.append({"date":date.today().isoformat(),"period":period_text(),"name":n,"ticker":t,"signal":sig,"up_pct":up,"down_pct":down,"price":round(info["last"],2) if info else "","next_result_pct":"","correct":""})
    for x in scored: all_news.append((n,)+x)

df=pd.DataFrame(radar).sort_values("상승확률",ascending=False) if radar else pd.DataFrame()

with tabs[0]:
    if not df.empty:
        top=df.iloc[0]; weak=df.sort_values("하락확률",ascending=False).iloc[0]
        st.markdown(f"<div class='card blue'><div class='midtitle'>📌 오늘 한 줄 브리핑</div>오늘은 <b>{top['종목']}</b>가 가장 강하게 잡혀. 예측 기간은 <b>{period_text()}</b>이고, 상승 가능성은 <b>{top['상승확률']}%</b>야.<br>반대로 <b>{weak['종목']}</b>는 주의 신호가 상대적으로 높아.</div>",unsafe_allow_html=True)
        c1,c2,c3=st.columns(3)
        c1.markdown(f"<div class='card green'><div class='tiny'>🥇 가장 강한 종목</div><div class='big'>{top['종목']}</div><div>{top['상승확률']}% · {stars(top['상승확률'])}</div><div class='tiny'>{top['메모']}</div></div>",unsafe_allow_html=True)
        c2.markdown(f"<div class='card red'><div class='tiny'>⚠️ 주의 종목</div><div class='big'>{weak['종목']}</div><div>하락주의 {weak['하락확률']}%</div><div class='tiny'>{weak['메모']}</div></div>",unsafe_allow_html=True)
        c3.markdown(f"<div class='card orange'><div class='tiny'>⏱ 예측 기준</div><div class='big'>3~4일</div><div>{period_text()}</div><div class='tiny'>단기 뉴스/차트 흐름 기준</div></div>",unsafe_allow_html=True)
        st.subheader("신호 랭킹")
        for _,r in df.iterrows():
            cls="green" if r["상승확률"]>=60 else "red" if r["하락확률"]>=60 else "orange"
            bar = r["상승확률"]
            st.markdown(f"<div class='rankrow {cls}'><b>{r['종목']}</b> <span class='badge'>{r['신호']}</span><span class='tiny'>{r['기간']}</span><br>상승 가능성 {r['상승확률']}% / 하락 주의 {r['하락확률']}%<div class='barbg'><div class='barg' style='width:{bar}%'></div></div><div class='tiny'>{r['메모']} · {r['근거']}</div></div>",unsafe_allow_html=True)
        if st.button("오늘 예측 저장",use_container_width=True):
            save_log(rows); st.success("저장 완료")

with tabs[1]:
    hot_news=[]
    for stock,sc,lab,reason,x in all_news:
        if sc>=75 or sc<=30: hot_news.append((stock,sc,lab,reason,x))
    if hot_news:
        for stock,sc,lab,reason,x in sorted(hot_news,key=lambda z:abs(z[1]-50),reverse=True)[:10]:
            cls="green" if lab=="호재" else "red"
            st.markdown(f"<div class='card {cls}'><span class='badge'>🚨 긴급</span><span class='badge'>{stock}</span><div class='midtitle'>{lab} {sc}점</div><a href='{x['link']}' target='_blank'>{x['title']}</a><div class='tiny'>{reason}</div></div>",unsafe_allow_html=True)
    else: st.info("지금은 강한 속보 신호가 없어.")

with tabs[2]:
    st.subheader("📅 전체 시장 캘린더")
    st.caption("무료 공개 데이터 기반이라 정확한 실적일은 기업 공시/증권사 캘린더로 한 번 더 확인하는 게 좋아.")
    for d,title,memo,typ in market_calendar():
        st.markdown(f"<div class='card blue'><span class='badge'>{typ}</span><span class='badge'>{d.strftime('%m/%d')}</span><b>{title}</b><br><span class='tiny'>{memo}</span></div>",unsafe_allow_html=True)

with tabs[3]:
    cols=st.columns(2)
    for i,r in df.iterrows():
        cls="green" if r["상승확률"]>=60 else "red" if r["하락확률"]>=60 else "orange"
        with cols[i%2]:
            st.markdown(f"<div class='card {cls}'><div class='tiny'>{r['종목']} · {r['티커']}</div><div class='big'>{r['신호']}</div><div>상승 {r['상승확률']}% / 하락 {r['하락확률']}%</div><div>{stars(r['상승확률'])}</div><div class='tiny'>{r['기간']}<br>{r['메모']}<br>{r['근거']}</div></div>",unsafe_allow_html=True)

with tabs[4]:
    for stock,sc,lab,reason,x in sorted(all_news,key=lambda z:z[1],reverse=True):
        emoji="🟢" if lab=="호재" else "🔴" if lab=="악재" else "⚪"
        st.markdown(f"<div class='news'>{emoji} <b>{stock} · {lab} {sc}점</b><br><a href='{x['link']}' target='_blank'>{x['title']}</a><br><span class='tiny'>{reason}</span></div>",unsafe_allow_html=True)

with tabs[5]:
    pick=st.selectbox("차트 종목",list(stocks.keys()))
    info=cache.get(stocks[pick])
    if info:
        chart=info["hist"][["Close"]].copy()
        chart["짧은 흐름"]=chart["Close"].rolling(5).mean()
        chart["중간 흐름"]=chart["Close"].rolling(20).mean()
        chart["긴 흐름"]=chart["Close"].rolling(60).mean()
        st.line_chart(chart)

with tabs[6]:
    log=update_log()
    if log.empty:st.info("아직 기록 없음. 브리핑 탭에서 오늘 예측 저장 눌러.")
    else:
        st.dataframe(log,use_container_width=True)
        valid=log[log["correct"].isin([True,False])]
        if len(valid):st.metric("누적 정확도",f"{valid['correct'].mean()*100:.1f}%")
        st.download_button("CSV 다운로드",log.to_csv(index=False,encoding="utf-8-sig"),"prediction_log.csv")

st.warning("투자 보조용 도구야. 실제 매수/매도는 반드시 본인이 판단해야 함.")
