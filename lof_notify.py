"""
LOF基金溢价率监控 + 微信推送（Server酱）
用于 GitHub Actions 定时运行
测试分支功能
增加飞书推送功能
"""

import sys
import requests
import re
import time
import os
import csv
import argparse
import json
from datetime import datetime

# Windows 终端默认 GBK 编码无法输出 emoji，统一切换到 UTF-8
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def load_dotenv(path=".env"):
    """从本地 .env 文件加载环境变量（不覆盖已有环境变量，无需安装 python-dotenv）"""
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = val


# ─── 基金列表 ────────────────────────────────────────────────────────────────

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0 Safari/537.36",
    "Referer": "https://fund.eastmoney.com/",
}

# ─── 数据获取（复用 lof_tracker.py 的逻辑）────────────────────────────────────

def fetch_premium():
    """从主列表页一次性抓取所有基金的EST数据（官方EST、EST日期、官方溢价、参考EST溢价）"""
    url = "https://palmmicro.com/woody/res/lofcn.php?sort=premium"
    print("获取溢价率（主列表页）...")
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        r.encoding = "utf-8"
        html = r.text

        m = re.search(r'id="estimationtable".*?<tbody>(.*?)</tbody>', html, re.S)
        if not m:
            print("  未找到 estimationtable")
            return {}, []

        tbody = m.group(1)
        result = {}
        fund_list = []  # 新增：保存基金列表 [(full_code, code6, name), ...]

        for row_m in re.finditer(r'<tr>(.*?)</tr>', tbody, re.S):
            cells = re.findall(r'<td[^>]*>(.*?)</td>', row_m.group(1), re.S)
            if len(cells) < 6:
                continue

            code_m = re.search(r'>(S[HZ]\d{6})<', cells[0])
            if not code_m:
                continue
            full_code = code_m.group(1)
            code6 = full_code[2:]  # 提取6位代码

            # 提取基金名称（在 <td> 标签的 title 属性中）
            name_m = re.search(r'<td[^>]*title="([^"]+)"', row_m.group(1))
            name = name_m.group(1) if name_m else '未知'

            est_m = re.search(r'>([\d.]+)<', cells[1])
            est = float(est_m.group(1)) if est_m else None

            date_m = re.search(r'(\d{4}-\d{2}-\d{2})', cells[2])
            est_date = date_m.group(1) if date_m else None

            prem_m = re.search(r'>([-\d.]+)', cells[3])
            premium = float(prem_m.group(1)) if prem_m else None

            ref_premium = None
            if cells[5].strip():
                ref_m = re.search(r'>([-\d.]+)', cells[5])
                ref_premium = float(ref_m.group(1)) if ref_m else None

            result[full_code] = {
                "est": est,
                "est_date": est_date,
                "premium": premium,
                "ref_premium": ref_premium,
                "name": name,  # 保存基金名称
            }
            
            fund_list.append((full_code, code6, name))

        print(f"  完成：{len(result)} 只")
        return result, fund_list
    except Exception as e:
        print(f"  溢价获取失败: {e}")
        return {}, []

def fetch_prices(fund_list):
    print("获取实时行情...")
    codes = ",".join(
        ("sh" if f[0].startswith("SH") else "sz") + f[1] for f in fund_list
    )
    try:
        r = requests.get(
            f"https://hq.sinajs.cn/list={codes}",
            headers={**HEADERS, "Referer": "https://finance.sina.com.cn"},
            timeout=15
        )
        r.encoding = "gbk"
        result = {}
        for line in r.text.splitlines():
            m = re.match(r'var hq_str_(s[hz])(\d{6})="([^"]+)"', line)
            if not m:
                continue
            full_code = m.group(1).upper() + m.group(2)
            parts = m.group(3).split(",")
            if len(parts) < 4:
                continue
            try:
                price = float(parts[3])
                prev = float(parts[2]) if parts[2] else 0
                change = round((price - prev) / prev * 100, 2) if prev else 0
                result[full_code] = {"price": price, "change": change}
            except:
                pass
        print(f"  完成：{len(result)} 只")
        return result
    except Exception as e:
        print(f"  行情获取失败: {e}")
        return {}

