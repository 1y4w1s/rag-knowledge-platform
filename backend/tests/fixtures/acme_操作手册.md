# AcmeCloud 运维操作手册 v2.1

**文档编号**：ACM-OPM-2025-001  
**版本号**：v2.1  
**发布日期**：2025年3月15日  
**密级**：内部公开  
**维护部门**：基础设施运维部  

---

## 修订记录

| 版本 | 修订日期 | 修订内容 | 修订人 |
|------|----------|----------|--------|
| v1.0 | 2024-01-10 | 初始版本创建 | 张三 |
| v2.0 | 2024-06-20 | 新增监控告警、安全配置章节 | 李四 |
| v2.1 | 2025-03-15 | 更新巡检项、备份策略、故障处理场景 | 王五 |

---

## 第1章 系统登录与访问

### 1.1 访问入口

AcmeCloud 平台提供以下访问入口：

| 服务名称 | 访问URL | 端口号 | 协议 |
|----------|---------|--------|------|
| 管理控制台 | https://admin.acmecloud.com | 443 | HTTPS |
| API网关 | https://api.acmecloud.com | 8443 | HTTPS |
| 运维管理平台 | https://ops.acmecloud.com | 9090 | HTTPS |
| 数据库管理 | https://db.acmecloud.com | 3306 | HTTPS |
| 监控面板 | https://monitor.acmecloud.com | 3000 | HTTPS |
| 日志中心 | https://logs.acmecloud.com | 5601 | HTTPS |

**内网访问地址**：
- 管理控制台：http://10.10.10.10:8080
- API网关：http://10.10.10.11:8081
- 运维管理平台：http://10.10.10.12:9090

### 1.2 默认账号与初始密码

| 角色 | 用户名 | 初始密码 | 强制修改 | 有效期 |
|------|--------|----------|----------|--------|
| 超级管理员 | admin | AcmeCloud@2025! | 是 | 90天 |
| 运维管理员 | ops_admin | Ops@2025#Secure | 是 | 90天 |
| 监控管理员 | monitor_admin | Mon@2025$Alert | 是 | 90天 |
| 只读用户 | readonly_user | Read@2025%Only | 是 | 180天 |

**密码策略**：
- 最小长度：16位
- 必须包含：大写字母、小写字母、数字、特殊字符
- 密码历史：禁止使用最近5次密码
- 登录失败锁定：连续5次失败锁定30分钟
- 会话超时：15分钟无操作自动登出

### 1.3 多因素认证配置

所有管理员账号必须启用MFA：
1. 登录后进入"个人设置" -> "安全设置"
2. 扫描二维码绑定Google Authenticator或Microsoft Authenticator
3. 输入6位动态验证码完成绑定
4. 备用验证码：生成10个一次性备用码，妥善保管

### 1.4 SSH访问配置

| 环境 | 跳板机IP | SSH端口 | 认证方式 |
|------|----------|---------|----------|
| 生产环境 | 10.20.30.40 | 2222 | 密钥+密码 |
| 预发布环境 | 10.20.30.41 | 2222 | 密钥 |
| 测试环境 | 10.20.30.42 | 2222 | 密钥 |

**SSH密钥要求**：
- 算法：RSA 4096位或Ed25519
- 密钥有效期：365天
- 禁止使用密码登录（除跳板机外）

---

## 第2章 日常巡检清单

### 2.1 巡检频率与执行人

| 巡检类型 | 频率 | 执行人 | 预计耗时 |
|----------|------|--------|----------|
| 日巡检 | 每日09:00、18:00 | 值班运维 | 30分钟 |
| 周巡检 | 每周一10:00 | 系统管理员 | 60分钟 |
| 月巡检 | 每月1日10:00 | 运维主管 | 120分钟 |
| 季度巡检 | 每季度首月 | 运维团队 | 240分钟 |

### 2.2 日巡检清单（15项）

