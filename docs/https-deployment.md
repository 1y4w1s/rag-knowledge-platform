# 睿阁 HTTPS 部署指南

> 适用场景：内网生产环境需要加密通信。
> 前置条件：已运行过 `docker compose up -d` 或 `docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build`。

---

## 方式一：自签证书（内网测试）

### 1. 生成证书

```powershell
.\scripts\gen-certs.ps1
```

生成文件：
- `docker/nginx/certs/ruige.crt` — 自签证书（PEM）
- `docker/nginx/certs/ruige.key` — 私钥

### 2. 启用 HTTPS

编辑 `docker-compose.prod.yml`，取消以下注释：

```yaml
  web:
    ports:
      - "80:80"
      - "443:443"          # ← 取消注释
    volumes:
      - ./docker/nginx/certs:/etc/nginx/certs:ro       # ← 取消注释
      - ./docker/nginx/ssl.conf:/etc/nginx/conf.d/ssl.conf:ro  # ← 取消注释
```

### 3. 重启

```powershell
docker compose -f docker-compose.yml -f docker-compose.prod.yml down
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

### 4. 访问

浏览器打开 `https://localhost`。因证书为自签，浏览器会提示「不安全」— 选择「高级 → 继续访问」。

---

## 方式二：权威证书（生产）

### 1. 获取证书

从 Let's Encrypt 或其他 CA 获取证书，放置到 `docker/nginx/certs/`：

```
docker/nginx/certs/
├── ruige.crt    # 包含完整证书链
├── ruige.key    # 私钥
```

Let's Encrypt 示例：

```bash
# 安装 certbot
sudo apt install certbot

# 申请证书（替换 your-domain.com）
sudo certbot certonly --standalone -d your-domain.com

# 复制到项目目录
sudo cp /etc/letsencrypt/live/your-domain.com/fullchain.pem docker/nginx/certs/ruige.crt
sudo cp /etc/letsencrypt/live/your-domain.com/privkey.pem docker/nginx/certs/ruige.key
```

### 2. 配置域名

编辑 `docker/nginx/ssl.conf`，将 `server_name _;` 改为你的域名：

```nginx
server {
    listen 443 ssl;
    server_name your-domain.com;  # ← 改为实际域名
    ...
}
```

### 3. 重启

同上。

### 4. 证书续期（Let's Encrypt）

添加 crontab 自动续期：

```bash
# 每月 1 日检查续期
0 0 1 * * certbot renew --deploy-hook "cd /path/to/project && docker compose -f docker-compose.yml -f docker-compose.prod.yml restart web"
```

---

## 验证

```powershell
# 验证 HTTPS 可用
curl -k https://localhost/health

# 验证 HTTP 自动重定向（如需）
# 取消 ssl.conf 中 HTTP→HTTPS 重定向注释后：
curl -I http://localhost/health
# 应返回 301 Moved Permanently
```

## 已知限制

| 限制 | 说明 |
|------|------|
| **自签证书不受浏览器信任** | 需要手动导入证书或添加例外。仅推荐内网测试使用。 |
| **无 OCSP Stapling** | 自签证书无法做 OCSP 装订（权威证书建议启用）。 |
| **证书续期非自动** | Let's Encrypt 的自动续期需配置 crontab（见上文）。 |
