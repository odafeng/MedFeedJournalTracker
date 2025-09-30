"""驗證期刊清單"""
import json

with open('config/journals.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

sds = [j for j in data['journals'] if j['category'] == 'SDS']
crc = [j for j in data['journals'] if j['category'] == 'CRC']

print("=" * 60)
print("期刊清單統計")
print("=" * 60)
print(f"\n✅ SDS 期刊: {len(sds)} 個")
for j in sds:
    print(f"   - {j['name']}")

print(f"\n✅ CRC 期刊: {len(crc)} 個")
for j in crc:
    print(f"   - {j['name']}")

print(f"\n📊 總計: {len(data['journals'])} 個期刊")
print("=" * 60)