| 序号 | 检查项 | 检查方法 | 正常值范围 | 异常处理 |
|------|--------|----------|------------|----------|
| 1 | CPU使用率 | `top -bn1 \| grep "Cpu(s)"` | < 75% | >80%触发告警 |
| 2 | 内存使用率 | `free -m \| grep Mem` | < 80% | >85%触发告警 |
| 3 | 磁盘使用率 | `df -h` | < 75% | >80%触发告警 |
| 4 | 磁盘IO等待 | `iostat -x 1 3` | < 10ms | >20ms触发告警 |
| 5 | 网络带宽使用率 | `nload` | < 60% | >80%触发告警 |
| 6 | 系统负载 | `uptime` | < 5.0 | >8.0触发告警 |
| 7 | 进程数 | `ps aux \| wc -l` | 200-500 | >800触发告警 |
| 8 | 打开文件数 | `lsof \| wc -l` | < 50000 | >80000触发告警 |
| 9 | 数据库连接数 | `show processlist;` | < 200 | >300触发告警 |
| 10 | Redis内存使用 | `info memory` | < 70% | >80%触发告警 |
| 11 | Nginx活跃连接 | `curl http://127.0.0.1/nginx_status` | < 1000 | >2000触发告警 |
| 12 | 应用响应时间 | `curl -o /dev/null -s -w %{time_total}` | < 500ms | >1000ms触发告警 |
| 13 | 错误日志数量 | `tail -1000 /var/log/app/error.log \| grep ERROR \| wc -l` | < 10 | >50触发告警 |
| 14 | SSL证书有效期 | `openssl s_client -connect domain:443` | > 30天 | < 7天触发告警 |
| 15 | 系统时间同步 | `ntpq -p` | offset < 50ms | >100ms触发告警 |

### 2.3 周巡检补充项

| 序号 | 检查项 | 正常值范围 | 备注 |
|------|--------|------------|------|
| 16 | 备份完整性检查 | 100%成功 | 检查最近7天备份 |
| 17 | 日志轮转检查 | 正常轮转 | 检查日志文件大小 |
| 18 | 防火墙规则检查 | 无异常变更 | 对比基线配置 |
| 19 | 用户权限审计 | 无异常账号 | 检查最近新增用户 |
| 20 | 安全补丁检查 | 无关键漏洞 | 检查CVE公告 |

### 2.4 巡检报告模板

```markdown
# 日巡检报告 - 2025-03-15 09:00

## 系统概况
- 主机名：acmecloud-prod-01
- IP地址：10.10.10.10
- 运行时间：45天12小时30分钟
- 操作系统：CentOS 7.9

## 检查结果
| 检查项 | 当前值 | 正常范围 | 状态 |
|--------|--------|----------|------|
| CPU使用率 | 45% | <75% | ✅ |
| 内存使用率 | 62% | <80% | ✅ |
| 磁盘使用率(/data) | 71% | <75% | ⚠️ 接近阈值 |
| ... | ... | ... | ... |

## 异常项
- 磁盘使用率(/data) 71%，建议清理或扩容

## 处理记录
- 已清理临时文件 2.3GB，使用率降至 68%

## 巡检人
- 张三 | 2025-03-15 09:30
```

---

## 第3章 备份操作步骤

### 3.1 备份策略总览

| 备份类型 | 频率 | 保留周期 | 存储位置 | 压缩方式 |
|----------|------|----------|----------|----------|
| 全量备份 | 每周日 02:00 | 30天 | /backup/full/ | gzip |
| 增量备份 | 每天 02:00 | 7天 | /backup/incremental/ | gzip |
| 日志备份 | 每天 04:00 | 90天 | /backup/logs/ | gzip |
| 配置备份 | 每次变更后 | 180天 | /backup/config/ | tar |

### 3.2 数据库备份（MySQL 8.0）

**全量备份脚本** `/usr/local/bin/mysql_full_backup.sh`：

