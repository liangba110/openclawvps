#!/usr/bin/env python3
"""从平台 API 拉真实数据，过滤违规词，生成合规英文展示站 data.js（数据快照模式）。

用法：
  1. 先拉数据（服务器上 API 在 127.0.0.1:5002 等，或公网反代地址）：
     curl -s 'http://127.0.0.1:5002/api/game/list'        -o /tmp/games.json
     curl -s 'http://127.0.0.1:5002/api/companion/list'   -o /tmp/companions.json
  2. python3 generate_mate_site.py > /var/www/xx/js/data.js

黑名单 = 游戏残留 + 服务嫌疑词 + 测试/身份不当词。tags/rank_title 一律不展示（游戏残留高发区）。
"""
import json

games = json.load(open('/tmp/games.json'))['data']
comps = json.load(open('/tmp/companions.json'))['data']['list']

# 分类中文名 -> 英文（按需扩充）
cat_en = {
 8:'History & Culture', 9:'Travel Tips', 10:'Food Guide', 11:'Outdoor Hiking', 12:'Travel Photography',
 13:'Self-Driving', 14:'Trip Planning', 23:'Translation Help', 24:'Car Rental', 25:'Outdoor Shooting',
 26:'Camping', 27:'Sea Adventure', 28:'Traditional Culture', 29:'Cycling Companion', 30:'Ski Practice',
 31:'Hiking Leader', 32:'Foodie Guide', 33:'Billiards', 34:'Badminton', 35:'Vocal Music',
 36:'Table Tennis', 37:'Instrument Coaching', 38:'Painting', 39:'Dance Coaching', 40:'Fitness Coaching',
}
# 城市中文名 -> 英文（按需扩充）
city_en = {'北京':'Beijing','北京市':'Beijing','上海':'Shanghai','上海市':'Shanghai','杭州':'Hangzhou',
 '杭州市':'Hangzhou','深圳':'Shenzhen','深圳市':'Shenzhen','西安':'Xi\'an','西安市':'Xi\'an',
 '青岛':'Qingdao','青岛市':'Qingdao','成都':'Chengdu','成都市':'Chengdu','重庆':'Chongqing','重庆市':'Chongqing',
 '武汉':'Wuhan','武汉市':'Wuhan','南京':'Nanjing','南京市':'Nanjing','广州':'Guangzhou','广州市':'Guangzhou',
 '长沙':'Changsha','长沙市':'Changsha','丽江':'Lijiang','丽江市':'Lijiang','大理':'Dali','大理市':'Dali',
 '三亚':'Sanya','三亚市':'Sanya','厦门':'Xiamen','厦门市':'Xiamen','':'Unknown'}

# 昵称过滤：游戏残留 / 擦边 / 服务嫌疑 / 测试数据
BLOCK = ['游戏','电竞','巅峰','大佬','小萌','奶音','御姐','管理员','测试','字符串','甜心','元气',
         '向导','讲解','领队','教练','陪骑','陪练']

cats = [{"id": g["id"], "name_en": cat_en.get(g["id"], g["name"]), "icon": g["icon"]} for g in games]

mates = []
for m in comps:
    if any(w in m["nickname"] for w in BLOCK):
        continue
    mates.append({
        "id": m["id"], "nickname": m["nickname"],
        "city": city_en.get(m["city"], m["city"]),
        "cat": cat_en.get(m["game_id"], m["game_name"]),
        "icon": m["game_icon"] or "🧳",
        "score": m["score"], "good_rate": m["good_rate"],
        "orders": m["order_count"], "price": int(m["price_1h"]),
        "avatar": m["avatar"] or "",
    })

js = "/* Tongtu Travel Mate - real platform data (filtered) */\n"
js += "var CATS=" + json.dumps(cats, ensure_ascii=False) + ";\n"
js += "var MATES=" + json.dumps(mates, ensure_ascii=False) + ";\n"
js += "var SITE={name:'Tongtu Travel Mate',slogan:'Find Your Travel Mate',ver:'v2.0.0'};\n"
print(js)
print("// 分类:", len(cats), " 旅伴:", len(mates), file=__import__('sys').stderr)
