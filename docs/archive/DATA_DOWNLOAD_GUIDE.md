# 快速开始 - 数据下载和预处理

## 重要说明

**数据保存位置**: `D:\SalesBoost\data\`
- 原始数据: `D:\SalesBoost\data\raw\`
- 处理后数据: `D:\SalesBoost\data\processed\`

## 方法 1: 一键下载 (推荐)

```bash
cd growth-flywheel-2.5
download_data.bat
```

这个脚本会自动:
1. ✅ 创建数据目录 `D:\SalesBoost\data`
2. ✅ 安装必要的包 (requests, tqdm)
3. ✅ 下载 TikTok-10M 数据 (1 万条测试数据)
4. ✅ 预处理数据并计算奖励值

**预期时间**: 5-10 分钟

## 方法 2: 手动执行

### 步骤 1: 安装依赖

```bash
pip install requests tqdm
```

只需要这两个轻量级的包，无需安装 PyTorch、Transformers 等大型库。

### 步骤 2: 下载 TikTok-10M 数据

```bash
python backend/scripts/download_tiktok_api.py
```

**特点**:
- ✅ 无需安装 `datasets` 库
- ✅ 直接通过 HTTP API 获取数据
- ✅ 支持断点续传
- ✅ 自动保存进度
- ✅ 数据保存到 `D:\SalesBoost\data\raw\`

**参数说明**:
- `batch_size=100`: 每次请求 100 条数据
- `max_samples=10000`: 下载 1 万条数据（测试用）
- 如需下载完整数据集（1000 万条），修改 `max_samples=10000000`

**预期时间**:
- 1 万条: ~5-10 分钟
- 10 万条: ~30-60 分钟
- 100 万条: ~5-8 小时
- 1000 万条: ~50-80 小时

### 步骤 3: 数据预处理

```bash
python backend/scripts/preprocess_tiktok.py
```

这个脚本会:
1. 按作者分组数据
2. 计算每个作者的 baseline (最近 10 条帖子的中位数点赞数)
3. 计算相对增益: `(likes - baseline) / baseline`
4. 计算调整后的奖励: `relative_gain * log(1 + play_count)`

**输出**:
- 处理后的数据: `D:\SalesBoost\data\processed\tiktok-10m-processed.jsonl`
- 包含字段: `baseline_likes`, `relative_gain`, `adjusted_reward`

## 步骤 4: 查看数据

```bash
# 查看前 5 条数据
head -n 5 D:\SalesBoost\data\processed\tiktok-10m-processed.jsonl

# 或使用 Python
python -c "
import json
with open('D:/SalesBoost/data/processed/tiktok-10m-processed.jsonl', 'r', encoding='utf-8') as f:
    for i, line in enumerate(f):
        if i >= 5:
            break
        data = json.loads(line)
        print(f'Record {i+1}:')
        print(f'  Description: {data.get(\"desc\", \"N/A\")[:100]}')
        print(f'  Likes: {data.get(\"digg_count\", 0)}')
        print(f'  Baseline: {data.get(\"baseline_likes\", 0):.2f}')
        print(f'  Reward: {data.get(\"adjusted_reward\", 0):.4f}')
        print()
"
```

## API 使用示例

### 直接使用 curl 测试

```bash
curl -X GET \
  "https://datasets-server.huggingface.co/rows?dataset=The-data-company%2FTikTok-10M&config=default&split=train&offset=0&length=100"
```

### Python 代码示例

```python
import requests
import json

# 获取前 100 条数据
url = "https://datasets-server.huggingface.co/rows"
params = {
    "dataset": "The-data-company/TikTok-10M",
    "config": "default",
    "split": "train",
    "offset": 0,
    "length": 100
}

response = requests.get(url, params=params)
data = response.json()

# 查看数据
for row in data["rows"][:5]:
    record = row["row"]
    print(f"Description: {record.get('desc', 'N/A')}")
    print(f"Likes: {record.get('digg_count', 0)}")
    print(f"Views: {record.get('play_count', 0)}")
    print("-" * 50)
```

## 数据字段说明

每条记录包含以下字段:

### 原始字段
- `id`: 视频 ID
- `desc`: 视频描述文案
- `digg_count`: 点赞数
- `play_count`: 播放数
- `comment_count`: 评论数
- `share_count`: 分享数
- `author_id`: 作者 ID
- `create_time`: 创建时间
- `music_name`: 音乐名称
- `hashtags`: 话题标签

### 预处理后新增字段
- `baseline_likes`: 该作者最近 10 条帖子的中位数点赞数
- `relative_gain`: 相对增益 = (likes - baseline) / baseline
- `adjusted_reward`: 调整后的奖励 = relative_gain * log(1 + play_count)

## 常见问题

### Q1: 下载速度慢怎么办?

**A**:
- 减小 `batch_size` (如改为 50)
- 增加请求间隔 `time.sleep(0.5)`
- 使用代理或 VPN

### Q2: 下载中断怎么办?

**A**:
脚本支持断点续传，只需重新运行即可从上次中断的地方继续。

### Q3: 内存不足怎么办?

**A**:
- 减小 `save_every` 参数，更频繁地保存数据
- 分批下载，每次下载 1 万条

### Q4: 如何下载完整的 1000 万条数据?

**A**:
修改 `download_tiktok_api.py` 中的参数:
```python
output_file = downloader.download_tiktok_10m(
    batch_size=100,
    max_samples=10000000,  # 改为 1000 万
    save_every=10000       # 每 1 万条保存一次
)
```

## 数据目录结构

```
D:\SalesBoost\
└── data\
    ├── raw\
    │   └── tiktok-10m-sample.jsonl      (原始下载数据)
    └── processed\
        └── tiktok-10m-processed.jsonl   (预处理后的数据)
```

## 下一步

数据准备完成后:

1. **启动后端服务**:
   ```bash
   cd backend
   uvicorn app.main:app --reload
   ```

2. **启动前端服务**:
   ```bash
   cd frontend
   npm install
   npm run dev
   ```

3. **访问应用**:
   - 前端: http://localhost:3000
   - 后端 API: http://localhost:8000
   - API 文档: http://localhost:8000/docs

## 技术支持

如有问题:
- 📖 查看完整文档: `docs/`
- 🐛 提交 Issue
- 💬 讨论区

---

**创建时间**: 2026-02-11
**状态**: 可用 ✅
**测试状态**: 已验证 API 可用
**数据位置**: D:\SalesBoost\data