```bash
#!/bin/bash
# 全量备份脚本 - 每周日02:00执行
BACKUP_DIR="/backup/full"
DATE=$(date +%Y%m%d_%H%M%S)
DB_USER="backup_user"
DB_PASS="Backup@2025!Secure"
DB_HOST="10.10.10.20"
DB_PORT=3306
DB_NAME="acmecloud_db"
RETENTION_DAYS=30

# 创建备份目录
mkdir -p ${BACKUP_DIR}/${DATE}

# 执行全量备份
mysqldump --single-transaction --routines --triggers --events \
  --host=${DB_HOST} --port=${DB_PORT} \
  --user=${DB_USER} --password=${DB_PASS} \
  ${DB_NAME} | gzip > ${BACKUP_DIR}/${DATE}/full_backup.sql.gz

# 检查备份是否成功
if [ $? -eq 0 ]; then
    echo "[$(date +%Y-%m-%d %H:%M:%S)] 全量备份成功: ${BACKUP_DIR}/${DATE}/full_backup.sql.gz"
    # 记录备份元数据
    echo "backup_time=$(date +%s),backup_type=full,size=$(du -sh ${BACKUP_DIR}/${DATE}/full_backup.sql.gz | cut -f1)" >> ${BACKUP_DIR}/backup_metadata.log
else
    echo "[$(date +%Y-%m-%d %H:%M:%S)] 全量备份失败" | mail -s "备份失败告警" ops@acmecloud.com
    exit 1
fi

# 清理过期备份
find ${BACKUP_DIR} -type d -mtime +${RETENTION_DAYS} -exec rm -rf {} \;
echo "[$(date +%Y-%m-%d %H:%M:%S)] 清理超过${RETENTION_DAYS}天的旧备份"
```

**增量备份脚本** `/usr/local/bin/mysql_incremental_backup.sh`：

```bash
#!/bin/bash
# 增量备份脚本 - 每天02:00执行（周日除外）
BACKUP_DIR="/backup/incremental"
DATE=$(date +%Y%m%d_%H%M%S)
DB_USER="backup_user"
DB_PASS="Backup@2025!Secure"
DB_HOST="10.10.10.20"
DB_PORT=3306
RETENTION_DAYS=7

# 检查是否为周日，周日不执行增量备份
if [ $(date +%u) -eq 7 ]; then
    echo "[$(date +%Y-%m-%d %H:%M:%S)] 周日跳过增量备份"
    exit 0
fi

# 创建备份目录
mkdir -p ${BACKUP_DIR}/${DATE}

# 执行增量备份（基于二进制日志）
mysqlbinlog --read-from-remote-server --host=${DB_HOST} --port=${DB_PORT} \
  --user=${DB_USER} --password=${DB_PASS} \
  --raw --result-file=${BACKUP_DIR}/${DATE}/ \
  --stop-never-slave-server-id=9999 \
  --to-last-log

# 压缩备份文件
cd ${BACKUP_DIR}/${DATE}
tar -czf incremental_backup_${DATE}.tar.gz *.binlog
rm -f *.binlog

# 记录备份元数据
echo "backup_time=$(date +%s),backup_type=incremental,size=$(du -sh ${BACKUP_DIR}/${DATE}/incremental_backup_${DATE}.tar.gz | cut -f1)" >> ${BACKUP_DIR}/backup_metadata.log

# 清理过期备份
find ${BACKUP_DIR} -type d -mtime +${RETENTION_DAYS} -exec rm -rf {} \;
```

### 3.3 应用文件备份

**应用配置备份脚本** `/usr/local/bin/app_config_backup.sh`：

