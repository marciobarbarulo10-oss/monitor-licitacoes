# 🔍 Monitor de Licitações — SaaS B2B

Alerta automatizado de licitações públicas via e-mail.
Segmentos: **TI & Serviços** (CNAE 62–63) e **Saúde & Farmácia**.

**Stack:** Python · PostgreSQL (Supabase) · SendGrid · Railway  
**Custo inicial:** R$ 0

---

## 🚀 Setup em 30 minutos

### 1. Banco — Supabase (grátis)
1. Crie conta em supabase.com → novo projeto (região SP)
2. SQL Editor → cole `migrations/001_schema.sql` → Execute
3. Copie Project URL + service_role key

### 2. E-mail — SendGrid (100/dia grátis)
1. Conta em sendgrid.com → API Key (Mail Send)
2. Verifique o e-mail remetente

### 3. Configure e rode
```bash
cp .env.example .env   # preencha com suas chaves
pip install -r requirements.txt
python scheduler.py    # scraping roda imediatamente
```

### 4. Deploy Railway
New Project → GitHub → Start command: `python scheduler.py`

---

## 🏗️ Estrutura

```
migrations/001_schema.sql     Schema PostgreSQL multi-tenant + RLS
scrapers/scraper_pncp.py      PNCP (Comprasnet API pública) + BEC/SP
core/scorer.py                Engine scoring 0–10 por tenant
notifiers/notifier_email.py   Alertas + resumo diário (SendGrid)
prospector/prospector.py      Prospecção automática 3 e-mails frios
scheduler.py                  Orquestrador: scraping/alertas/prospecção
```

## 💰 Planos

| Plano | Preço | Canais |
|---|---|---|
| Starter | R$ 297/mês | E-mail |
| Pro | R$ 697/mês | E-mail + WhatsApp |
| Enterprise | R$ 1.997/mês | Tudo + API |

Meta: 10 clientes = R$ 5.000 MRR

## 🗺️ Roadmap

- [x] v1: Scrapers PNCP + BEC, scoring, alertas e-mail, prospecção automática
- [ ] v2: Painel web cliente, self-service config, landing page + preços
- [ ] v3: WhatsApp (Z-API), TCE-SP/RJ, pagamento integrado