def parse_money_str(s):
    s = s.replace(",", "").strip()
    m = re.match(r'([\d.]+)\s*万元?', s)
    if m: return float(m.group(1)) * 10000
    m = re.match(r'([\d.]+)\s*亿元?', s)
    if m: return float(m.group(1)) * 1e8
    m = re.match(r'([\d.]+)\s*元?', s)
    if m: return float(m.group(1))
    return None

def fetch_quota_batch(codes6_batch):
    fcodes = ",".join(codes6_batch)
    url = (
        f"https://fundmobapi.eastmoney.com/FundMNewApi/FundMNFInfo"
        f"?pageIndex=1&pageSize={len(codes6_batch)}&plat=Android"
        f"&appType=ttjj&product=EFund&Version=1&Fcodes={fcodes}"
    )
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        data = r.json()
        if not data.get("Datas"):
            return {}
        result = {}
        for item in data["Datas"]:
            code = item.get("FCODE", "")
            sgzt = str(item.get("SGZT", "0"))
            sgsxe = float(item.get("SGSXE") or 0)
            sgba = float(item.get("SGBA") or 0)
            if sgzt == "1":
                status, status_text = "closed", "暂停申购"
            elif sgzt == "3":
                status, status_text = "closed", "封闭期"
            elif sgzt == "2":
                status, status_text = "limited", "限制大额"
            elif sgsxe > 0:
                status, status_text = "limited", "限额申购"
            else:
                status, status_text = "open", "正常申购"
            result[code] = {
                "status": status, "status_text": status_text,
                "quota": sgsxe if sgsxe > 0 else None,
                "big_quota": sgba if sgba > 0 else None,
            }
        return result
    except:
        return {}

def fetch_quota_page(code6):
    try:
        r = requests.get(f"https://fund.eastmoney.com/{code6}.html", headers=HEADERS, timeout=10)
        r.encoding = "utf-8"
        html = r.text
        raw_cells = re.findall(r'class="staticCell"[^>]*>(.*?)</span>\s*(?=<span|<div|$)', html, re.S)
        cells = [re.sub(r'<[^>]+>', '', c) for c in raw_cells]
        cell_text = " ".join(c.strip() for c in cells)
        status, status_text, quota = "unknown", "未知", None
        if "暂停申购" in cell_text or "暂停大额" in cell_text:
            status, status_text = "closed", "暂停申购"
        elif "封闭期" in cell_text:
            status, status_text = "closed", "封闭期"
        elif "限大额" in cell_text or "限制大额" in cell_text:
            status, status_text = "limited", "限制大额"
        elif "开放申购" in cell_text or "正常申购" in cell_text:
            status, status_text = "open", "正常申购"
        for target in [cell_text, html]:
            for pat in [r'单日累计购买上限\s*([\d.,]+\s*[万亿]?元?)',
                        r'单笔限购[：:]\s*([\d.,]+\s*[万亿]?元?)',
                        r'每日累计限购[：:]\s*([\d.,]+\s*[万亿]?元?)']:
                m = re.search(pat, target)
                if m:
                    quota = parse_money_str(m.group(1))
                    break
            if quota:
                break
        if quota and status not in ("closed",):
            status = "limited"
            status_text = "限制大额" if "限大额" in cell_text else "限额申购"
        return {"status": status, "status_text": status_text, "quota": quota, "big_quota": None}
    except Exception as e:
        print(f"  网页抓取失败 {code6}: {e}")
        return {"status": "error", "status_text": "查询失败", "quota": None, "big_quota": None}

