# 🛡️ 爬虫准备工作完整指南

> 在开始爬取之前，请按顺序完成以下所有步骤。全部准备好再开始！

---

## 📋 目录

1. [策略总览](#1-策略总览)
2. [第一步：注册小号](#2-第一步注册小号)
3. [第二步：获取 Cookie](#3-第二步获取-cookie)
4. [第三步：配置代理IP](#4-第三步配置代理ip)
5. [第四步：测试验证](#5-第四步测试验证)
6. [第五步：配置定时任务](#6-第五步配置定时任务)
7. [日常维护清单](#7-日常维护清单)
8. [风险评估与应急预案](#8-风险评估与应急预案)

---

## 1. 策略总览

### 爬取节奏

| 星期 | 任务 | 预计耗时 |
|------|------|---------|
| 周一 | 支付宝（~10个关键词） | 15-30分钟 |
| 周二 | 微信支付（~7个关键词） | 10-20分钟 |
| 周三 | 抖音支付（~6个关键词） | 10-15分钟 |
| 周四 | 美团支付（~6个关键词） | 10-15分钟 |
| 周五 | 京东支付（~6个关键词） | 10-15分钟 |
| 周六 | 云闪付（~3个关键词） | 5-10分钟 |
| **周日** | **休息 + 自动整理输出** | 1-2分钟 |

### 为什么这样做？

- **每天只发 ~10-20 个请求**，正常用户一天刷小红书搜几十次都正常
- **分散到6天**，比一次性爆发2-3小时安全得多
- **每次间隔15-60秒**，加上随机浏览推荐页，行为模式跟真人一样
- **周日不爬取**，给账号一天"休息"，降低风控概率

---

## 2. 第一步：注册小号

### 为什么要小号？

用小号爬取，即使最坏情况被封号，也不影响你的主账号。**绝不要用主号的 Cookie！**

### 注册步骤

1. **准备一个新手机号**
   - 可以用虚拟手机号（如 Google Voice、TextNow）
   - 或者用家人的闲置手机号
   - 或购买一个预付费 SIM 卡（十几块钱）

2. **在浏览器中注册**
   - 打开 https://www.xiaohongshu.com
   - 点击右上角"登录"
   - 选择"手机号登录" → 输入新手机号 → 收验证码
   - 完成注册

3. **养号（重要！新号直接爬容易被风控）**
   - 注册后**不要马上爬取**！
   - 用这个账号**正常浏览 3-5 天**：
     - 每天花 5-10 分钟刷推荐页
     - 搜索几个话题
     - 偶尔点赞、收藏
   - 让平台认为这是一个正常活跃用户
   - **养号期间不要用爬虫！**

4. **养号完成标志**
   - 连续登录3天以上
   - 有正常的浏览、搜索记录
   - 账号状态正常（能正常搜索、没有弹验证码）

---

## 3. 第二步：获取 Cookie

### 什么是 Cookie？

Cookie 中的 `web_session` 是你的登录凭证，爬虫需要它来伪装成你的浏览器。

### 获取步骤（Chrome 浏览器）

1. **打开 Chrome 浏览器**，进入 https://www.xiaohongshu.com

2. **用小号登录**（不是主号！）

3. **打开开发者工具**
   - Mac: `Cmd + Option + I`
   - Windows: `F12` 或 `Ctrl + Shift + I`

4. **切换到 Application 标签页**
   - 点击顶部的 `Application`（如果看不到，点 `>>` 展开）

5. **找到 Cookie**
   - 左侧面板：`Storage` → `Cookies` → `https://www.xiaohongshu.com`

6. **复制 web_session 的值**
   - 在 Cookie 列表中找到 `web_session`
   - 双击它的 `Value` 列，全选复制
   - 值类似：`040069xxxxxxxxxxxxxxxxxxxxxx`（一串十六进制字符）

7. **粘贴到项目中**
   ```bash
   # 方式一：直接编辑文件
   echo "你复制的web_session值" > cookie.txt
   
   # 方式二：用编辑器打开 cookie.txt，粘贴进去
   ```

### ⚠️ 注意事项

- `web_session` 大约 **7天过期**，过期后需要重新获取
- 获取 Cookie 后，**不要在浏览器中退出登录**（退出会使 Cookie 立即失效）
- 可以关闭浏览器标签页，但不要点"退出"
- 如果爬虫报告 "Session 已失效"，就是 Cookie 过期了，重新获取即可

### 快速验证 Cookie 是否有效

```bash
# 在项目目录下运行
python3 safe_crawler.py --session-file cookie.txt --dry-run
```

如果显示 `✅ Session 有效` 就OK了。

---

## 4. 第三步：配置代理IP

### 为什么需要代理？

- **不用代理**：所有请求来自你的家庭IP，长期爬取有聚类风险
- **用代理**：请求来自不同IP，极大降低被识别为爬虫的概率

### 方案选择

#### 方案A：免费代理（不推荐，不稳定但零成本试水）

不推荐长期使用，但可以先试试：

```bash
# 找免费 SOCKS5 代理（不稳定，随时失效）
# 搜索 "free socks5 proxy list"，如 https://www.socks-proxy.net/
# 编辑 proxy.txt：
socks5://IP:端口
```

#### 方案B：使用 VPN 的 SOCKS5 模式（推荐入门）

如果你已经有 VPN（Clash/V2ray/Shadowsocks 等），它们通常自带 SOCKS5 代理端口：

**Clash 用户：**
```bash
# Clash 默认的本地 SOCKS5 端口是 7891
# 编辑 proxy.txt：
socks5://127.0.0.1:7891
```

**V2ray/Xray 用户：**
```bash
# 查看你的配置，一般有 SOCKS5 入站（inbound），默认端口 10808
# 编辑 proxy.txt：
socks5://127.0.0.1:10808
```

**Shadowsocks 用户：**
```bash
# 默认本地 SOCKS5 端口是 1080
# 编辑 proxy.txt：
socks5://127.0.0.1:1080
```

**确认端口的方法：**
```bash
# 测试代理是否通
curl --socks5 127.0.0.1:7891 https://httpbin.org/ip
# 如果返回了IP地址（且不是你的真实IP），说明代理可用
```

#### 方案C：付费住宅代理（最安全，推荐长期使用）

住宅代理使用真实家庭宽带IP，几乎不会被检测。推荐服务商：

| 服务商 | 价格 | 特点 | 注册链接 |
|--------|------|------|---------|
| **Smartproxy** | ~$14/月(2GB) | 全球住宅IP池4000万+ | smartproxy.com |
| **Bright Data** | ~$15/月(按量) | 业界最大IP池 | brightdata.com |
| **IPIDEA** | ~¥50/月 | 中国厂商，支持中文 | ipidea.net |
| **快代理** | ~¥30/月 | 国内厂商 | kuaidaili.com |
| **站大爷** | ~¥25/月 | 国内厂商 | zhimaruanjian.com |

以 Smartproxy 为例的配置步骤：
1. 注册账号并购买住宅代理套餐
2. 在控制台获取代理凭证（用户名、密码、代理地址）
3. 编辑 `proxy.txt`：
   ```
   socks5://用户名:密码@gate.smartproxy.com:7000
   ```

#### 方案D：多代理池轮换（最佳实践）

如果有多个代理，爬虫会每次随机选一个：

```bash
# 编辑 proxy.txt，填入多个代理地址：
socks5://user:pass@proxy1.example.com:1080
socks5://user:pass@proxy2.example.com:1080
http://user:pass@proxy3.example.com:8080
socks5://127.0.0.1:7891
```

### 配置完成后验证

```bash
# 测试代理是否生效
python3 -c "
import asyncio, sys, os
sys.path.insert(0, os.path.join('skills', 'xiaohongshutools', 'scripts'))
from request.web.xhs_session import create_xhs_session

async def test():
    # 读取代理
    proxy = None
    if os.path.exists('proxy.txt'):
        with open('proxy.txt') as f:
            lines = [l.strip() for l in f if l.strip() and not l.startswith('#')]
        if lines:
            proxy = lines[0]
            print(f'使用代理: {proxy[:30]}...')
    
    cookie = open('cookie.txt').read().strip()
    xhs = await create_xhs_session(proxy=proxy, web_session=cookie)
    print('✅ 会话创建成功（代理连接正常）')
    await xhs.close_session()

asyncio.run(test())
"
```

---

## 5. 第四步：测试验证

在正式开始前，务必做一次完整测试：

### 5.1 试运行（不实际爬取）

```bash
cd /Users/zimyin/CodeBuddy/20260317215615

# 查看今天的爬取计划
python3 safe_crawler.py --session-file cookie.txt --dry-run
```

这会显示今天应该爬哪个平台、有哪些关键词，但不会发出任何请求。

### 5.2 小范围真实测试

```bash
# 只爬1个平台试试（选一个关键词最少的）
python3 safe_crawler.py --session-file cookie.txt --platform 云闪付
```

观察输出：
- ✅ `Session 有效` — Cookie OK
- ✅ `获取 X 条` — 爬取正常
- ⚠️ `空响应` — 可能有风控，停下来等24小时
- 🚨 `Session 已失效` — Cookie 过期了，重新获取

### 5.3 确认数据写入

```bash
# 查看数据文件
python3 -c "import json; d=json.load(open('real_data.json')); print(f'总计 {len(d[\"notes\"])} 条笔记')"
```

---

## 6. 第五步：配置定时任务

测试通过后，配置自动每天运行。

### 方式一：Crontab（推荐）

```bash
# 1. 先给脚本加执行权限
chmod +x /Users/zimyin/CodeBuddy/20260317215615/run_daily_crawl.sh

# 2. 编辑 crontab
crontab -e

# 3. 添加以下行（选一种）：
```

**选项A：每天固定中午12点运行**
```cron
0 12 * * * /Users/zimyin/CodeBuddy/20260317215615/run_daily_crawl.sh >> /Users/zimyin/CodeBuddy/20260317215615/cron_crawl.log 2>&1
```

**选项B：每天11-14点之间随机时间运行（更像真人，推荐！）**
```cron
0 11 * * * sleep $((RANDOM \% 10800)) && /Users/zimyin/CodeBuddy/20260317215615/run_daily_crawl.sh >> /Users/zimyin/CodeBuddy/20260317215615/cron_crawl.log 2>&1
```

**选项C：每天晚上10点运行（模拟晚上刷手机）**
```cron
0 22 * * * /Users/zimyin/CodeBuddy/20260317215615/run_daily_crawl.sh >> /Users/zimyin/CodeBuddy/20260317215615/cron_crawl.log 2>&1
```

### 方式二：macOS launchd（Mac 推荐）

创建 plist 文件实现开机自启+定时运行：

```bash
# 创建 plist（已自动生成在项目目录）
cp /Users/zimyin/CodeBuddy/20260317215615/com.fintech.daily-crawler.plist ~/Library/LaunchAgents/

# 加载
launchctl load ~/Library/LaunchAgents/com.fintech.daily-crawler.plist

# 查看状态
launchctl list | grep fintech
```

### 验证定时任务

```bash
# 查看当前的 crontab
crontab -l

# 查看运行日志
tail -50 /Users/zimyin/CodeBuddy/20260317215615/cron_crawl.log
```

---

## 7. 日常维护清单

### 每周必做（周日）

| # | 任务 | 操作 | 耗时 |
|---|------|------|------|
| 1 | 检查 Cookie 是否即将过期 | 看日志有无 "Session 已失效" | 1分钟 |
| 2 | 更新 Cookie（如已过期） | 重新从浏览器获取 web_session | 3分钟 |
| 3 | 查看爬取日志 | `tail -100 safe_crawl.log` | 2分钟 |
| 4 | 确认数据更新 | 打开网页看数据量是否增长 | 1分钟 |

### Cookie 续期快捷流程

```bash
# 1. 在浏览器打开小红书并用小号登录
# 2. 打开开发者工具 → Application → Cookies
# 3. 复制 web_session 的值
# 4. 更新 cookie.txt

echo "新的web_session值" > /Users/zimyin/CodeBuddy/20260317215615/cookie.txt

# 5. 验证
python3 /Users/zimyin/CodeBuddy/20260317215615/safe_crawler.py --session-file cookie.txt --dry-run
```

### 异常处理

| 现象 | 原因 | 处理 |
|------|------|------|
| "Session 已失效" | Cookie 过期 | 重新获取 Cookie |
| "风控检测" | 请求频率可能偏高 | 等24小时再试，检查代理是否生效 |
| "滑块验证" | 平台检测到异常 | 暂停2-3天，在浏览器中手动验证 |
| 连续3天无新数据 | 关键词重复率高 | 正常现象，说明增量已充分 |
| 代理连接失败 | 代理服务不可用 | 检查代理是否还能用，换一个 |

---

## 8. 风险评估与应急预案

### 风险等级评估

| 风险 | 使用小号+代理后概率 | 影响 |
|------|-------------------|------|
| 小号被封 | 极低（~1%/月） | 重新注册一个，无损失 |
| 主号受影响 | 零（完全隔离） | — |
| IP被封 | 极低（用代理后） | 换个代理IP即可 |
| 数据丢失 | 零 | 本地有 real_data.json 持久化 |

### 应急预案

**如果小号被封：**
1. 不要慌，这就是用小号的意义
2. 注册一个新小号
3. 养号3-5天
4. 获取新 Cookie 更新到 cookie.txt
5. 继续爬取（已有数据完好无损）

**如果代理被封：**
1. 更换代理IP
2. 如果用 proxy.txt 多代理池，自动会切换

**如果被要求滑块验证：**
1. 暂停爬虫3天
2. 在浏览器中用小号手动完成滑块验证
3. 重新获取 Cookie
4. 恢复爬取

---

## ✅ 准备工作检查清单

在开始爬取前，确认以下全部完成：

- [ ] **小号已注册** — 用新手机号注册小红书账号
- [ ] **小号已养号** — 连续正常使用3-5天
- [ ] **Cookie 已获取** — `cookie.txt` 中有 web_session 值
- [ ] **代理已配置** — `proxy.txt` 中至少有1个可用代理
- [ ] **试运行通过** — `--dry-run` 显示 Session 有效
- [ ] **小范围测试通过** — 爬了1个平台，数据正常写入
- [ ] **定时任务已配置** — crontab 或 launchd 已设置

**全部打勾后，就可以放心让它每天自动跑了！** 🎉

---

## 快速启动命令汇总

```bash
cd /Users/zimyin/CodeBuddy/20260317215615

# 1. 手动运行一次（自动按星期分配平台）
bash run_daily_crawl.sh

# 2. 手动指定平台
python3 safe_crawler.py --session-file cookie.txt --platform 支付宝

# 3. 带代理运行
python3 safe_crawler.py --session-file cookie.txt --proxy socks5://127.0.0.1:7891

# 4. 试运行
python3 safe_crawler.py --session-file cookie.txt --dry-run

# 5. 断点续爬
python3 safe_crawler.py --session-file cookie.txt --resume

# 6. 周日整理（不爬取）
python3 safe_crawler.py --weekly-build

# 7. 查看日志
tail -50 safe_crawl.log
cat cron_crawl.log
```
