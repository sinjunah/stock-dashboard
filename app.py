
import os,re,json
from datetime import datetime,date,timedelta
import pandas as pd
import requests, streamlit as st, yfinance as yf
try:
    from pykrx import stock as krx_stock
except Exception:
    krx_stock=None

st.set_page_config(page_title="AI 주식 레이더",page_icon="📈",layout="wide",initial_sidebar_state="expanded")
STOCKS_FILE="stocks.json"; PORTFOLIO_FILE="portfolio.json"; MEMO_FILE="memos.json"; LOG_FILE="prediction_log.csv"

DEFAULT_STOCKS={"삼성전자":"005930.KS","SK하이닉스":"000660.KS","엔비디아":"NVDA","테슬라":"TSLA","AMD":"AMD","SOXL":"SOXL","SOXS":"SOXS","TQQQ":"TQQQ","SQQQ":"SQQQ","대우건설":"047040.KS","샌디스크":"SNDK","KODEX 레버리지":"122630.KS","KODEX 200선물인버스2X":"252670.KS"}
SEARCH_MAP={
"삼성":"삼성전자|005930.KS","삼성전자":"삼성전자|005930.KS","하이닉스":"SK하이닉스|000660.KS","sk하이닉스":"SK하이닉스|000660.KS",
"대우건설":"대우건설|047040.KS","대우":"대우건설|047040.KS","샌디스크":"샌디스크|SNDK","sandisk":"샌디스크|SNDK","sndk":"샌디스크|SNDK",
"엔비":"엔비디아|NVDA","엔비디아":"엔비디아|NVDA","nvidia":"엔비디아|NVDA","nvda":"엔비디아|NVDA","테슬라":"테슬라|TSLA","tsla":"테슬라|TSLA",
"soxl":"SOXL|SOXL","soxs":"SOXS|SOXS","tqqq":"TQQQ|TQQQ","sqqq":"SQQQ|SQQQ","spxl":"SPXL|SPXL","spxs":"SPXS|SPXS","nvdl":"NVDL|NVDL","tsll":"TSLL|TSLL",
"레버리지":"KODEX 레버리지|122630.KS","kodex 레버리지":"KODEX 레버리지|122630.KS","코덱스 레버리지":"KODEX 레버리지|122630.KS",
"인버스":"KODEX 인버스|114800.KS","kodex 인버스":"KODEX 인버스|114800.KS","곱버스":"KODEX 200선물인버스2X|252670.KS","인버스2x":"KODEX 200선물인버스2X|252670.KS",
"sol ai반도체top2":"SOL AI반도체TOP2 Plus|486450.KS","sol ai반도체top2 plus":"SOL AI반도체TOP2 Plus|486450.KS",
"애플":"애플|AAPL","aapl":"애플|AAPL","마소":"마이크로소프트|MSFT","msft":"마이크로소프트|MSFT","구글":"알파벳|GOOGL","googl":"알파벳|GOOGL","아마존":"아마존|AMZN","amzn":"아마존|AMZN","메타":"메타|META","meta":"메타|META",
"현대차":"현대차|005380.KS","기아":"기아|000270.KS","카카오":"카카오|035720.KS","네이버":"NAVER|035420.KS","셀트리온":"셀트리온|068270.KS","한화에어로":"한화에어로스페이스|012450.KS","두산에너빌리티":"두산에너빌리티|034020.KS"}
GOOD=["상승","급등","호재","수주","계약","흑자","성장","상향","매수","공급","승인","성공","강세","반등","신고가","수혜","실적 개선","목표가 상향","beat","surge","rally","record","growth","upgrade","profit","contract","approved","strong","bullish","buy"]
BAD=["하락","급락","악재","소송","리콜","적자","지연","금지","약세","위험","조사","감산","매도","하향","부진","경고","실패","목표가 하향","miss","fall","drop","plunge","lawsuit","recall","downgrade","sell","loss","delay","ban","weak","risk","bearish"]
HOT=["HBM","AI","엔비디아","NVIDIA","반도체","실적","earnings","FOMC","CPI","금리","환율","관세","스페이스X","SpaceX","ETF","편입","레버리지","인버스"]

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;600;700;900&display=swap');
html,body,[class*="css"]{font-family:'Noto Sans KR',sans-serif}.stApp{background:radial-gradient(circle at top left,#101d37 0,#070a10 42%,#03050a 100%);color:#f3f6ff}.block-container{padding-top:.8rem;max-width:1280px}.hero{padding:20px;border-radius:26px;background:linear-gradient(135deg,rgba(0,180,255,.20),rgba(80,60,255,.13));border:1px solid rgba(160,180,255,.18);margin-bottom:14px;box-shadow:0 14px 40px rgba(0,0,0,.25)}.card{border:1px solid rgba(180,190,220,.15);border-radius:22px;padding:17px;background:rgba(255,255,255,.052);margin-bottom:13px;box-shadow:0 10px 28px rgba(0,0,0,.18)}.green{background:linear-gradient(135deg,rgba(0,210,120,.20),rgba(0,120,255,.08))}.red{background:linear-gradient(135deg,rgba(255,55,80,.22),rgba(255,160,0,.07))}.orange{background:linear-gradient(135deg,rgba(255,165,0,.18),rgba(255,255,255,.045))}.blue{background:linear-gradient(135deg,rgba(0,140,255,.17),rgba(255,255,255,.045))}.big{font-size:34px;font-weight:900}.tiny{opacity:.72;font-size:13px;line-height:1.45}.badge{display:inline-block;padding:5px 10px;border-radius:999px;background:rgba(255,255,255,.12);font-size:12px;margin-right:6px}.news{border:1px solid rgba(180,190,220,.15);border-radius:16px;padding:13px 15px;margin:9px 0;background:rgba(255,255,255,.052)}.rankrow{border:1px solid rgba(180,190,220,.15);border-radius:18px;padding:14px 15px;margin:9px 0;background:rgba(255,255,255,.052)}.barbg{height:8px;border-radius:99px;background:rgba(255,255,255,.13);margin-top:8px;overflow:hidden}.barg{height:8px;background:#00d084;border-radius:99px}
</style>""",unsafe_allow_html=True)

def rjson(p,d):
    if os.path.exists(p):
        try:
            with open(p,"r",encoding="utf-8") as f:return json.load(f)
        except Exception: pass
    return d
def wjson(p,d):
    with open(p,"w",encoding="utf-8") as f: json.dump(d,f,ensure_ascii=False,indent=2)
def is_kr(t): return t.endswith(".KS") or t.endswith(".KQ")
def is_us(t): return not is_kr(t) and not t.startswith("^")
@st.cache_data(ttl=600)
def fx_rate():
    try:
        h=yf.Ticker("USDKRW=X").history(period="5d")
        if h is not None and not h.empty:return float(h["Close"].dropna().iloc[-1])
    except Exception: pass
    return 1380.0
def to_krw(v,t): return (v*fx_rate()) if is_us(t) else v
def money(v):
    try:return f"{v:,.0f}원"
    except Exception:return "0원"

@st.cache_data(ttl=3600)
def krx_search(q):
    if krx_stock is None:return []
    try:
        codes=krx_stock.get_market_ticker_list(date.today().strftime("%Y%m%d"),market="ALL")
        s=q.lower().replace(" ",""); out=[]
        for c in codes:
            n=krx_stock.get_market_ticker_name(c)
            if s in n.lower().replace(" ","") or q in c: out.append((n,c+".KS"))
        return out[:10]
    except Exception:return []
@st.cache_data(ttl=3600)
def yahoo_search(q):
    try:
        r=requests.get("https://query1.finance.yahoo.com/v1/finance/search",params={"q":q,"quotesCount":10,"newsCount":0},timeout=8,headers={"User-Agent":"Mozilla/5.0"})
        arr=[]
        for x in r.json().get("quotes",[]):
            sym=x.get("symbol",""); name=x.get("shortname") or x.get("longname") or sym; typ=x.get("quoteType","")
            if sym and typ in ["EQUITY","ETF","INDEX"]: arr.append((name,sym))
        return arr[:8]
    except Exception:return []
def candidates(q):
    q=q.strip(); out=[]
    if not q:return []
    if q.lower() in SEARCH_MAP:
        n,t=SEARCH_MAP[q.lower()].split("|"); out.append((n,t))
    if re.fullmatch(r"\d{6}",q): out.append((q,q+".KS"))
    out+=krx_search(q)+yahoo_search(q)
    if re.fullmatch(r"[A-Za-z.^]{1,10}",q): out.append((q.upper(),q.upper()))
    seen=set(); clean=[]
    for n,t in out:
        if (n,t) not in seen: seen.add((n,t)); clean.append((n,t))
    return clean[:10]

@st.cache_data(ttl=30)
def kr_price(t):
    if krx_stock is None:return None
    try:
        code=t.replace(".KS","").replace(".KQ","")
        df=krx_stock.get_market_ohlcv_by_date((date.today()-timedelta(days=15)).strftime("%Y%m%d"),date.today().strftime("%Y%m%d"),code)
        if df is None or df.empty:return None
        c=df["종가"].dropna(); last=float(c.iloc[-1]); prev=float(c.iloc[-2]) if len(c)>1 else last
        h=yf.Ticker(t).history(period="6mo",interval="1d")
        if h is None or h.empty: h=pd.DataFrame({"Close":c})
        close=h["Close"].dropna()
        return {"hist":h,"last":last,"last_krw":last,"chg":(last-prev)/prev*100 if prev else 0,"ma5":float(close.tail(5).mean()),"ma20":float(close.tail(20).mean()),"ma60":float(close.tail(60).mean()),"hi20":float(close.tail(20).max()),"lo20":float(close.tail(20).min()),"vol":0,"avgv":0,"source":"KRX"}
    except Exception:return None
@st.cache_data(ttl=60)
def price(t):
    if is_kr(t):
        kp=kr_price(t)
        if kp:return kp
    try:
        h=yf.Ticker(t).history(period="6mo",interval="1d")
        if h is None or h.empty:return None
        c=h["Close"].dropna(); last=float(c.iloc[-1]); prev=float(c.iloc[-2]) if len(c)>1 else last
        return {"hist":h,"last":last,"last_krw":to_krw(last,t),"chg":(last-prev)/prev*100 if prev else 0,"ma5":float(c.tail(5).mean()),"ma20":float(c.tail(20).mean()),"ma60":float(c.tail(60).mean()),"hi20":float(c.tail(20).max()),"lo20":float(c.tail(20).min()),"vol":float(h["Volume"].dropna().iloc[-1]) if "Volume" in h and len(h["Volume"].dropna()) else 0,"avgv":float(h["Volume"].dropna().tail(20).mean()) if "Volume" in h and len(h["Volume"].dropna()) else 0,"source":"Yahoo"}
    except Exception:return None

@st.cache_data(ttl=180)
def get_news(q,limit=12):
    try:
        r=requests.get("https://news.google.com/rss/search",params={"q":q,"hl":"ko","gl":"KR","ceid":"KR:ko"},timeout=8)
        items=re.findall(r"<item>(.*?)</item>",r.text,flags=re.S); out=[]
        for it in items[:limit]:
            title=re.search(r"<title><!\[CDATA\[(.*?)\]\]></title>|<title>(.*?)</title>",it,flags=re.S); link=re.search(r"<link>(.*?)</link>",it,flags=re.S)
            tt=(title.group(1) or title.group(2) or "").strip() if title else ""; tt=re.sub("<.*?>","",tt)
            out.append({"title":tt,"link":link.group(1).strip() if link else ""})
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
    s=max(0,min(100,int(s))); lab="호재" if s>=65 else "악재" if s<=40 else "중립"
    return s,lab,("긍정 "+",".join(g[:2]) if g else "")+(" / 부정 "+",".join(b[:2]) if b else "")+(" / 핵심 "+",".join(hot[:2]) if hot else "") or "강한 키워드 없음"
def ai_signal(news_score,info):
    s=news_score; good=[]; bad=[]
    if info:
        chg=info["chg"]
        if chg>4:s+=12;good.append("오늘 매수세가 꽤 강함")
        elif chg>1:s+=6;good.append("최근 흐름이 위쪽으로 기울어짐")
        elif chg<-4:s-=12;bad.append("오늘 매도 압력이 강함")
        elif chg<-1:s-=6;bad.append("최근 흐름이 약해짐")
        if info["ma5"]>info["ma20"]>info["ma60"]:s+=12;good.append("단기·중기 흐름이 모두 좋아짐")
        elif info["ma5"]>info["ma20"]:s+=7;good.append("짧은 기간 흐름이 회복 중")
        elif info["ma5"]<info["ma20"]<info["ma60"]:s-=12;bad.append("전체 흐름이 아직 무거움")
        elif info["ma5"]<info["ma20"]:s-=7;bad.append("짧은 기간 힘이 약함")
        if info["last"]>=info["hi20"]*.98:s+=5;good.append("최근 고점 근처")
        if info["last"]<=info["lo20"]*1.02:s-=5;bad.append("최근 저점 근처라 불안정")
    s=max(0,min(100,int(s)))
    if s>=75:sig="강한 상승"
    elif s>=60:sig="상승 우세"
    elif s<=30:sig="강한 하락"
    elif s<=42:sig="하락 우세"
    else:sig="관망"
    return sig,s,100-s,good,bad
def period_text():
    return f"{(date.today()+timedelta(days=1)).strftime('%m/%d')} ~ {(date.today()+timedelta(days=4)).strftime('%m/%d')} 기준"
def market_calendar():
    today=date.today()
    items=[[today+timedelta(days=1),"미국 CPI / 물가 일정","시장 전체 흔들릴 수 있음","경제"],[today+timedelta(days=3),"FOMC·금리 발언","반도체·성장주 영향 큼","경제"],[today+timedelta(days=5),"빅테크 실적 시즌","엔비디아·AMD·테슬라 영향 가능","실적"],[today+timedelta(days=10),"ETF 리밸런싱/편입","레버리지·인버스 ETF 변동 가능","ETF"]]
    for i,n in enumerate(["엔비디아","테슬라","AMD","애플","마이크로소프트","구글","아마존","메타","삼성전자","SK하이닉스"]):
        items.append([today+timedelta(days=2+i*2),f"{n} 실적/가이던스 확인","정확한 날짜는 공시로 재확인 필요","실적"])
    return sorted(items,key=lambda x:x[0])
def load_log():
    if os.path.exists(LOG_FILE):
        try:return pd.read_csv(LOG_FILE)
        except Exception:pass
    return pd.DataFrame(columns=["date","period","name","ticker","signal","up_pct","down_pct","price_krw","next_result_pct","correct"])
def save_log(rows):
    df=load_log(); today=date.today().isoformat()
    if not df.empty: df=df[df["date"]!=today]
    pd.concat([df,pd.DataFrame(rows)],ignore_index=True).to_csv(LOG_FILE,index=False,encoding="utf-8-sig")

stocks=rjson(STOCKS_FILE,DEFAULT_STOCKS.copy()); portfolio=rjson(PORTFOLIO_FILE,{}); memos=rjson(MEMO_FILE,{"global":"","stock":{}})
with st.sidebar:
    st.header("⚙️ 설정")
    auto=st.toggle("자동 새로고침",True); sec=st.slider("간격(초)",60,600,180,30)
    if auto: st.markdown(f"<meta http-equiv='refresh' content='{sec}'>",unsafe_allow_html=True)
    st.divider(); st.subheader("⭐ 종목 찾기")
    q=st.text_input("종목 이름만 입력",placeholder="레버리지 / 인버스 / SOXL / 샌디스크 / 대우건설")
    cs=candidates(q) if q else []; selected=None
    if cs:
        labels=[f"{n} · {t}" for n,t in cs]; pick=st.selectbox("검색 결과",labels); selected=cs[labels.index(pick)]
    elif q: st.warning("다른 이름이나 종목코드도 가능")
    if st.button("관심종목 추가",use_container_width=True):
        if selected: stocks[selected[0]]=selected[1]; wjson(STOCKS_FILE,stocks); st.success("저장됨")
    rm=st.selectbox("삭제",["선택 안 함"]+list(stocks.keys()))
    if st.button("삭제",use_container_width=True) and rm!="선택 안 함":
        stocks.pop(rm,None); portfolio.pop(rm,None); memos.get("stock",{}).pop(rm,None); wjson(STOCKS_FILE,stocks); wjson(PORTFOLIO_FILE,portfolio); wjson(MEMO_FILE,memos)

st.markdown("<div class='hero'><h1>📈 AI 주식 레이더</h1><div>가격 정확도 개선 · 원화 기준 · ETF/레버리지/인버스 검색 · 강화된 AI 분석</div></div>",unsafe_allow_html=True)
st.caption(f"업데이트: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} · 예측기간: {period_text()} · 환율: 1달러 ≈ {fx_rate():,.0f}원")

tabs=st.tabs(["🏠 메인","🔎 종목 상세","🚨 긴급 속보","📅 전체 캘린더","📊 종목 카드","📰 뉴스","📈 차트","🎯 기록"])
cache={}; rows=[]; radar=[]; all_news=[]
for n,t in stocks.items():
    info=price(t); cache[t]=info; ns=get_news(f"{n} {t} 주식 OR stock",12)
    scored=[(*score_news(x["title"]),x) for x in ns]; avg=int(sum(x[0] for x in scored)/len(scored)) if scored else 50
    sig,up,down,good,bad=ai_signal(avg,info)
    news_good=[x[3]["title"] for x in scored if x[1]=="호재"][:2]; news_bad=[x[3]["title"] for x in scored if x[1]=="악재"][:2]
    radar.append({"종목":n,"티커":t,"신호":sig,"상승확률":up,"하락확률":down,"현재가원":round(info["last_krw"]) if info else 0,"등락률":round(info["chg"],2) if info else 0,"좋은점":" · ".join(good+news_good),"주의점":" · ".join(bad+news_bad),"기간":period_text(),"출처":info.get("source","") if info else ""})
    rows.append({"date":date.today().isoformat(),"period":period_text(),"name":n,"ticker":t,"signal":sig,"up_pct":up,"down_pct":down,"price_krw":round(info["last_krw"]) if info else ""})
    for x in scored: all_news.append((n,)+x)
df=pd.DataFrame(radar).sort_values("상승확률",ascending=False) if radar else pd.DataFrame()

with tabs[0]:
    st.subheader("🏠 메인 메뉴")
    gm=st.text_area("📝 전체 투자 메모",value=memos.get("global",""),height=80)
    if st.button("전체 메모 저장",use_container_width=True): memos["global"]=gm; wjson(MEMO_FILE,memos); st.success("저장됨")
    total_v=total_c=0
    for _,r in df.iterrows():
        n,t=r["종목"],r["티커"]; info=cache.get(t); hold=portfolio.get(n,{"qty":0,"avg":0})
        qty=float(hold.get("qty",0) or 0); avg=float(hold.get("avg",0) or 0); now=float(r["현재가원"]); val=qty*now; cost=qty*avg; pnl=val-cost; pct=(pnl/cost*100) if cost else 0
        total_v+=val; total_c+=cost; cls="green" if pnl>=0 and cost else "red" if cost else "blue"
        sub=f"({info['last']:,.2f} USD)" if info and is_us(t) else f"출처 {r['출처']}"
        st.markdown(f"<div class='card {cls}'><span class='badge'>{n}</span><span class='badge'>{t}</span><div class='big'>{money(now)}</div><div class='tiny'>{sub}</div><div>보유 {qty:g}주 · 평단 {money(avg)}</div><div>평가금액 {money(val)} / 손익 {pnl:+,.0f}원 ({pct:+.2f}%)</div><div class='tiny'>AI: {r['신호']} · 상승 {r['상승확률']}%<br>좋은 점: {r['좋은점'] or '뚜렷한 호재 부족'}<br>주의 점: {r['주의점'] or '뚜렷한 악재 부족'}</div></div>",unsafe_allow_html=True)
        c1,c2,c3=st.columns([1,1,2])
        nq=c1.number_input(f"{n} 보유 주식 수",min_value=0.0,value=qty,step=0.0001,format="%.4f",key=f"q{n}")
        na=c2.number_input(f"{n} 평단 가격(원화)",min_value=0.0,value=avg,step=1.0,format="%.0f",key=f"a{n}")
        sm=c3.text_input(f"{n} 메모",value=memos.get("stock",{}).get(n,""),key=f"m{n}")
        if st.button(f"{n} 저장",key=f"s{n}",use_container_width=True):
            portfolio[n]={"qty":nq,"avg":na}; memos.setdefault("stock",{})[n]=sm; wjson(PORTFOLIO_FILE,portfolio); wjson(MEMO_FILE,memos); st.success("저장됨")
    pnl=total_v-total_c; pct=(pnl/total_c*100) if total_c else 0
    st.markdown(f"<div class='card orange'><b>💰 전체 보유 평가</b><br>총 평가금액 {money(total_v)}<br>총 손익 {pnl:+,.0f}원 ({pct:+.2f}%)</div>",unsafe_allow_html=True)
with tabs[1]:
    pick=st.selectbox("자세히 볼 종목",list(stocks.keys())); t=stocks[pick]; info=cache.get(t); r=df[df["종목"]==pick].iloc[0]
    st.markdown(f"<div class='card blue'><div class='big'>{pick}</div><div>현재가 {money(r['현재가원'])}</div><div>{r['신호']} · 상승 {r['상승확률']}% / 하락 {r['하락확률']}%</div><div class='tiny'>좋은 점: {r['좋은점'] or '뚜렷한 호재 부족'}<br>주의 점: {r['주의점'] or '뚜렷한 악재 부족'}<br>메모: {memos.get('stock',{}).get(pick,'없음')}</div></div>",unsafe_allow_html=True)
    if info:
        ch=info["hist"][["Close"]].copy(); ch["짧은 흐름"]=ch["Close"].rolling(5).mean(); ch["중간 흐름"]=ch["Close"].rolling(20).mean(); st.line_chart(ch)
with tabs[2]:
    hot=[x for x in all_news if x[1]>=75 or x[1]<=30]
    if hot:
        for stock,sc,lab,reason,x in sorted(hot,key=lambda z:abs(z[1]-50),reverse=True)[:10]:
            st.markdown(f"<div class='card {'green' if lab=='호재' else 'red'}'><span class='badge'>🚨 긴급</span><span class='badge'>{stock}</span><b>{lab} {sc}점</b><br><a href='{x['link']}' target='_blank'>{x['title']}</a><div class='tiny'>{reason}</div></div>",unsafe_allow_html=True)
    else: st.info("지금은 강한 속보 신호가 없어.")
with tabs[3]:
    for d,title,memo,typ in market_calendar():
        st.markdown(f"<div class='card blue'><span class='badge'>{typ}</span><span class='badge'>{d.strftime('%m/%d')}</span><b>{title}</b><br><span class='tiny'>{memo}</span></div>",unsafe_allow_html=True)
with tabs[4]:
    for _,r in df.iterrows():
        st.markdown(f"<div class='rankrow {'green' if r['상승확률']>=60 else 'red' if r['하락확률']>=60 else 'orange'}'><b>{r['종목']}</b> <span class='badge'>{r['신호']}</span><br>현재가 {money(r['현재가원'])} · 상승 {r['상승확률']}% / 하락 {r['하락확률']}%<div class='barbg'><div class='barg' style='width:{r['상승확률']}%'></div></div><div class='tiny'>좋은 점: {r['좋은점'] or '없음'}<br>주의 점: {r['주의점'] or '없음'}</div></div>",unsafe_allow_html=True)
with tabs[5]:
    for stock,sc,lab,reason,x in sorted(all_news,key=lambda z:z[1],reverse=True):
        st.markdown(f"<div class='news'>{'🟢' if lab=='호재' else '🔴' if lab=='악재' else '⚪'} <b>{stock} · {lab} {sc}점</b><br><a href='{x['link']}' target='_blank'>{x['title']}</a><br><span class='tiny'>{reason}</span></div>",unsafe_allow_html=True)
with tabs[6]:
    pick=st.selectbox("차트 종목",list(stocks.keys()),key="chartpick"); info=cache.get(stocks[pick])
    if info:
        ch=info["hist"][["Close"]].copy(); ch["짧은 흐름"]=ch["Close"].rolling(5).mean(); ch["중간 흐름"]=ch["Close"].rolling(20).mean(); ch["긴 흐름"]=ch["Close"].rolling(60).mean(); st.line_chart(ch)
with tabs[7]:
    if st.button("오늘 예측 저장",use_container_width=True): save_log(rows); st.success("저장 완료")
    log=load_log()
    if log.empty: st.info("아직 기록 없음.")
    else: st.dataframe(log,use_container_width=True); st.download_button("CSV 다운로드",log.to_csv(index=False,encoding="utf-8-sig"),"prediction_log.csv")
st.warning("투자 보조용 도구야. 실제 매수/매도는 반드시 본인이 판단해야 함.")