def fetch_quota(fund_list):
    print("获取限购状态...")
    all_codes = [f[1] for f in fund_list]
    result = {}
    for i in range(0, len(all_codes), 20):
        result.update(fetch_quota_batch(all_codes[i:i+20]))
        time.sleep(0.5)
    failed = [f[1] for f in fund_list if f[1] not in result]
    if failed:
        print(f"  App API 未返回 {len(failed)} 只，改用网页...")
        for code6 in failed:
            result[code6] = fetch_quota_page(code6)
            time.sleep(0.3)
    print(f"  完成")
    return result

def merge(premium_map, price_map, quota_map, fund_list):
    rows = []
    for full_code, code6, name in fund_list:
        p = price_map.get(full_code, {})
        e = premium_map.get(full_code, {})
        q = quota_map.get(code6, {"status": "error", "status_text": "查询失败", "quota": None, "big_quota": None})
        price = p.get("price")
        change = p.get("change")
        est = e.get("est")
        premium = e.get("premium")
        if premium is None and price and est:
            premium = round((price - est) / est * 100, 2)
        rows.append({
            "full_code": full_code, "code6": code6, "name": name,
            "price": price, "change": change, "est": est, "premium": premium,
            "est_date": e.get("est_date"), "ref_premium": e.get("ref_premium"),
            "status": q["status"], "status_text": q["status_text"],
            "quota": q["quota"], "big_quota": q["big_quota"],
        })
    rows.sort(key=lambda x: (x["premium"] or -999), reverse=True)
    return rows

# ─── 格式化 ──────────────────────────────────────────────────────────────────

def fmt_money(val):
    if not val: return "无限制"
    if val >= 1e8: return f"{val/1e8:.0f}亿"
    if val >= 1e4: return f"{val/1e4:.0f}万"
    return f"{val:.0f}元"