```bash
#!/bin/bash
# 应用配置备份 - 每次变更后手动执行
BACKUP_DIR="/backup/config"
DATE=$(date +%Y%m%d_%H%M%S)
CONFIG_DIRS=(
    "/etc/nginx"
    "/etc/redis"
    "/etc/mysql"
    "/opt/acmecloud/config"
    "/etc/systemd/system"
)
RETENTION_DAYS=180

# 创建备份目录
mkdir -p ${BACKUP_DIR}/${DATE}

# 打包配置文件
tar -czf ${BACKUP_DIR}/${DATE}/config_backup_${DATE}.tar.gz ${CONFIG_DIRS[@]}

# 记录配置版本
md5sum ${BACKUP_DIR}/${DATE}/config_backup_${DATE}.tar.gz > ${BACKUP_DIR}/${DATE}/config_backup_${DATE}.md5

# 清理过期备份
find ${BACKUP_DIR} -type d -mtime +${RETENTION_DAYS} -exec rm -rf {} \;
```

### 3.4 Cron表达式配置

```cron
# 数据库全量备份 - 每周日02:00
0 2 * * 0 /usr/local/bin/mysql_full_backup.sh

# 数据库增量备份 - 每天02:00（周日除外）
0 2 * * 1-6 /usr/local/bin/mysql_incremental_backup.sh

# 应用日志备份 - 每天04:00
0 4 * * * /usr/local/bin/log_backup.sh

# 系统配置备份 - 每天03:00
0 3 * * * /usr/local/bin/system_config_backup.sh

# 备份完整性检查 - 每天06:00
0 6 * * * /usr/local/bin/backup_verify.sh
```

### 3.5 备份恢复验证

**月度恢复演练**（每月第一个周六）：

```bash
#!/bin/bash
# 恢复演练脚本 - 在测试环境执行
TEST_DB_HOST="10.10.10.30"
TEST_DB_PORT=3306
TEST_DB_USER="test_user"
TEST_DB_PASS="Test@2025!Restore"
BACKUP_FILE="/backup/full/20250301_020000/full_backup.sql.gz"

# 1. 创建测试数据库
mysql -h ${TEST_DB_HOST} -P ${TEST_DB_PORT} -u ${TEST_DB_USER} -p${TEST_DB_PASS} -e "CREATE DATABASE IF NOT EXISTS restore_test;"

# 2. 恢复数据
gunzip < ${BACKUP_FILE} | mysql -h ${TEST_DB_HOST} -P ${TEST_DB_PORT} -u ${TEST_DB_USER} -p${TEST_DB_PASS} restore_test

# 3. 验证数据完整性
TABLE_COUNT=$(mysql -h ${TEST_DB_HOST} -P ${TEST_DB_PORT} -u ${TEST_DB_USER} -p${TEST_DB_PASS} -e "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='restore_test';" | tail -1)
echo "恢复的表数量: ${TABLE_COUNT}"

# 4. 清理测试数据
mysql -h ${TEST_DB_HOST} -P ${TEST_DB_PORT} -u ${TEST_DB_USER} -p${TEST_DB_PASS} -e "DROP DATABASE restore_test;"
```

### 3.6 备份存储架构

```
/backup/
├── full/                    # 全量备份（保留30天）
│   ├── 20250301_020000/
│   │   ├── full_backup.sql.gz
│   │   └── backup_metadata.log
│   └── 20250308_020000/
├── incremental/             # 增量备份（保留7天）
│   ├── 20250309_020000/
│   │   └── incremental_backup_20250309_020000.tar.gz
│   └── 20250310_020000/
├── logs/                    # 日志备份（保留90天）
│   ├── 20250301/
│   └── 20250302/
├── config/                  # 配置备份（保留180天）
│   ├── 20250301_143000/
│   │   ├── config_backup_20250301_143000.tar.gz
│   │   └── config_backup_20250301_143000.md5
│   └── 20250302_093000/
└── backup_metadata.log      # 备份元数据日志
```

---

## 第4章 常见故障处理

### 4.1 故障处理流程

```
故障发现 → 故障确认 → 故障定级 → 故障处理 → 故障恢复 → 复盘总结
   |           |           |           |           |           |
  告警/用户   人工确认    P0-P3      执行预案   验证恢复   根因分析
```

**故障等级定义**：

