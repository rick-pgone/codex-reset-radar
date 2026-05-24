# Codex Reset Radar

一个静态页面 + 本地 X 采集脚本，用来监测 Codex usage limit / reset 相关信号。

## 本地文件

- `codex-reset-radar.html`：前端页面。
- `data/latest.json`：前端读取的数据源。
- `scripts/update_reset_radar.py`：从 X 拉取信息、筛选、打标签，并更新 `data/latest.json`。
- `scripts/install_launchd.sh`：在 macOS 上安装每 12 小时执行一次的本地定时任务。
- `scripts/package_site.sh`：把线上需要的文件打包到 `dist/`。

## 第一次运行

本项目使用本地 X 登录态，不使用 X 官方 API。

先刷新一次登录 cookie：

```bash
/opt/homebrew/bin/python3.11 scripts/update_reset_radar.py --refresh-login --cadence-hours 12
```

如果打开 X 登录窗口，完成登录后脚本会把 cookie 保存到：

```text
/Users/rick/登录态/x_cookies.json
```

之后手动更新数据：

```bash
/opt/homebrew/bin/python3.11 scripts/update_reset_radar.py --cadence-hours 12
```

## 本地预览

不要直接用 `file://` 验证动态 JSON。浏览器会阻止 `fetch(data/latest.json)`。

使用静态服务器：

```bash
python3 -m http.server 8787
```

然后打开：

```text
http://127.0.0.1:8787/codex-reset-radar.html
```

## 安装 12 小时定时任务

```bash
./scripts/install_launchd.sh
```

查看日志：

```bash
tail -f logs/update_reset_radar.out.log
tail -f logs/update_reset_radar.err.log
```

停止任务：

```bash
launchctl unload ~/Library/LaunchAgents/com.rick.codex-reset-radar.plist
```

重新安装任务：

```bash
./scripts/install_launchd.sh
```

## 推荐上线方式

推荐：Cloudflare Pages + Cloudflare Registrar。

原因：

- 前端是纯静态页面，Cloudflare Pages 免费额度足够。
- 域名、DNS、Pages 自定义域名都在 Cloudflare 一个地方管理。
- 本地脚本每 12 小时更新 `data/latest.json` 后，只要提交到 GitHub，Cloudflare Pages 会自动重新部署。

### 上线流程

1. 新建 GitHub 仓库，例如 `codex-reset-radar`。
2. 把以下文件提交到仓库：
   - `codex-reset-radar.html`
   - `data/latest.json`
   - `scripts/update_reset_radar.py`
   - `scripts/install_launchd.sh`
   - `scripts/package_site.sh`
   - `README-codex-reset-radar.md`
3. Cloudflare Dashboard 里进入 Workers & Pages，创建 Pages 项目。
4. 连接 GitHub 仓库。
5. 构建设置：
   - Build command：`./scripts/package_site.sh`
   - Build output directory：`dist`
6. 部署后先得到一个 `*.pages.dev` 地址。
7. 在 Cloudflare Registrar 购买域名。
8. 在 Pages 项目里添加 Custom Domain。
9. Cloudflare 会自动处理 DNS 和证书。

## 自动发布数据

如果你希望本地每 12 小时更新后自动上线，可以让脚本更新 JSON 后执行：

```bash
git add data/latest.json
git commit -m "Update reset radar data"
git push
```

当前目录还不是 git 仓库。等你确定 GitHub 仓库地址后，再把自动提交/推送加进定时任务。

## 云服务器方案

如果要把采集任务也放到云服务器，推荐低配 Ubuntu VPS：

- 性价比优先：Hetzner CX22 / ARM 低配，约 4-5 美元/月，适合欧洲/美国访问。
- 更容易购买和管理：DigitalOcean Basic Droplet，官方页面显示 Droplet 起步价约 4 美元/月，常见 1GB 档约 6 美元/月。
- 最省钱但开通不稳定：Oracle Cloud Always Free，官方 Always Free 文档显示 ARM A1 有免费资源，但经常需要抢可用区容量。

云服务器部署脚本在：

```bash
deploy/ubuntu-vps-setup.sh
```

服务器上运行方式：

```bash
REPO_URL=https://github.com/rick-pgone/codex-reset-radar.git \
DOMAIN=your-domain.com \
sudo -E bash deploy/ubuntu-vps-setup.sh
```

注意：如果采集任务放云服务器，需要把 X 登录 cookie 安全复制到服务器。不要提交到 GitHub。
