"""
prospector/prospector.py
Prospecção automática de leads — 100% sem intervenção manual.
Fluxo:
  1. enrich_leads() -> busca empresas TI/Saúde via API CNPJ.ws
  2. run_sequences() -> dispara sequência de 3 e-mails espaçados
  3. Cron: roda 1x/dia às 09h via scheduler.py
"""
import os
import asyncio
import logging
import httpx
from datetime import datetime, timedelta, timezone
from typing import Optional

logger = logging.getLogger(__name__)

SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY", "")
FROM_EMAIL = os.getenv("FPOM_EMAIL", "contato@SEUDOMINIO.com.br")
FROM_NAME = os.getenv("FROM_NAME", "Marcio — Monitor de Licitações")
PRODUCT_URL = os.getenv("PRODUCT_URL", "https://SEUDOMINIO.com.br")
TRIAL_URL = os.getenv("TRIAL_URL", "https://SEUDOMINIO.com.br/trial")

CNAE_SEGMENTS = {
    "ti": ["6201501","6201502","6202300","6203100","6204000","6209100","6311900","6319400"],
    "saude": ["4644301","4644302","4645101","4645102","2121101","2121102","8610101","8640201"],
}

SEQUENCES = {
    "ti": [
        {"subject": "Sua empresa participa de licitações de TI?", "delay_days": 0},
        {"subject": "Como empresas de TI ganham mais licitações", "delay_days": 4},
        {"subject": "7 dias grátis — ver se funciona para você", "delay_days": 8},
    ],
    "saude": [
        {"subject": "Distribuidora/farmácia participa de pregões hospitalares?", "delay_days": 0},
        {"subject": "Como distribuidoras de saúde antecipam oportunidades", "delay_days": 4},
        {"subject": "Teste grátis por 7 dias — sem cartão de crédito", "delay_days": 8},
    ],
}

STATUS_SEQUENCE = ["new", "email_1_sent", "email_2_sent", "email_3_sent"]


async def enrich_leads(segment: str, uf: str = "SP", max_leads: int = 50) -> list[dict]:
    cnaes = CNAE_SEGMENTS.get(segment, [])
    leads = []
    async with httpx.AsyncClient(timeout=20, headers={"User-Agent": "MonitorLicitacoes/1.0"}) as client:
        for cnae in cnaes[:3]:
            try:
                resp = await client.get(f"https://brasilapi.com.br/api/cnpj/v1/empresa", params={"cnae": cnae, "uf": uf, "pagina": 1})
                if resp.status_code != 200: continue
                companies = resp.json() if isinstance(resp.json(), list) else []
                for c in companies[:max_leads]:
                    email = _extract_email(c)
                    if not email: continue
                    leads.append({"company_name": c.get("razao_social", c.get("nome_fantasia", "")), "contact_email": email, "contact_name": _extract_contact_name(c), "segment": segment, "source": "cnpj_api", "enriched_data": {"cnpj": c.get("cnpj"), "municipio": c.get("municipio"), "uf": c.get("uf"), "porte": c.get("porte"), "cnae_principal": cnae}})
                await asyncio.sleep(0.5)
            except Exception as e:
                logger.warning(f"enrich_leads [{cnae}]: {e}")
    return leads[:max_leads]


def _extract_email(company: dict) -> Optional[str]:
    for field in ["email", "correio_eletronico"]:
        v = company.get(field, "")
        if v and "@" in v and "." in v.split("@")[-1]: return v.lower().strip()
    return None


def _extract_contact_name(company: dict) -> str:
    socios = company.get("socios", company.get("qsa", []))
    if socios: return socios[0].get("nome_socio", socios[0].get("nome", "")).title()
    return ""


async def run_sequences(supabase_client) -> int:
    now = datetime.now(timezone.utc)
    sent_count = 0
    resp = supabase_client.table("leads").select("*").lte("next_email_at", now.isoformat()).in_("status", ["new", "email_1_sent", "email_2_sent"]).limit(100).execute()
    leads = resp.data or []
    for lead in leads:
        seg = lead.get("segment", "ti")
        seq = SEQUENCES.get(seg, SEQUENCES["ti"])
        current_status = lead.get("status", "new")
        step_idx = STATUS_SEQUENCE.index(current_status) if current_status in STATUS_SEQUENCE else 0
        if step_idx >= len(seq): continue
        step = seq[step_idx]
        html = f"<h1>{step['subject']}</h1><p style='font-family:sans-serif'>Olá {  lead.get('contact_name') or lead.get('company_name','')}, olvivokeon licitações? {PRODUCT_URL}</p>"
        ok = await _send_prospecting_email(to_email=lead["contact_email"], to_name=lead.get("contact_name") or lead.get("company_name", ""), subject=step["subject"], html=html, lead_id=lead["id"])
        if ok:
            next_step_idx = step_idx + 1
            next_status = STATUS_SEQUENCE[next_step_idx] if next_step_idx < len(STATUS_SEQUENCE) else "email_3_sent"
            next_delay = seq[next_step_idx]["delay_days"] if next_step_idx < len(seq) else 999
            next_email_at = (now + timedelta(days=next_delay)).isoformat() if next_step_idx < len(seq) else None
            supabase_client.table("leads").update({"status": next_status, "last_email_at": now.isoformat(), "next_email_at": next_email_at}).eq("id", lead["id"]).execute()
            sent_count += 1
            await asyncio.sleep(0.3)
    return sent_count


async def _send_prospecting_email(to_email: str, to_name: str, subject: str, html: str, lead_id: str) -> bool:
    if not SENDGRID_API_KEY: return False
    payload = {"personalizations": [{"to": [{"email": to_email, "name": to_name}]}], "from": {"email": FROM_EMAIL, "name": FROM_NAME}, "subject": subject, "content": [{"type": "text/html", "value": html}], "custom_args": {"lead_id": lead_id}}
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post("https://api.sendgrid.com/v3/mail/send", json=payload, headers={"Authorization": f"Bearer {SENDGRID_API_KEY}"})
            return resp.status_code in (200, 202)
    except Exception as e:
        logger.error(f"Prospecting send error: {e}")
        return False
