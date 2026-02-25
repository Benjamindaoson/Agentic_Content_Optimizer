"""
vLLM 部署脚本 - 部署 Dots LLM 推理服务

支持：
1. 基础模型部署
2. LoRA 动态加载
3. 多 GPU 并行
4. 4-bit 量化
"""

import os
import sys
import argparse
import subprocess
from pathlib import Path

# 配置
DOTS_MODEL_PATH = os.getenv("DOTS_MODEL_PATH", "./models/dots.llm1.inst")
VLLM_HOST = os.getenv("VLLM_HOST", "0.0.0.0")
VLLM_PORT = int(os.getenv("VLLM_PORT", "8001"))
GPU_MEMORY_UTILIZATION = float(os.getenv("GPU_MEMORY_UTILIZATION", "0.9"))
MAX_MODEL_LEN = int(os.getenv("MAX_MODEL_LEN", "4096"))
TENSOR_PARALLEL_SIZE = int(os.getenv("TENSOR_PARALLEL_SIZE", "1"))


def check_dependencies():
    """检查依赖是否安装"""
    print("🔍 检查依赖...")

    try:
        import vllm
        print(f"✅ vLLM 已安装: {vllm.__version__}")
    except ImportError:
        print("❌ vLLM 未安装")
        print("请运行: pip install vllm")
        return False

    try:
        import torch
        print(f"✅ PyTorch 已安装: {torch.__version__}")
        print(f"   CUDA 可用: {torch.cuda.is_available()}")
        if torch.cuda.is_available():
            print(f"   GPU 数量: {torch.cuda.device_count()}")
            for i in range(torch.cuda.device_count()):
                print(f"   GPU {i}: {torch.cuda.get_device_name(i)}")
    except ImportError:
        print("❌ PyTorch 未安装")
        return False

    return True


def check_model_exists(model_path: str):
    """检查模型是否存在"""
    print(f"\n🔍 检查模型路径: {model_path}")

    if not os.path.exists(model_path):
        print(f"❌ 模型路径不存在: {model_path}")
        print("\n请下载 Dots LLM 模型：")
        print("1. 从 Hugging Face 下载:")
        print("   git clone https://huggingface.co/rednote-hilab/dots.llm1.inst")
        print("\n2. 或使用 huggingface-cli:")
        print("   huggingface-cli download rednote-hilab/dots.llm1.inst --local-dir ./models/dots.llm1.inst")
        return False

    # 检查必需文件
    required_files = ["config.json", "tokenizer_config.json"]
    missing_files = []

    for file in required_files:
        file_path = os.path.join(model_path, file)
        if not os.path.exists(file_path):
            missing_files.append(file)

    if missing_files:
        print(f"❌ 缺少必需文件: {', '.join(missing_files)}")
        return False

    print("✅ 模型文件完整")
    return True


def deploy_vllm_server(
    model_path: str,
    host: str = VLLM_HOST,
    port: int = VLLM_PORT,
    enable_lora: bool = True,
    max_loras: int = 8,
    tensor_parallel_size: int = TENSOR_PARALLEL_SIZE,
    gpu_memory_utilization: float = GPU_MEMORY_UTILIZATION,
    max_model_len: int = MAX_MODEL_LEN,
    quantization: str = None
):
    """部署 vLLM 推理服务

    Args:
        model_path: 模型路径
        host: 服务地址
        port: 服务端口
        enable_lora: 是否启用 LoRA 支持
        max_loras: 最大 LoRA 数量
        tensor_parallel_size: 张量并行大小（GPU 数量）
        gpu_memory_utilization: GPU 显存利用率
        max_model_len: 最大序列长度
        quantization: 量化方法（awq, gptq, squeezellm, None）
    """
    print("\n🚀 启动 vLLM 服务...")
    print(f"   模型: {model_path}")
    print(f"   地址: {host}:{port}")
    print(f"   LoRA 支持: {enable_lora}")
    print(f"   GPU 数量: {tensor_parallel_size}")
    print(f"   显存利用率: {gpu_memory_utilization}")
    print(f"   最大序列长度: {max_model_len}")
    if quantization:
        print(f"   量化方法: {quantization}")

    # 构建启动命令
    cmd = [
        "python", "-m", "vllm.entrypoints.openai.api_server",
        "--model", model_path,
        "--host", host,
        "--port", str(port),
        "--tensor-parallel-size", str(tensor_parallel_size),
        "--gpu-memory-utilization", str(gpu_memory_utilization),
        "--max-model-len", str(max_model_len),
        "--trust-remote-code",  # Dots LLM 需要
    ]

    if enable_lora:
        cmd.extend([
            "--enable-lora",
            "--max-loras", str(max_loras),
            "--max-lora-rank", "64"
        ])

    if quantization:
        cmd.extend(["--quantization", quantization])

    print(f"\n执行命令:")
    print(" ".join(cmd))
    print("\n" + "="*80)

    try:
        # 启动服务
        subprocess.run(cmd, check=True)
    except KeyboardInterrupt:
        print("\n\n⚠️  服务已停止")
    except subprocess.CalledProcessError as e:
        print(f"\n❌ 启动失败: {e}")
        sys.exit(1)