def build_wechat_message(rows, now_str):
    """构建微信推送的标题和正文（支持 Server酱 Markdown）"""
    today = datetime.now().strftime("%Y-%m-%d")

    def prem_cell(r, bold=True):
        """格式化溢价单元格，EST日期非今日时附加参考溢价"""
        prem = r["premium"]
        if prem is None:
            return "—"
        sign = "+" if prem > 0 else ""
        prem_str = f"**{sign}{prem:.2f}%**" if bold and prem > 0 else f"{sign}{prem:.2f}%"
        est_date = r.get("est_date")
        ref = r.get("ref_premium")
        if est_date and est_date != today:
            if ref is not None:
                ref_sign = "+" if ref > 0 else ""
                prem_str += f"（参考: {ref_sign}{ref:.2f}%）"
            else:
                prem_str += " ⚠️"
        return prem_str

    stale_est = any(r.get("est_date") and r["est_date"] != today for r in rows)

    arb = [r for r in rows if (r["premium"] or 0) > 0 and r["status"] in ("open", "limited")]
    all_pos = [r for r in rows if (r["premium"] or 0) > 0]
    # 新增：负溢价（折价）相关数据筛选
    discount = [r for r in rows if (r["premium"] or 0) < 0]  # 所有折价基金
    discount_top10 = sorted(discount, key=lambda x: (x["premium"] or 999))[:10]  # 折价最多的前10只

    title = f"LOF溢价提醒 {now_str}  |  【{len(arb)}】只套利机会  |  【{len(discount)}】只折价"
    if not arb and not discount:
        title = f"LOF溢价提醒 {now_str}  |  暂无套利/折价机会"
    elif not arb:
        title = f"LOF溢价提醒 {now_str}  |  暂无套利机会  |  【{len(discount)}】只折价"
    elif not discount:
        title = f"LOF溢价提醒 {now_str}  |  【{len(arb)}】只套利机会  |  暂无折价"
    lines = [f"## LOF基金 溢价/折价追踪 · {now_str}", ""]

    if stale_est:
        lines.append("> ⚠️ 部分基金EST日期非今日，溢价率可能存在滞后，已显示参考EST溢价（如有）")
        lines.append("")

    # 套利机会（正溢价）
    if arb:
        lines.append(f"### ⚡ 溢价机会（正溢价｜{len(arb)}只）")
        lines.append("")
        lines.append("| 基金 | 溢价 | 限额 | 状态 |")
        lines.append("|------|------|------|------|")
        for r in arb:
            lines.append(
                f"| {r['name']} `{r['full_code']}` "
                f"| {prem_cell(r, bold=True)} "
                f"| {fmt_money(r['quota'])} "
                f"| {r['status_text']} |"
            )
        lines.append("")
    else:
        lines.append("### ⚡ 套利机会（正溢价）｜暂无")
        lines.append("")

    # 所有溢价基金（含暂停申购的）
    if all_pos:
        closed_pos = [r for r in all_pos if r["status"] not in ("open", "limited")]
        if closed_pos:
            lines.append(f"### ⚠️ 溢价但已暂停申购（{len(closed_pos)}只）")
            lines.append("")
            for r in closed_pos:
                lines.append(f"- {r['name']} `{r['full_code']}` 溢价 **{prem_cell(r, bold=False)}** · {r['status_text']}")
            lines.append("")

    # 新增：负溢价（折价）表格
    if discount:
        lines.append(f"### 📉 折价排行（负溢价｜前10只）")
        lines.append("")
        lines.append("| 排名 | 基金 | 折价率 | 限额 | 状态 |")
        lines.append("|------|------|--------|------|------|")
        for i, r in enumerate(discount_top10, 1):
            lines.append(
                f"| {i} | {r['name']} `{r['full_code']}` "
                f"| {prem_cell(r, bold=False)} "
                f"| {fmt_money(r['quota'])} "
                f"| {r['status_text']} |"
            )
        lines.append("")
    else:
        lines.append("### 📉 折价排行（负溢价）｜暂无")
        lines.append("")

    # 全部溢价率排行（保留原前10，可按需调整）
    lines.append("### 📊 全量溢价率排行（前10）")
    lines.append("")
    lines.append("| 排名 | 基金 | 溢价率 | 限额 |")
    lines.append("|------|------|--------|------|")
    for i, r in enumerate(rows[:10], 1):
        lines.append(f"| {i} | {r['name']} | {prem_cell(r, bold=False)} | {fmt_money(r['quota'])} |")

    lines.append("")
    lines.append(f"---")
    lines.append(f"*数据来源：palmmicro + 天天基金 · {now_str}*")

    return title, "\n".join(lines)

# ─── Server酱推送 ─────────────────────────────────────────────────────────────

def send_wechat(title, content, sendkey):
    """通过 Server酱 推送微信消息"""
    url = f"https://sctapi.ftqq.com/{sendkey}.send"
    try:
        r = requests.post(url, data={
            "title": title,
            "desp": content,
        }, timeout=15)
        result = r.json()
        if result.get("code") == 0:
            print(f"✅ 微信推送成功")
        else:
            print(f"⚠️  推送失败: {result}")
    except Exception as e:
        print(f"❌ 推送异常: {e}")

# ─── 飞书推送 ─────────────────────────────────────────────────────────────────

def send_feishu(title, content, app_id, app_secret, chat_id):
    """通过飞书机器人推送消息到指定群"""
    try:
        # 获取 tenant_access_token
        token_res = requests.post(
            "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
            json={"app_id": app_id, "app_secret": app_secret},
            timeout=10
        )
        access_token = token_res.json().get("tenant_access_token", "")
        if not access_token:
            print("⚠️  飞书 token 获取失败")
            return

        # 发送消息
        msg = f"{title}\n\n{content}"
        res = requests.post(
            "https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=chat_id",
            headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"},
            json={"receive_id": chat_id, "msg_type": "text", "content": json.dumps({"text": msg})},
            timeout=10
        )
        if res.json().get("code") == 0:
            print("✅ 飞书推送成功")
        else:
            print(f"⚠️  飞书推送失败: {res.json()}")
    except Exception as e:
        print(f"❌ 飞书推送异常: {e}")

