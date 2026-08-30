# 全国多节点延迟测速（ITDog）— 使用方法 + 数据提取

用途：新服务器上架后 / 迁移后 / 对比两机线路质量时，测全国各地区访问延迟。ITDog 提供 200+ 监测点（电信/联通/移动家庭宽带节点），免费免登录。

## 三类测速 URL

- TCP ping（最贴近实际网站访问）：`https://www.itdog.cn/tcping/域名:443` 或 `https://www.itdog.cn/tcping/IP:443`
- ICMP ping：`https://www.itdog.cn/ping/域名`
- HTTP 测速：`https://www.itdog.cn/http/域名`

URL 带参数会自动触发测试。

## ⚠️ 缓存假数据陷阱（必读）

页面首屏的汇总表格是**上一次测试的缓存**，不是本次结果。实测：给东京服务器测速，首屏显示"中国香港 2ms / 广东中山 9ms"（到东京不可能 <10ms）——这是历史缓存。

必须：
1. 点 **"单次测试"** 按钮（页面中部）
2. 等 1-2 分钟（200 节点逐批跑）
3. 再提取数据

判断真伪：香港→东京应 50-70ms；出现 <5ms 一律视为缓存假数据。

## 提取统计（browser_console 执行 JS）

```js
(() => {
  const rows = document.querySelectorAll('table tr');
  const nodes = [];
  rows.forEach(r => {
    const cells = [...r.querySelectorAll('td')].map(c => c.innerText.trim());
    if (cells.length >= 4 && cells[3] && /ms$/.test(cells[3]) && cells[0] && cells[0].includes(' ')) {
      const ms = parseFloat(cells[3]);
      if (!isNaN(ms) && ms > 0 && ms < 5000) nodes.push({name: cells[0], ms});
    }
  });
  const regions = {'华东':[], '华南':[], '华中':[], '华北':[], '西南':[], '西北':[], '东北':[], '港澳台':[]};
  const map = {'江苏':'华东','浙江':'华东','安徽':'华东','福建':'华东','江西':'华东','山东':'华东','上海':'华东',
    '广东':'华南','广西':'华南','海南':'华南','湖北':'华中','湖南':'华中','河南':'华中',
    '北京':'华北','天津':'华北','河北':'华北','山西':'华北','内蒙古':'华北',
    '四川':'西南','重庆':'西南','贵州':'西南','云南':'西南','西藏':'西南',
    '陕西':'西北','甘肃':'西北','青海':'西北','宁夏':'西北','新疆':'西北',
    '辽宁':'东北','吉林':'东北','黑龙江':'东北','香港':'港澳台','澳门':'港澳台','台湾':'港澳台'};
  nodes.forEach(n => { for (const [prov, reg] of Object.entries(map)) { if (n.name.includes(prov)) { regions[reg].push(n.ms); return; } } });
  const stat = arr => {
    if (!arr.length) return '-';
    const s = [...arr].sort((a,b)=>a-b);
    const med = s[Math.floor(s.length/2)];
    const avg = (s.reduce((a,b)=>a+b,0)/s.length).toFixed(0);
    const normal = s.filter(v => v < 500);
    const nmed = normal.length ? normal[Math.floor(normal.length/2)] : '-';
    return `n=${arr.length} 中位${med}ms 均${avg}ms 正常中位${nmed}ms 异常(>500ms)${s.length-normal.length}个`;
  };
  const ops = {'电信':[], '联通':[], '移动':[]};
  nodes.forEach(n => { for (const o of Object.keys(ops)) if (n.name.includes(o)) ops[o].push(n.ms); });
  const res = {total: nodes.length, overall: stat(nodes.map(n=>n.ms)), regions: {}, ops: {}};
  for (const [rk, arr] of Object.entries(regions)) res.regions[rk] = stat(arr);
  for (const [o, arr] of Object.entries(ops)) res.ops[o] = stat(arr);
  return JSON.stringify(res);
})()
```

节点行格式：`运营商 地区 | IP:端口 | 归属 | XXms`（第 0 格含空格、第 3 格以 ms 结尾）。

## 结果解读

- 正常：国内→日本/香港 50-100ms；国内→国内 20-50ms
- **电信 1.0-1.1s 异常节点**（湖南/河南/湖北/四川/甘肃/辽宁等省家庭节点，规律性 ~1068-1112ms）是**电信省网国际出口拥塞/绕路**，非服务器问题——同测联通/移动全程正常即可佐证
- 港澳台 4ms 但全国 230ms+ = 服务器物理位置近（如香港）但国内线路绕路（如阿里云国际线路），此时把站迁到线路更好的机器收益大
- 平均被异常值拉高时，用**中位数**汇报更真实

## 对比两台服务器

- 用同一批节点才有意义（节点池基本固定，隔 5 分钟重测即可对比）
- 输出格式：区域表格（两机并列中位数）+ 运营商分组 + 结论（哪台更适合当主站）
