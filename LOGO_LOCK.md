# Logo 锁定配置 - 勿修改

## 微信支付 logo
SVG viewBox="38 12 44 38", fill="#14AB39" (绿色气泡聊天图标，单个path元素)
**绝对不要**用 viewBox="0 0 48 48" 带 rect+ellipse+circle 的简笔画版本
**绝对不要**用 viewBox="0 0 100 100" circle 4CB648 的打勾版本

## 抖音支付 logo
SVG viewBox="0 0 48 48", rect fill="#000" (黑底), 音符 fill="#fff" (白色)
**必须带** #25F4EE 和 #FE2C55 两个彩色点缀 path（opacity=".6"）
**必须有** `<g transform="translate(14,7)">` 包裹的三段 path
**绝对不要**用只有单个白色 path（无彩色点缀）的简化版本
**绝对不要**用白底黑音符版本

## 部署规则
- **绝不擅自部署到 Netlify**
- 只有用户明确说"部署"时才执行 netlify deploy --prod
- 每次 build_static.py 后必须检查 logo 是否被覆盖