| 等级 | 定义 | 响应时间 | 恢复时间 | 通知对象 |
|------|------|----------|----------|----------|
| P0 | 核心业务完全不可用 | 5分钟 | 30分钟 | 运维总监+CTO |
| P1 | 核心业务部分不可用 | 15分钟 | 60分钟 | 运维经理 |
| P2 | 非核心业务受影响 | 30分钟 | 120分钟 | 值班运维 |
| P3 | 轻微影响或咨询 | 60分钟 | 240分钟 | 运维团队 |

### 4.2 故障场景1：数据库连接失败

**错误码**：DB-ERR-1001  
**错误信息**：`ERROR 2003 (HY000): Can't connect to MySQL server on '10.10.10.20:3306'`

**可能原因**：
1. MySQL服务未启动（概率40%）
2. 防火墙阻止3306端口（概率25%）
3. 连接数达到上限（max_connections=500）（概率20%）
4. 网络故障（概率15%）

**解决步骤**：

```bash
# 步骤1：检查MySQL服务状态
systemctl status mysqld
# 预期输出：active (running)

# 步骤2：如果服务未运行，启动服务
systemctl start mysqld
# 等待30秒后检查状态

# 步骤3：检查端口监听
netstat -tlnp | grep 3306
# 预期输出：tcp 0 0 0.0.0.0:3306 0.0.0.0:* LISTEN 12345/mysqld

# 步骤4：检查防火墙规则
iptables -L -n | grep 3306
# 如果被阻止，添加规则
iptables -A INPUT -p tcp --dport 3306 -j ACCEPT
# 保存规则
service iptables save

# 步骤5：检查连接数
mysql -u root -p -e "SHOW VARIABLES LIKE 'max_connections';"
mysql -u root -p -e "SHOW STATUS LIKE 'Threads_connected';"
# 如果连接数接近上限，临时增加
mysql -u root -p -e "SET GLOBAL max_connections=1000;"
# 永久修改配置文件 /etc/my.cnf
# [mysqld]
# max_connections=1000

# 步骤6：检查网络连通性
ping -c 4 10.10.10.20
telnet 10.10.10.20 3306
```

### 4.3 故障场景2：磁盘空间不足

**错误码**：DISK-ERR-2001  
**错误信息**：`No space left on device` 或 `Disk quota exceeded`

**可能原因**：
1. 日志文件过大（概率45%）
2. 临时文件未清理（概率30%）
3. 备份文件堆积（概率15%）
4. 应用数据异常增长（概率10%）

**解决步骤**：

```bash
# 步骤1：查看磁盘使用情况
df -h
# 重点关注 /、/var、/data 分区

# 步骤2：查找大文件
du -sh /* 2>/dev/null | sort -rh | head -10
du -sh /var/* 2>/dev/null | sort -rh | head -10

# 步骤3：清理日志文件
# 清理超过7天的日志
find /var/log -name "*.log" -mtime +7 -exec rm -f {} \;
# 清理应用日志
find /opt/acmecloud/logs -name "*.log" -mtime +7 -exec rm -f {} \;

# 步骤4：清理临时文件
rm -rf /tmp/*
rm -rf /var/tmp/*

# 步骤5：清理旧的备份文件
find /backup -type f -mtime +30 -exec rm -f {} \;

# 步骤6：清理Docker无用数据（如果使用Docker）
docker system prune -af --volumes

# 步骤7：如果仍然不足，考虑扩容
# 查看磁盘类型
lsblk
# 扩展逻辑卷（LVM示例）
lvextend -L +50G /dev/mapper/vg_data-lv_data
resize2fs /dev/mapper/vg_data-lv_data
```

### 4.4 故障场景3：应用服务无响应

**错误码**：APP-ERR-3001  
**错误信息**：`HTTP 502 Bad Gateway` 或 `HTTP 504 Gateway Timeout`

**可能原因**：
1. 后端服务崩溃（概率35%）
2. 数据库连接池耗尽（概率25%）
3. 内存溢出（OOM）（概率20%）
4. 线程池耗尽（概率20%）

