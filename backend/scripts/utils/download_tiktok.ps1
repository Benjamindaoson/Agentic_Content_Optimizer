# TikTok-10M 数据集下载脚本
# 直接从 Hugging Face 下载 Parquet 文件到 D 盘

# 设置参数
$OutputDir = "D:\growth-flywheel-2.5\backend\data\raw\tiktok-10m"
$BaseUrl = "https://huggingface.co/datasets/The-data-company/TikTok-10M/resolve/main/data"
$TotalFiles = 10  # 总共 10 个文件
$StartFrom = 0    # 从第几个文件开始下载（0-9）

# 创建输出目录
if (-not (Test-Path $OutputDir)) {
    New-Item -ItemType Directory -Path $OutputDir -Force | Out-Null
    Write-Host "创建目录: $OutputDir" -ForegroundColor Green
}

Write-Host ("=" * 60) -ForegroundColor Cyan
Write-Host "TikTok-10M 数据集下载" -ForegroundColor Cyan
Write-Host ("=" * 60) -ForegroundColor Cyan
Write-Host "输出目录: $OutputDir" -ForegroundColor Yellow
Write-Host "总文件数: $TotalFiles" -ForegroundColor Yellow
Write-Host ("=" * 60) -ForegroundColor Cyan

# 主下载循环
$successCount = 0
$failedFiles = @()

for ($i = $StartFrom; $i -lt $TotalFiles; $i++) {
    $fileName = "train-{0:D5}-of-00010.parquet" -f $i
    $url = "$BaseUrl/$fileName"
    $outputPath = Join-Path $OutputDir $fileName

    Write-Host ""
    Write-Host "[$($i+1)/$TotalFiles] 文件: $fileName" -ForegroundColor Cyan

    # 检查文件是否已存在
    if (Test-Path $outputPath) {
        $fileSize = (Get-Item $outputPath).Length / 1MB
        $fileSizeRounded = [math]::Round($fileSize, 2)
        Write-Host "文件已存在: $fileSizeRounded MB" -ForegroundColor Yellow
        Write-Host "跳过下载..." -ForegroundColor Yellow
        $successCount++
        continue
    }

    # 下载文件
    try {
        Write-Host "开始下载..." -ForegroundColor Green
        Write-Host "URL: $url" -ForegroundColor Gray

        # 使用 Invoke-WebRequest 下载
        $ProgressPreference = 'SilentlyContinue'  # 禁用进度条以提高速度
        Invoke-WebRequest -Uri $url -OutFile $outputPath -UseBasicParsing
        $ProgressPreference = 'Continue'

        # 检查文件
        if (Test-Path $outputPath) {
            $fileSize = (Get-Item $outputPath).Length / 1MB
            $fileSizeRounded = [math]::Round($fileSize, 2)
            Write-Host "下载完成: $fileSizeRounded MB" -ForegroundColor Green
            $successCount++
        } else {
            Write-Host "下载失败: 文件不存在" -ForegroundColor Red
            $failedFiles += $fileName
        }

    } catch {
        Write-Host "下载失败: $($_.Exception.Message)" -ForegroundColor Red
        $failedFiles += $fileName
    }

    # 短暂延迟，避免请求过快
    Start-Sleep -Seconds 1
}

# 显示统计信息
Write-Host ""
Write-Host ("=" * 60) -ForegroundColor Cyan
Write-Host "下载完成统计" -ForegroundColor Cyan
Write-Host ("=" * 60) -ForegroundColor Cyan
Write-Host "成功: $successCount / $TotalFiles" -ForegroundColor Green

if ($failedFiles.Count -gt 0) {
    Write-Host "失败: $($failedFiles.Count)" -ForegroundColor Red
    Write-Host "失败文件:" -ForegroundColor Red
    foreach ($file in $failedFiles) {
        Write-Host "  - $file" -ForegroundColor Red
    }
}

# 计算总大小
$totalSize = 0
Get-ChildItem -Path $OutputDir -Filter "*.parquet" | ForEach-Object {
    $totalSize += $_.Length
}
$totalSizeGB = [math]::Round($totalSize / 1GB, 2)
Write-Host "总大小: $totalSizeGB GB" -ForegroundColor Yellow
Write-Host ("=" * 60) -ForegroundColor Cyan
