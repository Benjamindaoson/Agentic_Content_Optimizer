#!/bin/bash
# MinIO 安全配置脚本

set -e

echo "等待 MinIO 启动..."
sleep 5

# 配置 mc 客户端
mc alias set myminio http://minio:9000 ${MINIO_ROOT_USER} ${MINIO_ROOT_PASSWORD}

echo "创建存储桶..."
mc mb myminio/covers --ignore-existing
mc mb myminio/videos --ignore-existing
mc mb myminio/exports --ignore-existing
mc mb myminio/temp --ignore-existing

echo "配置存储桶策略 - 私有访问..."
# 设置为私有,只允许认证访问
mc anonymous set none myminio/covers
mc anonymous set none myminio/videos
mc anonymous set none myminio/exports
mc anonymous set none myminio/temp

echo "创建应用专用访问密钥..."
# 创建只读策略
cat > /tmp/readonly-policy.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:ListBucket"
      ],
      "Resource": [
        "arn:aws:s3:::covers/*",
        "arn:aws:s3:::covers",
        "arn:aws:s3:::videos/*",
        "arn:aws:s3:::videos"
      ]
    }
  ]
}
EOF

# 创建读写策略
cat > /tmp/readwrite-policy.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:*"
      ],
      "Resource": [
        "arn:aws:s3:::covers/*",
        "arn:aws:s3:::covers",
        "arn:aws:s3:::videos/*",
        "arn:aws:s3:::videos",
        "arn:aws:s3:::exports/*",
        "arn:aws:s3:::exports",
        "arn:aws:s3:::temp/*",
        "arn:aws:s3:::temp"
      ]
    }
  ]
}
EOF

# 创建策略
mc admin policy create myminio readonly /tmp/readonly-policy.json || true
mc admin policy create myminio readwrite /tmp/readwrite-policy.json || true

# 创建应用用户
mc admin user add myminio growth-app ${MINIO_APP_SECRET_KEY} || true
mc admin policy attach myminio readwrite --user growth-app

echo "配置版本控制..."
mc version enable myminio/covers
mc version enable myminio/videos

echo "配置生命周期策略 - 临时文件自动清理..."
cat > /tmp/lifecycle.json <<EOF
{
  "Rules": [
    {
      "ID": "DeleteTempAfter7Days",
      "Status": "Enabled",
      "Filter": {
        "Prefix": ""
      },
      "Expiration": {
        "Days": 7
      }
    }
  ]
}
EOF
mc ilm import myminio/temp < /tmp/lifecycle.json

echo "✓ MinIO 安全配置完成"
echo "应用访问密钥: growth-app"
echo "请将以下配置添加到 .env:"
echo "MINIO_ACCESS_KEY=growth-app"
echo "MINIO_SECRET_KEY=${MINIO_APP_SECRET_KEY}"