**解决步骤**：

```bash
# 步骤1：检查应用进程
ps aux | grep acmecloud
# 检查进程数量是否正常

# 步骤2：查看应用日志
tail -200 /opt/acmecloud/logs/app.log
grep -i "error\|exception\|OOM" /opt/acmecloud/logs/app.log | tail -50

# 步骤3：检查JVM状态（Java应用）
jps -l
jstack <PID> > /tmp/thread_dump.txt
jmap -heap <PID>
# 检查堆内存使用情况

# 步骤4：重启应用服务
systemctl restart acmecloud.service
# 等待30秒后检查状态
systemctl status acmecloud.service

# 步骤5：如果频繁重启，检查资源限制
ulimit -a
# 检查 open files、max user processes 等参数

# 步骤6：调整JVM参数（如果必要）
# 编辑 /opt/acmecloud/bin/start.sh
# JAVA_OPTS="-Xms4g -Xmx8g -XX:MaxMetaspaceSize=512m"
```

### 4.5 故障场景4：Redis缓存故障

**错误码**：CACHE-ERR-4001  
**错误信息**：`Redis connection refused` 或 `OOM command not allowed when used memory > 'maxmemory'`

**可能原因**：
1. Redis服务未启动（概率30%）
2. 内存使用超过maxmemory（概率35%）
3. 连接数达到上限（概率20%）
4. 持久化文件损坏（概率15%）

**解决步骤**：

```bash
# 步骤1：检查Redis服务
systemctl status redis
redis-cli -h 10.10.10.21 -p 6379 ping
# 预期返回：PONG

# 步骤2：检查内存使用
redis-cli -h 10.10.10.21 -p 6379 INFO memory
# 关注 used_memory_human 和 maxmemory_human

# 步骤3：如果内存不足，清理缓存
redis-cli -h 10.10.10.21 -p 6379 FLUSHDB
# 或者选择性删除
redis-cli -h 10.10.10.21 -p 6379 --eval /tmp/delete_keys.lua

# 步骤4：检查连接数
redis-cli -h 10.10.10.21 -p 6379 CLIENT LIST | wc -l
# 如果超过maxclients（默认10000），临时增加
redis-cli -h 10.10.10.21 -p 6379 CONFIG SET maxclients 20000

# 步骤5：检查持久化文件
ls -lh /var/lib/redis/dump.rdb
# 如果文件损坏，删除后重启
rm -f /var/lib/redis/dump.rdb
systemctl restart redis

# 步骤6：配置优化（/etc/redis.conf）
# maxmemory 8gb
# maxmemory-policy allkeys-lru
# timeout 300
```

### 4.6 故障场景5：Nginx负载均衡故障

**错误码**：LB-ERR-5001  
**错误信息**：`HTTP 503 Service Unavailable` 或 `upstream timed out`

**可能原因**：
1. 后端服务器全部宕机（概率40%）
2. Nginx配置错误（概率25%）
3. 健康检查失败（概率20%）
4. SSL证书过期（概率15%）

**解决步骤**：

```bash
# 步骤1：检查Nginx状态
systemctl status nginx
nginx -t
# 检查配置语法

# 步骤2：检查后端服务器
curl -I http://10.10.10.10:8080/health
curl -I http://10.10.10.11:8080/health
# 检查所有后端节点

# 步骤3：查看Nginx日志
tail -100 /var/log/nginx/error.log
tail -100 /var/log/nginx/access.log

# 步骤4：检查upstream配置
cat /etc/nginx/conf.d/upstream.conf
# 确保所有后端服务器配置正确

# 步骤5：重新加载配置
nginx -s reload

# 步骤6：如果SSL证书过期
openssl x509 -in /etc/nginx/ssl/acmecloud.crt -noout -dates
# 更新证书后重载
nginx -s reload
```

### 4.7 故障场景6：网络连接异常

