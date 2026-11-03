"""One-off read-only scan for Caesar Blue Quattro Villa SALE offers across joined Telegram groups/channels."""
import asyncio, json, os, re
from datetime import datetime, timedelta, timezone
from telethon import TelegramClient
from telethon.tl.types import PeerChannel

PROJECT=re.compile(r"(?:caesar\s*blue|cesar\s*blue|цезар(?:ь)?\s*блю|сезар\s*блю)",re.I)
QUATTRO=re.compile(r"(?:quattro|quatro|кватро|кваттро)",re.I)
VILLA=re.compile(r"(?:villa|вилла|виллу|виллы)",re.I)
SALE=re.compile(r"(?:sat[ıi]l[ıi]k|sat[ıi]yorum|sat[ıi]l[ıi]yor|for\s+sale|selling|sale|продаю|продам|прода[её]тся|продажа|переуступк\w*)",re.I)
BUY_DEMAND=re.compile(r"(?:\bкуплю\b|\bищу\b.{0,100}\b(?:квартир|вилл|дом)|looking\s+to\s+buy|want\s+to\s+buy|buying|sat[ıi]n\s+al(?:mak|acağım)|\bar[ıi]yorum\b)",re.I|re.S)
RENT=re.compile(r"(?:аренда|сда[её]тся|сдам|сдаю|rent(?:al)?|for\s+rent|kiral[ıi]k|kiraya)",re.I)
PRICE=re.compile(r"(?:[£€$]\s*\d[\d\s,.]*|\d[\d\s,.]*\s*(?:gbp|eur|usd|sterlin|pounds?|фунт\w*))",re.I)
LAYOUT=re.compile(r"(?<!\d)([0-6]\s*[+＋]\s*[0-3])(?!\d)",re.I)
AREA=re.compile(r"(\d{2,4})\s*(?:m²|m2|sqm|кв\.?\s*м)",re.I)
SEA=re.compile(r"(?:sea\s*view|deniz\s+manzara|вид\s+на\s+море|море)",re.I)
FURNISHED=re.compile(r"(?:furnished|eşyal[ıi]|mobilyal[ıi]|меблирован\w*|с\s+мебелью)",re.I)
TITLE=re.compile(r"(?:title\s*deed|ko[çc]an|tapu|титул)",re.I)
TAX=re.compile(r"(?:vat|kdv|ндс|tax(?:es)?\s+paid|налоги\s+оплачены)",re.I)

def link_for(entity,msg):
    u=str(getattr(entity,"username","") or "").strip()
    if u:return f"https://t.me/{u}/{msg.id}"
    if isinstance(getattr(msg,"peer_id",None),PeerChannel):
        cid=int(getattr(entity,"id",0) or 0)
        if cid:return f"https://t.me/c/{cid}/{msg.id}"
    return ""

def classify(text):
    t=str(text or "").strip()
    if not (PROJECT.search(t) and QUATTRO.search(t) and VILLA.search(t)):
        return False
    if RENT.search(t) and not SALE.search(t):
        return False
    if BUY_DEMAND.search(t) and not SALE.search(t):
        return False
    return bool(SALE.search(t) or PRICE.search(t))

async def scan():
    client=TelegramClient(
        os.getenv("TELEGRAM_SESSION_PATH","telegram_radar_session/radar_session.session"),
        int(os.environ["TELEGRAM_API_ID"]),os.environ["TELEGRAM_API_HASH"])
    cutoff=datetime.now(timezone.utc)-timedelta(days=int(os.getenv("CBQ_SALE_DAYS","180")))
    per_group=int(os.getenv("CBQ_PER_GROUP_LIMIT","2500"))
    stats={"groups":0,"messages":0,"matches":0,"errors":0,"offers":[]}
    seen=set()
    try:
        await client.connect()
        if not await client.is_user_authorized():raise RuntimeError("Telegram session not authorized")
        async for dialog in client.iter_dialogs():
            if not (dialog.is_group or dialog.is_channel):continue
            stats["groups"]+=1
            try:
                async for msg in client.iter_messages(dialog.entity,limit=per_group):
                    if not msg.date:continue
                    dt=msg.date if msg.date.tzinfo else msg.date.replace(tzinfo=timezone.utc)
                    if dt<cutoff:break
                    stats["messages"]+=1
                    text=str(msg.message or "").strip()
                    if not classify(text):continue
                    url=link_for(dialog.entity,msg)
                    key=url or f"{dialog.id}:{msg.id}"
                    if key in seen:continue
                    seen.add(key)
                    sender=""
                    try:
                        snd=await msg.get_sender()
                        sender="@"+snd.username if getattr(snd,"username",None) else str(getattr(snd,"first_name","") or "")
                    except Exception:pass
                    lm=LAYOUT.search(text); am=AREA.search(text)
                    stats["offers"].append({
                        "date":dt.isoformat(),"group":dialog.name,"author":sender,"url":url,
                        "price_mentions":PRICE.findall(text)[:5],
                        "layout":lm.group(1) if lm else None,
                        "area_m2":int(am.group(1)) if am else None,
                        "sea_view":bool(SEA.search(text)),"furnished":bool(FURNISHED.search(text)),
                        "title_mentioned":bool(TITLE.search(text)),"tax_paid_mentioned":bool(TAX.search(text)),
                        "text":text[:2200]})
            except Exception as exc:
                stats["errors"]+=1
                print("CBQ_GROUP_ERROR",type(exc).__name__,str(exc)[:160])
    finally:
        await client.disconnect()
    stats["offers"].sort(key=lambda x:x["date"],reverse=True)
    stats["matches"]=len(stats["offers"])
    print("CAESAR_BLUE_QUATTRO_SALE_RESULTS",json.dumps(stats,ensure_ascii=False))
    return stats

if __name__=="__main__":asyncio.run(scan())
