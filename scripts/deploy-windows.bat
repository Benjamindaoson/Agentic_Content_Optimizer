@echo off
echo ========================================
echo   Growth Flywheel v4.0 一键部署
echo ========================================
echo.

REM 检查 Docker Desktop 是否运行
docker ps >nul 2>&1
if %errorlevel% neq 0 (
    echo [错误] Docker Desktop 未运行
    echo.
    echo 请先启动 Docker Desktop，然后重新运行此脚本
    echo.
    pause
    exit /b 1
)

echo [1/9] Docker Desktop 运行正常
echo.

REM 检查 .env 文件
if not exist .env (
    echo [错误] .env 文件不存在
    echo 请先配置 .env 文件中的 API Keys
    pause
    exit /b 1
)

echo [2/9] 配置文件检查完成
echo.

REM 创建必要目录
if not exist logs mkdir logs
if not exist monitoring\grafana\dashboards mkdir monitoring\grafana\dashboards
if not exist monitoring\grafana\datasources mkdir monitoring\grafana\datasources
if not exist scripts mkdir scripts

echo [3/9] 目录创建完成
echo.

echo [4/9] 拉取 Docker 镜像...
docker-compose -f docker-compose.v4.yml pull postgres redis qdrant minio prometheus grafana
if %errorlevel% neq 0 (
    echo [错误] 镜像拉取失败
    pause
    exit /b 1
)
echo.

echo [5/9] 构建应用镜像...
docker-compose -f docker-compose.v4.yml build api celery-worker celery-beat
if %errorlevel% neq 0 (
    echo [错误] 应用构建失败
    pause
    exit /b 1
)
echo.

echo [6/9] 启动服务...
docker-compose -f docker-compose.v4.yml up -d postgres redis qdrant minio api celery-worker celery-beat prometheus grafana
if %errorlevel% neq 0 (
    echo [错误] 服务启动失败
    pause
    exit /b 1
)
echo.

echo [7/9] 等待数据库启动...
timeout /t 15 /nobreak >nul
echo.

echo [8/9] 运行数据库迁移...
docker-compose -f docker-compose.v4.yml exec -T api alembic upgrade head
if %errorlevel% neq 0 (
    echo [警告] 数据库迁移可能失败，请检查日志
)
echo.

echo [9/9] 初始化存储...
docker-compose -f docker-compose.v4.yml exec -T minio mc alias set local http://localhost:9000 minioadmin MinIO2025!Secure 2>nul
docker-compose -f docker-compose.v4.yml exec -T minio mc mb local/covers 2>nul
docker-compose -f docker-compose.v4.yml exec -T minio mc mb local/videos 2>nul
docker-compose -f docker-compose.v4.yml exec -T minio mc mb local/exports 2>nul
echo.

echo ========================================
echo   部署完成！
echo ========================================
echo.
echo 服务访问地址：
echo   - API 文档: http://localhost:8080/docs
echo   - 健康检查: http://localhost:8080/health
echo   - Grafana: http://localhost:3000
echo   - Prometheus: http://localhost:9090
echo   - MinIO: http://localhost:9001
echo   - Qdrant: http://localhost:6333/dashboard
echo.
echo 查看日志：
echo   docker-compose -f docker-compose.v4.yml logs -f
echo.
echo 停止服务：
echo   docker-compose -f docker-compose.v4.yml down
echo.
pause
