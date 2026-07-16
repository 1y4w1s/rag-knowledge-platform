# 睿阁 Postgres + pgvector（自建，避免 pgvector/pgvector 镜像在国内难拉）
# 基础镜像是常用的 postgres:16-bookworm；pgvector 用 apt 安装（国内走清华 Debian 源）
FROM postgres:16-bookworm

RUN set -eux; \
    if [ -f /etc/apt/sources.list.d/debian.sources ]; then \
      sed -i 's/deb.debian.org/mirrors.tuna.tsinghua.edu.cn/g' /etc/apt/sources.list.d/debian.sources; \
    fi; \
    apt-get update; \
    apt-get install -y --no-install-recommends postgresql-16-pgvector; \
    rm -rf /var/lib/apt/lists/*

COPY init/ /docker-entrypoint-initdb.d/