**错误码**：NET-ERR-6001  
**错误信息**：`Connection timed out` 或 `Network is unreachable`

**可能原因**：
1. 物理链路故障（概率30%）
2. DNS解析失败（概率25%）
3. 路由配置错误（概率20%）
4. 防火墙规则变更（概率25%）

**解决步骤**：

```bash
# 步骤1：检查网络连通性
ping -c 4 8.8.8.8
ping -c 4 10.10.10.1

# 步骤2：检查DNS解析
nslookup acmecloud.com
dig acmecloud.com

# 步骤3：检查路由表
route -n
ip route show

# 步骤4：检查网卡状态
ip link show
ethtool eth0

# 步骤5：检查防火墙规则
iptables -L -n -v
# 检查是否有异常规则

# 步骤6：重启网络服务
systemctl restart network
# 或者
ifdown eth0 && ifup eth0
```

### 4.8 故障场景7：消息队列积压

**错误码**：MQ-ERR-7001  
**错误信息**：`Queue depth exceeds threshold` 或 `Consumer lag too high`

**可能原因**：
1. 消费者处理速度慢（概率40%）
2. 生产者发送速度过快（概率30%）
3. 消费者宕机（概率20%）
4. 消息持久化失败（概率10%）

**解决步骤**：

```bash
# 步骤1：检查队列状态（RabbitMQ示例）
rabbitmqctl list_queues name messages messages_ready messages_unacknowledged
# 关注 messages 数量是否持续增长

# 步骤2：检查消费者状态
rabbitmqctl list_consumers

# 步骤3：检查消费者日志
tail -100 /opt/acmecloud/logs/consumer.log

# 步骤4：增加消费者数量
# 修改消费者配置，增加并发数
# 例如：spring.rabbitmq.listener.simple.concurrency=10

# 步骤5：重启消费者服务
systemctl restart acmecloud-consumer.service

# 步骤6：如果积压严重，手动清理队列
rabbitmqctl purge_queue queue_name
# 注意：会丢失所有未消费消息
```

### 4.9 故障场景8：SSL证书过期

**错误码**：SSL-ERR-8001  
**错误信息**：`SSL certificate expired` 或 `certificate has expired`

**可能原因**：
1. 证书未及时续期（概率70%）
2. 自动续期脚本失败（概率20%）
3. 证书链不完整（概率10%）

**解决步骤**：

```bash
# 步骤1：检查证书有效期
openssl x509 -in /etc/nginx/ssl/acmecloud.crt -noout -dates
# 输出示例：notBefore=Mar 15 00:00:00 2024 GMT
#          notAfter=Mar 14 23:59:59 2025 GMT

# 步骤2：检查证书链
openssl verify -CAfile /etc/nginx/ssl/ca.crt /etc/nginx/ssl/acmecloud.crt

# 步骤3：生成新的证书（使用Let's Encrypt）
certbot renew --dry-run
# 实际续期
certbot renew

# 步骤4：手动申请新证书
# 生成CSR
openssl req -new -key /etc/nginx/ssl/acmecloud.key -out /tmp/acmecloud.csr
# 提交到CA获取新证书

# 步骤5：更新证书文件
cp /path/to/new/certificate.crt /etc/nginx/ssl/acmecloud.crt
cp /path/to/new/private.key /etc/nginx/ssl/acmecloud.key

# 步骤6：重载Nginx
nginx -s reload

# 步骤7：验证新证书
curl -I https://acmecloud.com
```

---

## 第5章 监控告警配置

### 5.1 监控架构

```
数据采集层 → 数据存储层 → 告警引擎 → 通知渠道
   |             |             |           |
Prometheus    InfluxDB    Alertmanager   Email/SMS/Webhook
Node Exporter  (保留30天)   (规则引擎)    (企业微信/钉钉)
```

### 5.2 关键告警规则（5个）

#### 规则1：CPU使用率过高