def deploy_with_docker(
    model_path: str,
    port: int = VLLM_PORT,
    gpu_count: int = 1
):
    """使用 Docker 部署 vLLM

    Args:
        model_path: 模型路径
        port: 服务端口
        gpu_count: GPU 数量
    """
    print("\n🐳 使用 Docker 部署 vLLM...")

    # 检查 Docker 是否安装
    try:
        subprocess.run(["docker", "--version"], check=True, capture_output=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("❌ Docker 未安装")
        print("请先安装 Docker: https://docs.docker.com/get-docker/")
        return

    # 检查 nvidia-docker 是否安装
    try:
        subprocess.run(["nvidia-docker", "--version"], check=True, capture_output=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("❌ nvidia-docker 未安装")
        print("请先安装 nvidia-docker: https://github.com/NVIDIA/nvidia-docker")
        return

    # 构建 Docker 命令
    model_path_abs = os.path.abspath(model_path)

    cmd = [
        "docker", "run",
        "--gpus", f"device={','.join(str(i) for i in range(gpu_count))}",
        "-v", f"{model_path_abs}:/model",
        "-p", f"{port}:8000",
        "--ipc=host",
        "vllm/vllm-openai:latest",
        "--model", "/model",
        "--enable-lora",
        "--max-loras", "8",
        "--trust-remote-code"
    ]

    print(f"\n执行命令:")
    print(" ".join(cmd))
    print("\n" + "="*80)

    try:
        subprocess.run(cmd, check=True)
    except KeyboardInterrupt:
        print("\n\n⚠️  服务已停止")
    except subprocess.CalledProcessError as e:
        print(f"\n❌ 启动失败: {e}")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="部署 Dots LLM + vLLM 推理服务")

    parser.add_argument(
        "--model-path",
        type=str,
        default=DOTS_MODEL_PATH,
        help="Dots LLM 模型路径"
    )
    parser.add_argument(
        "--host",
        type=str,
        default=VLLM_HOST,
        help="服务地址"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=VLLM_PORT,
        help="服务端口"
    )
    parser.add_argument(
        "--enable-lora",
        action="store_true",
        default=True,
        help="启用 LoRA 支持"
    )
    parser.add_argument(
        "--tensor-parallel-size",
        type=int,
        default=TENSOR_PARALLEL_SIZE,
        help="张量并行大小（GPU 数量）"
    )
    parser.add_argument(
        "--gpu-memory-utilization",
        type=float,
        default=GPU_MEMORY_UTILIZATION,
        help="GPU 显存利用率 (0.0-1.0)"
    )
    parser.add_argument(
        "--max-model-len",
        type=int,
        default=MAX_MODEL_LEN,
        help="最大序列长度"
    )
    parser.add_argument(
        "--quantization",
        type=str,
        choices=["awq", "gptq", "squeezellm"],
        help="量化方法"
    )
    parser.add_argument(
        "--docker",
        action="store_true",
        help="使用 Docker 部署"
    )
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="仅检查环境，不启动服务"
    )

    args = parser.parse_args()

    print("="*80)
    print("🚀 Dots LLM + vLLM 部署脚本")
    print("="*80)

    # 检查依赖
    if not check_dependencies():
        sys.exit(1)

    # 检查模型
    if not check_model_exists(args.model_path):
        sys.exit(1)

    if args.check_only:
        print("\n✅ 环境检查通过！")
        print("\n可以运行以下命令启动服务:")
        print(f"python {__file__} --model-path {args.model_path}")
        return

    # 部署服务
    if args.docker:
        deploy_with_docker(
            model_path=args.model_path,
            port=args.port,
            gpu_count=args.tensor_parallel_size
        )
    else:
        deploy_vllm_server(
            model_path=args.model_path,
            host=args.host,
            port=args.port,
            enable_lora=args.enable_lora,
            tensor_parallel_size=args.tensor_parallel_size,
            gpu_memory_utilization=args.gpu_memory_utilization,
            max_model_len=args.max_model_len,
            quantization=args.quantization
        )


if __name__ == "__main__":
    main()
