# 云端生产部署步骤 (供AI执行)

## 前置条件

- 一台 Linux 服务器 (Ubuntu 22.04 推荐)
- 公网 IP
- SSH 访问权限

---

## 步骤 1: 安装 Docker

```bash
# 更新系统
sudo apt update && sudo apt upgrade -y

# 安装 Docker
curl -fsSL https://get.docker.com | sudo sh

# 添加当前用户到 docker 组
sudo usermod -aG docker $USER

# 启动 Docker
sudo systemctl enable docker
sudo systemctl start docker

# 安装 Docker Compose 插件
sudo apt install docker-compose-plugin -y

# 验证安装
docker --version
docker compose version
```

---

## 步骤 2: 上传项目代码

**方式 A: Git 克隆**
```bash
cd /opt
sudo git clone <repository-url> shield-tunneling
cd shield-tunneling
sudo chown -R $USER:$USER .
```

**方式 B: SCP 上传**
```bash
# 在本地执行
scp -r /path/to/shield-tunneling-icp-backup user@<server-ip>:/opt/shield-tunneling
```

---

## 步骤 3: 配置环境变量

```bash
cd /opt/shield-tunneling

# 复制模板
cp .env.cloud.example .env.cloud

# 生成随机密码
POSTGRES_PASS=$(openssl rand -base64 16 | tr -d '/+=' | head -c 20)
REDIS_PASS=$(openssl rand -base64 16 | tr -d '/+=' | head -c 20)
MINIO_PASS=$(openssl rand -base64 16 | tr -d '/+=' | head -c 20)
API_KEY=$(openssl rand -base64 32 | tr -d '/+=' | head -c 40)
AIRFLOW_KEY=$(openssl rand -base64 32 | tr -d '/+=' | head -c 40)

# 替换配置文件中的占位符
sed -i "s/change_this_password_to_secure_one/$POSTGRES_PASS/g" .env.cloud
sed -i "s/REDIS_PASSWORD=.*/REDIS_PASSWORD=$REDIS_PASS/" .env.cloud
sed -i "s/MINIO_ROOT_PASSWORD=.*/MINIO_ROOT_PASSWORD=$MINIO_PASS/" .env.cloud
sed -i "s/generate_a_long_random_secret_key_here_at_least_32_chars/$API_KEY/" .env.cloud
sed -i "s/generate_another_secret_key_here/$AIRFLOW_KEY/" .env.cloud

# 输出密码供记录
echo "=== 生成的密码 ==="
echo "PostgreSQL: $POSTGRES_PASS"
echo "Redis: $REDIS_PASS"
echo "MinIO: $MINIO_PASS"
echo "API Key: $API_KEY"
```

---

## 步骤 4: 启动服务

```bash
cd /opt/shield-tunneling

# 启动所有服务
docker compose -f docker-compose.cloud.yml up -d

# 等待服务启动
sleep 30

# 检查服务状态
docker compose -f docker-compose.cloud.yml ps
```

**预期输出:** 所有服务状态应为 `running` 或 `healthy`

---

## 步骤 5: 初始化 MinIO Buckets

```bash
# 等待 MinIO 完全启动
sleep 10

# 获取 MinIO 密码
source .env.cloud

# 进入 MinIO 容器创建 buckets
docker exec shield-minio mc alias set local http://localhost:9000 $MINIO_ROOT_USER $MINIO_ROOT_PASSWORD

docker exec shield-minio mc mb local/mlflow --ignore-existing
docker exec shield-minio mc mb local/models --ignore-existing

# 验证
docker exec shield-minio mc ls local/
```

---

## 步骤 6: 初始化 Airflow

```bash
# 等待 Airflow 数据库就绪
sleep 20

# 创建管理员用户
docker exec shield-airflow-webserver airflow users create \
    --username admin \
    --password admin123 \
    --firstname Admin \
    --lastname User \
    --role Admin \
    --email admin@shield.local

# 验证
docker exec shield-airflow-webserver airflow users list
```

---

## 步骤 7: 验证服务

```bash
# 检查 Cloud API
curl http://localhost:8001/health

# 检查 MLflow
curl http://localhost:5000/health

# 检查所有服务端口
netstat -tlnp | grep -E '5000|8001|8080|9001'
```

**预期结果:**
- 8001 端口: Cloud API
- 5000 端口: MLflow
- 8080 端口: Airflow
- 9001 端口: MinIO Console

---

## 步骤 8: 配置防火墙 (可选)

```bash
# Ubuntu UFW
sudo ufw allow 22/tcp    # SSH
sudo ufw allow 8001/tcp  # Cloud API (供边缘设备访问)
sudo ufw enable
```

**云服务商安全组规则:**

| 端口 | 协议 | 来源 | 用途 |
|------|------|------|------|
| 22 | TCP | 管理员IP | SSH |
| 8001 | TCP | 边缘设备IP/0.0.0.0 | Cloud API |
| 5000 | TCP | 管理员IP | MLflow UI |
| 8080 | TCP | 管理员IP | Airflow UI |
| 9001 | TCP | 管理员IP | MinIO Console |

---

## 步骤 9: 配置边缘设备连接

在边缘设备上修改环境变量:

```bash
# 边缘设备 .env 文件
CLOUD_API_URL=http://<云端公网IP>:8001

# 如果有 API Key 认证
CLOUD_SYNC_API_KEY=<步骤3生成的API_KEY>
```

---

## 常用运维命令

```bash
# 查看日志
docker compose -f docker-compose.cloud.yml logs -f

# 查看特定服务日志
docker compose -f docker-compose.cloud.yml logs -f cloud-api

# 重启服务
docker compose -f docker-compose.cloud.yml restart cloud-api

# 停止所有服务
docker compose -f docker-compose.cloud.yml down

# 更新代码后重建
git pull
docker compose -f docker-compose.cloud.yml up -d --build

# 备份数据库
docker exec shield-timescaledb pg_dump -U shield shield_cloud > backup_$(date +%Y%m%d).sql
```

---

## 服务访问地址

| 服务 | URL | 默认账号 |
|------|-----|---------|
| Cloud API | http://<IP>:8001/docs | 无需登录 |
| MLflow | http://<IP>:5000 | 无需登录 |
| Airflow | http://<IP>:8080 | admin / admin123 |
| MinIO | http://<IP>:9001 | minioadmin / <MINIO_PASS> |

---

## 故障排查

**服务未启动:**
```bash
docker compose -f docker-compose.cloud.yml logs <service-name>
```

**端口被占用:**
```bash
sudo lsof -i :<port>
sudo kill -9 <PID>
```

**数据库连接失败:**
```bash
docker exec shield-cloud-api ping timescaledb
docker exec shield-timescaledb psql -U shield -d shield_cloud -c "SELECT 1"
```