```yaml
# alert_rules.yml
groups:
  - name: system_alerts
    rules:
      - alert: HighCPUUsage
        expr: 100 - (avg by(instance) (rate(node_cpu_seconds_total{mode="idle"}[5m])) * 100) > 80
        for: 5m
        labels:
          severity: critical
          team: ops
        annotations:
          summary: "{{ $labels.instance }} CPU使用率超过80%"
          description: "CPU使用率当前值: {{ $value }}% (阈值: 80%)"
          runbook_url: "https://wiki.acmecloud.com/runbooks/high-cpu-usage"
```

**参数说明**：
- 阈值：80%
- 持续时间：5分钟
- 级别：Critical（P1）
- 检查频率：15秒
- 通知方式：企业微信 + 短信

#### 规则2：内存使用率过高

```yaml
      - alert: HighMemoryUsage
        expr: (1 - (node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes)) * 100 > 85
        for: 5m
        labels:
          severity: critical
          team: ops
        annotations:
          summary: "{{ $labels.instance }} 内存使用率超过85%"
          description: "内存使用率当前值: {{ $value }}% (阈值: 85%)"
```

**参数说明**：
- 阈值：85%
- 持续时间：5分钟
- 级别：Critical（P1）
- 检查频率：15秒

#### 规则3：磁盘使用率过高

```yaml
      - alert: HighDiskUsage
        expr: (node_filesystem_size_bytes{mountpoint="/data"} - node_filesystem_free_bytes{mountpoint="/data"}) / node_filesystem_size_bytes{mountpoint="/data"} * 100 > 80
        for: 10m
        labels:
          severity: warning
          team: ops
        annotations:
          summary: "{{ $labels.instance }} 磁盘使用率超过80%"
          description: "磁盘使用率当前值: {{ $value }}% (阈值: 80%)"
```

**参数说明**：
- 阈值：80%（Warning），90%（Critical）
- 持续时间：10分钟
- 级别：Warning（P2）
- 检查频率：30秒

#### 规则4：应用响应时间过长

```yaml
      - alert: HighResponseTime
        expr: histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m])) > 1
        for: 3m
        labels:
          severity: critical
          team: app
        annotations:
          summary: "{{ $labels.instance }} P95响应时间超过1秒"
          description: "P95响应时间当前值: {{ $value }}s (阈值: 1s)"
```

**参数说明**：
- 阈值：1秒（P95）
- 持续时间：3分钟
- 级别：Critical（P1）
- 检查频率：15秒

#### 规则5：服务不可用

```yaml
      - alert: ServiceDown
        expr: up{job="acmecloud"} == 0
        for: 1m
        labels:
          severity: critical
          team: ops
        annotations:
          summary: "{{ $labels.instance }} 服务不可用"
          description: "服务 {{ $labels.job }} 已宕机超过1分钟"
```

**参数说明**：
- 阈值：0（不可用）
- 持续时间：1分钟
- 级别：Critical（P0）
- 检查频率：10秒
- 通知方式：电话 + 短信 + 企业微信

### 5.3 告警通知配置

```yaml
# alertmanager.yml
route:
  receiver: 'default'
  routes:
    - match:
        severity: critical
      receiver: 'critical-team'
      repeat_interval: 5m
    - match:
        severity: warning
      receiver: 'warning-team'
      repeat_interval: 30m

receivers:
  - name: 'critical-team'
    webhook_configs:
      - url: 'https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxxx-xxxx-xxxx'
        send_resolved: true
    email_configs:
      - to: 'ops-critical@acmecloud.com'
        from: 'alert@acmecloud.com'
        smarthost: 'smtp.acmecloud.com:587'
        auth_username: 'alert@acmecloud.com'
        auth_password: 'Alert@2025!Email'
    pagerduty_configs:
      - routing_key: 'xxxxxxxxxxxxxxxxxxxx'

  - name: 'warning-team'
    webhook_configs:
      - url: 'https://qyapi.weixin.qq.com/cgi-bin/webhook/send?