"""
scrapers/scraper_pncp.py  +  scrapers/scraper_bec.py (combined)
PNCP = API pública Comprasnet — sem auth, sem risco de bloqueio
BEC  = Bolsa Eletrônica de Compras SP
"""
import httpx
import asyncio
import logging
from datetime import date, timedelta
from typing import AsyncIterator, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)

PNCP_BASE = "https://pncp.gov.br/api/consulta/v1"
BEC_BASE  = "https://www.bec.sp.gov.br/BECSP/Compras/ListaCompras"

SEGMENT_KEYWORDS = {
    "ti": ["software", "sistema de informação", "tecnologia da informação", "desenvolvimento de sistema", "suporte técnico", "infraestrutura de ti", "licença de software", "erp", "cloud computing", "segurança da informação", "banco de dados", "helpdesk", "datacenter", "microsoft", "oracle", "implantação de sistema", "consultoria em ti", "manutenção de sistema"],
    "saude": ["medicamento", "material farmacêutico", "equipamento hospitalar", "material hospitalar", "insumo farmacêutico", "reagente laboratorial", "equipamento médico", "epi hospitalar", "kit diagnóstico", "vacina", "órtese prótese", "radiologia", "hemodiálise", "laboratório análises"],
}

@dataclass
class LicitacaoIn:
    source: str
    external_id: str
    portal_url: str
    titulo: str
    descricao: Optional[str]
    orgao: Optional[str]
    uf: Optional[str]
    municipio: Optional[str]
    modalidade: Optional[str]
    valor_estimado: Optional[float]
    data_abertura: Optional[str]
    data_publicacao: Optional[str]
    status: str
    raw_json: dict

async def fetch_pncp(segments: list, days_back: int = 1, max_pages: int = 5):
    dt_ini = (date.today() - timedelta(days=days_back)).strftime("%Y%m%d")
    dt_fim = date.today().strftime("%Y%m%d")
    keywords = []
    for seg in segments:
        keywords.extend(SEGMENT_KEYWORDS.get(seg, []))
    seen = set()
    async with httpx.AsyncClient(timeout=30, headers={"User-Agent": "MonitorLicitacoes/1.0"}) as client:
        for keyword in keywords:
            page = 1
            while page <= max_pages:
                try:
                    resp = await client.get(f"{PNCP_BASE}/contratacoes/publicacao", params={"dataInicial": dt_ini, "dataFinal": dt_fim, "q": keyword, "pagina": page, "tamanhoPagina": 50})
                    resp.raise_for_status()
                    data = resp.json()
                except Exception as e:
                    logger.warning(f"PNCP [{keyword} p{page}]: {e}")
                    break
                items = data.get("data", [])
                if not items: break
                for item in items:
                    lic = _parse_pncp(item)
                    if lic.external_id not in seen:
                        seen.add(lic.external_id)
                        yield lic
                if page >= data.get("totalPaginas", 1): break
                page += 1
                await asyncio.sleep(0.5)

def _parse_pncp(item: dict) -> LicitacaoIn:
    num = item.get("numeroControlePNCP", "")
    orgao = item.get("orgaoEntidade", {})
    unidade = item.get("unidadeOrgao", {})
    return LicitacaoIn(source="pncp", external_id=num, portal_url=f"https://pncp.gov.br/app/editais/{num}", titulo=item.get("objetoCompra", "")[:500], descricao=item.get("informacaoComplementar", ""), orgao=orgao.get("razaoSocial", ""), uf=unidade.get("ufSigla", ""), municipio=unidade.get("municipioNome", ""), modalidade=item.get("modalidadeNome", ""), valor_estimado=item.get("valorTotalEstimado"), data_abertura=item.get("dataAberturaProposta"), data_publicacao=item.get("dataPublicacaoPncp"), status="aberta", raw_json=item)

async def fetch_bec(segments: list, days_back: int = 1):
    keywords = []
    for seg in segments:
        keywords.extend(SEGMENT_KEYWORDS.get(seg, []))
    seen = set()
    async with httpx.AsyncClient(timeout=30, follow_redirects=True, headers={"User-Agent": "Mozilla/5.0 (compatible; MonitorLicitacoes/1.0)"}) as client:
        for keyword in keywords[:12]:
            try:
                resp = await client.get(BEC_BASE, params={"Pesquisa": keyword, "TipoConsulta": "1"})
                items = _parse_bec_html(resp.text)
                for item in items:
                    lic = _parse_bec_item(item)
                    if lic.external_id not in seen:
                        seen.add(lic.external_id)
                        yield lic
                await asyncio.sleep(1.0)
            except Exception as e:
                logger.warning(f"BEC [{keyword}]: {e}")

def _parse_bec_html(html: str) -> list:
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "html.parser")
        rows = soup.select("table tr:not(:first-child)")
        results = []
        for row in rows:
            cols = row.select("td")
            if len(cols) < 3: continue
            link_tag = cols[1].find("a", href=True)
            results.append({"id": cols[0].get_text(strip=True), "objeto": cols[1].get_text(strip=True), "orgao": cols[2].get_text(strip=True), "abertura": cols[3].get_text(strip=True) if len(cols) > 3 else None, "url": link_tag["href"] if link_tag else None})
        return results
    except Exception:
        return []

def _parse_bec_item(item: dict) -> LicitacaoIn:
    ext_id = str(item.get("id", "bec_unknown"))
    url = item.get("url") or f"https://www.bec.sp.gov.br/BECSP/Compras/DetalhesCompra?OC={ext_id}"
    if url.startswith("/"): url = "https://www.bec.sp.gov.br" + url
    return LicitacaoIn(source="bec", external_id=ext_id, portal_url=url, titulo=item.get("objeto", "")[:500], descricao=item.get("objeto", ""), orgao=item.get("orgao", ""), uf="SP", municipio="", modalidade="", valor_estimado=None, data_abertura=item.get("abertura"), data_publicacao=None, status="aberta", raw_json=item)