# ─── 历史记录 CSV ─────────────────────────────────────────────────────────────

def save_history_csv(rows, now_str, filepath="history.csv"):
    """追加一行到历史CSV"""
    file_exists = os.path.exists(filepath)
    with open(filepath, "a", newline="", encoding="utf-8-sig") as f:
        fieldnames = ["时间"] + [r["full_code"] for r in rows]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()
        row = {"时间": now_str}
        for r in rows:
            row[r["full_code"]] = r["premium"] if r["premium"] is not None else ""
        writer.writerow(row)
    print(f"历史记录已追加到 {filepath}")

# ─── 本地测试 ─────────────────────────────────────────────────────────────────

def make_test_rows():
    """生成模拟数据，覆盖推送消息的所有场景：套利机会、暂停申购、折价排行"""
    return [
        # 正溢价 + 正常申购 → 套利机会
        {"full_code": "SZ164906", "code6": "164906", "name": "中概互联网LOF",
         "price": 1.520, "change": 2.15, "est": 1.450, "premium": 4.83,
         "status": "open", "status_text": "正常申购", "quota": None, "big_quota": None},
        # 正溢价 + 限额申购 → 套利机会（有限额）
        {"full_code": "SZ161130", "code6": "161130", "name": "纳斯达克100LOF",
         "price": 2.180, "change": 1.88, "est": 2.100, "premium": 3.81,
         "status": "limited", "status_text": "限额申购", "quota": 10000.0, "big_quota": None},
        # 正溢价 + 暂停申购 → 溢价但已暂停
        {"full_code": "SZ162415", "code6": "162415", "name": "美国消费LOF",
         "price": 1.350, "change": 0.75, "est": 1.310, "premium": 3.05,
         "status": "closed", "status_text": "暂停申购", "quota": None, "big_quota": None},
        # 正溢价 + 限制大额
        {"full_code": "SH501018", "code6": "501018", "name": "南方原油LOF",
         "price": 1.220, "change": -0.81, "est": 1.200, "premium": 1.67,
         "status": "limited", "status_text": "限制大额", "quota": 1000000.0, "big_quota": None},
        # 微小正溢价 + 正常申购
        {"full_code": "SZ160719", "code6": "160719", "name": "嘉实黄金LOF",
         "price": 3.580, "change": 0.56, "est": 3.560, "premium": 0.56,
         "status": "open", "status_text": "正常申购", "quota": None, "big_quota": None},
        # 折价
        {"full_code": "SZ161226", "code6": "161226", "name": "国投白银LOF",
         "price": 3.120, "change": 3.22, "est": 3.180, "premium": -1.89,
         "status": "open", "status_text": "正常申购", "quota": None, "big_quota": None},
        {"full_code": "SZ160140", "code6": "160140", "name": "美国REIT精选LOF",
         "price": 1.340, "change": 1.82, "est": 1.380, "premium": -2.90,
         "status": "open", "status_text": "正常申购", "quota": None, "big_quota": None},
    ]


# ─── 本地表格输出 ─────────────────────────────────────────────────────────────

