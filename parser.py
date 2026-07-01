import urllib.request
import json
import random
import time

# Используем проверенную базу
json_url = "https://raw.githubusercontent.com/tiagorrg/vless-checker/main/docs/keys.json"
final_list = []

try:
    req = urllib.request.Request(json_url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req, timeout=15) as response:
        data = json.loads(response.read().decode('utf-8'))
        
        for region_name, region_data in data.items():
            if isinstance(region_data, dict) and "top10" in region_data:
                for item in region_data["top10"]:
                    # Берем только VLESS с пингом < 300мс
                    if isinstance(item, dict) and "key" in item and item.get("latency_ms", 999) < 300:
                        clean_key = item["key"].strip()
                        if clean_key.startswith("vless://"):
                            final_list.append(clean_key)
except:
    pass

# Очистка и перемешивание
final_list = list(set(final_list))
random.shuffle(final_list)
final_list = final_list[:5] # Строгий лимит 5 штук

# Метка времени для Hiddify
timestamp = f"# Updated at {time.strftime('%Y-%m-%d %H:%M:%S')}"
final_list.insert(0, timestamp)

with open("sub.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(final_list))
