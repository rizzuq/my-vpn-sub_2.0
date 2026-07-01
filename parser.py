import asyncio
import os
import re
import urllib.parse
import aiohttp
import logging
from dataclasses import dataclass
from typing import List, Optional
from datetime import datetime

logging.basicConfig(level=logging.INFO, format="%(asctime)s - [%(levelname)s] - %(message)s")
logger = logging.getLogger("VPN_Parser_Best")

LOCAL_FILE = "working_configs.txt"
SUB_FILE = "sub.txt"
TIMEOUT = 3.0 

GITHUB_RAW_URLS = [
    "https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/main/BLACK_VLESS_RUS.txt",
    "https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/main/BLACK_VLESS_RUS_mobile.txt",
    "https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/main/BLACK_SS%2BAll_RUS.txt",
    "https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/main/Vless-Reality-White-Lists-Rus-Mobile.txt",
    "https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/main/Vless-Reality-White-Lists-Rus-Mobile-2.txt",
    "https://raw.githubusercontent.com/WHITE-SNI-RU-all.txt"
]

@dataclass
class VPNKey:
    raw_url: str
    protocol: str
    host: str
    port: int
    uuid: str
    is_reality: bool
    is_de: bool

    def __hash__(self) -> int: return hash((self.host, self.port, self.uuid))
    def __eq__(self, other: object) -> bool:
        if not isinstance(other, VPNKey): return NotImplemented
        return (self.host, self.port, self.uuid) == (other.host, other.port, other.uuid)

def parse_to_vpn_key(config_str: str) -> Optional[VPNKey]:
    try:
        line = config_str.strip()
        if not line or line.startswith('#') or line.startswith('//'): return None
        remark = ""
        if '#' in line: line, remark = line.split('#', 1)
        parsed = urllib.parse.urlparse(line)
        if parsed.scheme not in ('vless', 'vmess', 'trojan', 'ss', 'hysteria2'): return None
        if any(x in line.lower() for x in ["127.0.0.1", "localhost", "anycast"]): return None
        netloc = parsed.netloc
        endpoint = netloc.rsplit('@', 1)[-1] if '@' in netloc else netloc
        if endpoint.startswith('['):
            close_bracket = endpoint.rfind(']')
            host = endpoint[1:close_bracket]
            port = int(endpoint[close_bracket+1:].lstrip(':')) if ':' in endpoint[close_bracket+1:] else 443
        else:
            host, port = endpoint.rsplit(':', 1) if ':' in endpoint else (endpoint, 443)
            port = int(port)
        uuid = netloc.split('@')[0] if '@' in netloc else ""
        is_reality = 'security=reality' in line.lower() or 'reality' in remark.lower()
        is_de = any(kw in remark.lower() or kw in host.lower() for kw in ['de', 'germany', 'германия', 'frankfurt'])
        return VPNKey(raw_url=f"{line}#{remark}" if remark else line, protocol=parsed.scheme, host=host, port=port, uuid=uuid, is_reality=is_reality, is_de=is_de)
    except Exception: return None

async def check_server(key: VPNKey) -> Optional[VPNKey]:
    try:
        reader, writer = await asyncio.wait_for(asyncio.open_connection(key.host, key.port), timeout=TIMEOUT)
        writer.close()
        await writer.wait_closed()
        return key
    except Exception: return None

async def fetch_file(session: aiohttp.ClientSession, url: str) -> List[str]:
    try:
        async with session.get(url, timeout=10.0) as response:
            return (await response.text()).splitlines() if response.status == 200 else []
    except Exception: return []

def load_lines(filename: str) -> List[str]:
    if not os.path.exists(filename): return []
    with open(filename, "r", encoding="utf-8") as f: return [line.strip() for line in f if line.strip()]

def save_lines(filename: str, data: List[str]):
    with open(filename, "w", encoding="utf-8") as f:
        for item in data: f.write(item + "\n")

async def main():
    logger.info("Этап 1: Валидация старой базы...")
    alive_old_pool = [k for k in await asyncio.gather(*[check_server(k) for k in [parse_to_vpn_key(cfg) for cfg in load_lines(LOCAL_FILE)] if k is not None]) if k is not None]
    
    logger.info("Этап 2: Парсинг Игоряка...")
    all_parsed_lines = []
    async with aiohttp.ClientSession() as session:
        for lines in await asyncio.gather(*[fetch_file(session, url) for url in GITHUB_RAW_URLS]): all_parsed_lines.extend(lines)
        
    logger.info("Этап 3: Дедупликация...")
    new_candidates_map = {}
    for line in all_parsed_lines:
        v_key = parse_to_vpn_key(line)
        if v_key: new_candidates_map[v_key] = v_key
    unique_new_candidates = [k for k in new_candidates_map.values() if (k.host, k.port) not in {(k.host, k.port) for k in alive_old_pool}]
    
    logger.info("Этап 4: Тест сокетов...")
    alive_new_pool = [k for k in await asyncio.gather(*[check_server(k) for k in unique_new_candidates]) if k is not None]
    
    logger.info("Этап 5: Сортировка и экспорт ТОП-3...")
    total_working_pool = list(set(alive_old_pool + alive_new_pool))
    if not total_working_pool: return
    
    total_working_pool.sort(key=lambda k: (k.is_reality, k.is_de, k.protocol == 'vless'), reverse=True)
    save_lines(LOCAL_FILE, [k.raw_url for k in total_working_pool])
    
    top_3_pool = total_working_pool[:3]
    sub_lines = [f"# Updated at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"]
    for k in top_3_pool: sub_lines.append(k.raw_url)
    
    save_lines(SUB_FILE, sub_lines)
    logger.info("Файл подписки sub.txt успешно обновлен!")

if __name__ == '__main__':
    asyncio.run(main())