def print_local_table(rows, now_str):
    """在终端以对齐表格打印完整查询结果，供本地调试使用"""
    today = datetime.now().strftime("%Y-%m-%d")

    # ANSI 颜色（Windows cmd 不一定支持，Terminal/iTerm/Linux 均可）
    RED    = "\033[91m"
    GREEN  = "\033[92m"
    YELLOW = "\033[93m"
    CYAN   = "\033[96m"
    RESET  = "\033[0m"
    BOLD   = "\033[1m"

    def color_prem(val, est_date):
        if val is None:
            return "   —   "
        sign = "+" if val > 0 else ""
        stale = est_date and est_date != today
        text = f"{sign}{val:+.2f}%"
        if stale:
            text += "⚠"
        if val > 2:
            return RED + BOLD + text + RESET
        elif val > 0:
            return RED + text + RESET
        else:
            return GREEN + text + RESET

    def color_status(status, text):
        if status == "open":
            return GREEN + text + RESET
        elif status == "limited":
            return YELLOW + text + RESET
        elif status == "closed":
            return RED + text + RESET
        return text

    sep = "─" * 78
    print(f"\n{BOLD}{CYAN}{'═'*78}{RESET}")
    print(f"{BOLD}{CYAN}  LOF 溢价实时查询  ·  {now_str}{RESET}")
    print(f"{BOLD}{CYAN}{'═'*78}{RESET}")
    print(f"  {'排':>2}  {'代码':<10}  {'基金名称':<16}  {'现价':>7}  {'涨跌':>7}  {'EST':>7}  {'溢价率':>10}  {'状态':<8}  {'限额'}")
    print(sep)

    arb_count = 0
    for i, r in enumerate(rows, 1):
        prem    = r["premium"]
        price   = r["price"]
        change  = r["change"]
        est     = r["est"]
        status  = r["status"]

        price_s  = f"{price:.3f}"  if price  is not None else "  —  "
        change_s = f"{change:+.2f}%" if change is not None else "  —  "
        est_s    = f"{est:.3f}"    if est    is not None else "  —  "
        prem_s   = color_prem(prem, r.get("est_date"))
        status_s = color_status(status, r["status_text"])
        quota_s  = fmt_money(r["quota"])

        if prem and prem > 0 and status in ("open", "limited"):
            arb_count += 1
            rank_s = f"{BOLD}{RED}{i:>2}{RESET}"
        else:
            rank_s = f"{i:>2}"

        print(f"  {rank_s}  {r['full_code']:<10}  {r['name']:<16}  {price_s:>7}  {change_s:>8}  {est_s:>7}  {prem_s:>10}  {status_s:<8}  {quota_s}")

    print(sep)

    # 汇总行
    arb_rows    = [r for r in rows if (r["premium"] or 0) > 0 and r["status"] in ("open","limited")]
    closed_rows = [r for r in rows if (r["premium"] or 0) > 0 and r["status"] not in ("open","limited")]

    print(f"\n  {BOLD}套利机会{RESET}（正溢价且可申购）：{RED}{BOLD}{arb_count} 只{RESET}")
    if arb_rows:
        for r in arb_rows:
            sign = "+" if (r["premium"] or 0) > 0 else ""
            stale = "⚠ EST非今日 " if r.get("est_date") and r["est_date"] != today else ""
            print(f"    → {r['name']} {r['full_code']}  溢价 {RED}{sign}{r['premium']:.2f}%{RESET}  {stale}{r['status_text']}  限额:{fmt_money(r['quota'])}")

    if closed_rows:
        print(f"\n  {BOLD}溢价但暂停申购{RESET}（{len(closed_rows)} 只）：")
        for r in closed_rows:
            print(f"    ⚠ {r['name']} {r['full_code']}  溢价 {r['premium']:.2f}%  · {r['status_text']}")

    stale = [r for r in rows if r.get("est_date") and r["est_date"] != today]
    if stale:
        print(f"\n  {YELLOW}⚠  {len(stale)} 只基金的EST日期非今日，溢价率可能滞后{RESET}")
        for r in stale:
            ref = r.get("ref_premium")
            ref_s = f"  参考溢价: {ref:+.2f}%" if ref is not None else ""
            print(f"     · {r['name']}  EST日期: {r['est_date']}{ref_s}")

    print(f"\n  数据来源: palmmicro + 天天基金  ·  {now_str}")
    print(f"{CYAN}{'═'*78}{RESET}\n")


