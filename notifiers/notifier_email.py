"""
notifiers/notifier_email.py
Envio de alertas e resumo diário via SendGrid (free tier: 100 emails/dia).
"""
import os
import logging
import httpx
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)
SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY", "")
FROM_EMAIL = os.getenv("FPOM_EMAIL", "alertas@SEUDOMINIO.com.br")
FROM_NAME = os.getenv("FROM_NAME", "Monitor de Licitações")
REPLY_TO = os.getenv("REPLY_TO", "suporte@SEUDOMINIO.com.br")

async def send_alert(to_email: str, to_name: str, licitacoes: list[dict], tenant_name: str = "") -> bool:
    if not licitacoes: return True
    subject = f"🔔 {len(licitacoes)} nova{'s' if len(licitacoes) > 1 else ''} licitação{'ões' if len(licitacoes) > 1 else ''} para {tenant_name or 'você�}"
    html = _build_alert_html(licitacoes, tenant_name)
    return await _send(to_email, to_name, subject, html)

async def send_daily_digest(to_email: str, to_name: str, licitacoes: list[dict], tenant_name: str = "", period_label: str = "hoje") -> bool:
    if not licitacoes: return True
    subject = f"📋 Resumo de licitações de {period_label} — {len(licitacoes)} oportunidade{'s' if len(licitacoes) > 1 else ''}"
    html = _build_digest_html(licitacoes, tenant_name, period_label)
    return await _send(to_email, to_name, subject, html)

async def _send(to_email: str, to_name: str, subject: str, html: str) -> bool:
    if not SENDGRID_API_KEY:
        logger.error("SENDGRID_API_KEY não configurada")
        return False
    payload = {"personalizations": [{"to": [{"email": to_email, "name": to_name}]}], "from": {"email": FROM_EMAIL, "name": FROM_NAME}, "reply_to": {"email": REPLY_TO}, "subject": subject, "content": [{"type": "text/html", "value": html}], "tracking_settings": {"click_tracking": {"enable": True}, "open_tracking": {"enable": True}}}
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post("https://api.sendgrid.com/v3/mail/send", json=payload, headers={"Authorization": f"Bearer {SENDGRID_API_KEY}"})
            if resp.status_code not in (200, 202):
                logger.error(f"SendGrid error {resp.status_code}: {resp.text[:300]}")
                return False
            return True
    except Exception as e:
        logger.error(f"SendGrid exception: {e}")
        return False

def _build_alert_html(licitacoes: list[dict], tenant_name: str) -> str:
    cards = ""
    for lic in licitacoes[:10]:
        score = lic.get("score", 0)
        score_color = "#16a34a" if score >= 7 else "#d97706" if score >= 5 else "#6b7280"
        valor = f"R$ {lic.get('valor_estimado', 0):,.2f}" if lic.get("valor_estimado") else "Não informado"
        cards += f"<tr><td style='padding:16px;border-bottom:1px solid #f0f0f0;'><span style='display:inline-block;border-radius:12px;background:{score_color};color:#fff;padding:2px 8px;font-size:12px;font-weight:600;'>Score {score:.1f}</span><p style='margin:4px 0 4px;font-size:15px;font-weight:600;color:#111827;'>{_esc(lic.get('titulo','')[:120])}</p><p style='margin:0 0 8px;font-size:13px;color:#6b7280;'>{_esc(lic.get('orgao',''))} · {lic.get('uf','')}</p><p>💰 <strong>{valor}</strong></p><a href='{lic.get('portal_url','#')}' style='display:inline-block;background:#2563eb;color:#fff;font-size:13px;padding:8px 16px;border-radius:6px;text-decoration:none;'>Ver edital →</a></td></tr>"
    return f"<!DOCTYPE html><html><body style='font-family:sans-serif;'><h2>🔍 Novas licitações detectadas para {_esc(tenant_name)}</h2><table width='100%'>{cards}</table></body></html>"

def _build_digest_html(licitacoes: list[dict], tenant_name: str, period_label: str) -> str:
    top = sorted(licitacoes, key=lambda x: x.get("score", 0), reverse=True)[:5]
    return _build_alert_html(top, tenant_name)

def _esc(text: str) -> str:
    return str(text).replace("&","&amp;").replace("<","&lt;").replace(">","&gt;").replace('"',"&quot;")
