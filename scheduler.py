"""
scheduler.py — Monitor de Licitações
Ciclos automatizados: scraping / alertas / digest / prospecção
Deploy: Railway (python scheduler.py)
"""
import asyncio, logging, os
from datetime import datetime, timezone, timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from supabase import create_client

logging.basicConfig(level=os.getenv("LOG_LEVEL","INFO"),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("scheduler")

SUPABASE_URL = os.getenv("SUPABASE_URL","")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY","")
SEGMENTS = ["ti","saude"]

def sb(): return create_client(SUPABASE_URL, SUPABASE_KEY)

async def run_scraping_cycle():
    logger.info("▶ Scraping iniciado")
    from scrapers.scraper_pncp import fetch_pncp, fetch_bec
    from core.scorer import score_licitacao
    client = sb()
    tenants = (client.table("tenants").select("id,name,email").eq("is_active",True).execute()).data or []
    configs = {c["tenant_id"]: c for c in (client.table("tenant_configs").select("*").execute()).data or []}
    if not tenants: return
    all_lics = []
    async for l in fetch_pncp(SEGMENTS, days_back=1): all_lics.append(l)
    async for l in fetch_bec(SEGMENTS, days_back=1):  all_lics.append(l)
    logger.info(f"Coletadas {len(all_lics)} licitações")
    if all_lics:
        rows = [{"source":l.source,"external_id":l.external_id,"portal_url":l.portal_url,"titulo":l.titulo,"descricao":l.descricao,"Orgao":l.orgao,"uf":l.uf,"municipio":l.municipio,"modalidade":l.modalidade,"valor_estimado":l.valor_estimado,"data_abertura":str(l.data_abertura) if l.data_abertura else None,"data_publicacao":str(l.data_publicacao) if l.data_publicacao else None,"status":l.status,"raw_json":l.raw_json} for l in all_lics]
        client.table("licitacoes").upsert(rows, on_conflict="source,external_id").execute()
    logger.info("✓ Scraping concluído")

async def run_daily_digest():
    logger.info("▶ Digest diário")
    from notifiers.notifier_email import send_daily_digest
    client = sb()
    tenants = (client.table("tenants").select("id,name,email").eq("is_active",True).execute()).data or []
    today = datetime.now(timezone.utc).date().isoformat()
    for t in tenants:
        matches = (client.table("matches").select("*,licitacoes(*)").eq("tenant_id",t["id"]).gte("created_at",today).is_("notified_at","null").order("score",desc=True).limit(20).execute()).data or []
        lics = []
        for m in matches:
            l = m.get("licitacoes",{})
            if l: l["score"]=m.get("score",0); lics.append(l)
        if lics:
            await send_daily_digest(t["email"],t["name"],lics,t["name"],datetime.now().strftime("%d/%m"))
    logger.info("✓ Digest concluído")

async def main():
    scheduler = AsyncIOScheduler(timezone="America/Sao_Paulo")
    scheduler.add_job(run_scraping_cycle, "interval", hours=6, next_run_time=datetime.now())
    scheduler.add_job(run_daily_digest, CronTrigger(hour=8, minute=0))
    scheduler.start()
    logger.info("✅ Monitor de Licitações rodando. Ctrl+C para parar.")
    try:
        while True: await asyncio.sleep(60)
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()

if __name__ == "__main__":
    asyncio.run(main())