# ─── 主程序 ──────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="LOF基金溢价率监控")
    parser.add_argument(
        "--test", action="store_true",
        help="使用模拟数据测试消息格式和推送（不抓取真实数据，不写入 CSV）"
    )
    parser.add_argument(
        "--local", action="store_true",
        help="本地调试模式：抓取真实数据，终端表格展示，不写入 CSV，不推送微信"
    )
    args = parser.parse_args()

    load_dotenv()  # 优先从本地 .env 文件加载 SERVERCHAN_KEY

    sendkeys = [
        "SCT348643TPeDG7b88AeaCEbpc4uqvPKv2",
         "SCT348625TeaJCpA5WwJh1WDaoGcZe1BwT",
         "SCT348719TRYV90SZ6SujEIaE4bwMFub7Q",
         "SCT348724TwhQxyd8VBZJxnOFNJyffnxBu",
         "SCT357633THXXXk2DrGEYMXm6szQYYxdaG",
         "SCT350784TJfHeBylPaT1ikEB0AxOBMaWV"
    ]
    sendkey ="123"
    # for i in ["", "1", "2", "3", "4", "5"]:
    #     sendkey = os.environ.get(f"SERVERCHAN_KEY{i}", "").strip()
    #     if sendkey:
    #         sendkeys.append(sendkey)
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")

    if args.local:
        print(f"=== [本地模式] LOF溢价监控 {now_str} ===")
        premium_map, fund_list = fetch_premium()
        if not fund_list:
            print("  未获取到基金列表，退出")
            return
        time.sleep(0.5)
        price_map = fetch_prices(fund_list)
        time.sleep(0.5)
        quota_map = fetch_quota(fund_list)
        rows = merge(premium_map, price_map, quota_map, fund_list)
        print_local_table(rows, now_str)
        return  # 本地模式到此结束，不写 CSV，不推送

    if args.test:
        print(f"=== [测试模式] LOF溢价监控 {now_str} ===")
        print("使用模拟数据，不请求远程接口，不写入 history.csv\n")
        rows = make_test_rows()
        title, content = build_wechat_message(rows, now_str)
        # 测试模式在标题加【测试】标记，便于在微信中识别
        title = f"【测试】{title}"
        
        # 始终在终端打印完整消息，便于本地核查
        print(f"\n{'─'*60}")
        print(f"标题：{title}")
        print(f"{'─'*60}")
        print(content)
        print(f"{'─'*60}\n")
        
        print("💡 测试模式：不发送微信/飞书推送")
        return  # 测试模式到此结束，不推送
    else:
        if not sendkey:
            print("⚠️  未设置 SERVERCHAN_KEY 环境变量，将跳过微信推送")
        print(f"=== LOF溢价监控 {now_str} ===")
        premium_map, fund_list = fetch_premium()
        if not fund_list:
            print("  未获取到基金列表，退出")
            return
        time.sleep(0.5)
        price_map = fetch_prices(fund_list)
        time.sleep(0.5)
        quota_map = fetch_quota(fund_list)
        rows = merge(premium_map, price_map, quota_map, fund_list)
        save_history_csv(rows, now_str)
        title, content = build_wechat_message(rows, now_str)

    # 始终在终端打印完整消息，便于本地核查
    print(f"\n{'─'*60}")
    print(f"标题：{title}")
    print(f"{'─'*60}")
    print(content)
    print(f"{'─'*60}\n")

    # if sendkey:
    #     send_wechat(title, content, sendkey)
    for key in sendkeys:
        send_wechat(title, content, key)
        print(f"发送 key是: {key}")
    
    feishu_app_id     = os.environ.get("FEISHU_APP_ID", "")
    feishu_app_secret = os.environ.get("FEISHU_APP_SECRET", "")
    feishu_chat_id    = os.environ.get("FEISHU_CHAT_ID", "")
    if feishu_app_id and feishu_app_secret and feishu_chat_id:
        send_feishu(title, content, feishu_app_id, feishu_app_secret, feishu_chat_id)
    elif args.test:
        print("💡 提示：在项目根目录创建 .env 文件并写入 SERVERCHAN_KEY=SCTxxx 即可同时测试实际推送")

if __name__ == "__main__":
    main()
