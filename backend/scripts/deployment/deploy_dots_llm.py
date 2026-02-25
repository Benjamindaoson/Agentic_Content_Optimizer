"""
Dots LLM Deployment Scripts
使用 vLLM 或 SGLang 部署 dots.llm1

推荐部署方式:
1. vLLM (推荐) - 高性能推理，支持 MoE
2. SGLang - 结构化生成，适合复杂约束
3. Transformers - 标准推理 (不推荐生产环境)
"""

import subprocess
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class DotsLLMDeployer:
    """Dots LLM 部署器"""

    def __init__(
        self,
        model_path: str,
        deployment_type: str = "vllm",  # vllm, sglang, transformers
        port: int = 8000,
        gpu_memory_utilization: float = 0.9,
        tensor_parallel_size: int = 1
    ):
        """
        初始化部署器

        Args:
            model_path: 模型路径
            deployment_type: 部署类型
            port: 服务端口
            gpu_memory_utilization: GPU 显存利用率
            tensor_parallel_size: 张量并行大小 (多卡)
        """
        self.model_path = model_path
        self.deployment_type = deployment_type
        self.port = port
        self.gpu_memory_utilization = gpu_memory_utilization
        self.tensor_parallel_size = tensor_parallel_size

    def deploy_vllm(self):
        """
        使用 vLLM 部署

        vLLM 优势:
        1. PagedAttention - 高效 KV cache 管理
        2. 支持 MoE 模型
        3. 高吞吐量
        4. 兼容 OpenAI API
        """
        logger.info("Deploying with vLLM...")

        command = [
            "python", "-m", "vllm.entrypoints.openai.api_server",
            "--model", self.model_path,
            "--port", str(self.port),
            "--gpu-memory-utilization", str(self.gpu_memory_utilization),
            "--tensor-parallel-size", str(self.tensor_parallel_size),
            "--trust-remote-code",
            "--dtype", "bfloat16",
            # MoE 特定配置
            "--enable-prefix-caching",  # 启用前缀缓存
            "--max-model-len", "32768",  # dots.llm1 支持 32K
        ]

        logger.info(f"Running command: {' '.join(command)}")

        try:
            subprocess.run(command, check=True)
        except subprocess.CalledProcessError as e:
            logger.error(f"vLLM deployment failed: {e}")
            raise

    def deploy_sglang(self):
        """
        使用 SGLang 部署

        SGLang 优势:
        1. 结构化生成 (JSON, 正则表达式约束)
        2. 高效的约束解码
        3. 适合需要严格格式控制的场景
        """
        logger.info("Deploying with SGLang...")

        command = [
            "python", "-m", "sglang.launch_server",
            "--model-path", self.model_path,
            "--port", str(self.port),
            "--mem-fraction-static", str(self.gpu_memory_utilization),
            "--tp", str(self.tensor_parallel_size),
            "--trust-remote-code",
            "--context-length", "32768"
        ]

        logger.info(f"Running command: {' '.join(command)}")

        try:
            subprocess.run(command, check=True)
        except subprocess.CalledProcessError as e:
            logger.error(f"SGLang deployment failed: {e}")
            raise

    def deploy(self):
        """部署模型"""
        if self.deployment_type == "vllm":
            self.deploy_vllm()
        elif self.deployment_type == "sglang":
            self.deploy_sglang()
        else:
            raise ValueError(f"Unknown deployment type: {self.deployment_type}")

    def generate_docker_compose(self, output_path: str = "./docker-compose-dots.yml"):
        """
        生成 Docker Compose 配置

        用于容器化部署
        """
        if self.deployment_type == "vllm":
            compose_content = f"""version: '3.8'

services:
  dots-llm-vllm:
    image: vllm/vllm-openai:latest
    container_name: dots-llm-vllm
    ports:
      - "{self.port}:8000"
    volumes:
      - {self.model_path}:/model
      - ~/.cache/huggingface:/root/.cache/huggingface
    environment:
      - CUDA_VISIBLE_DEVICES=0
    command: >
      --model /model
      --gpu-memory-utilization {self.gpu_memory_utilization}
      --tensor-parallel-size {self.tensor_parallel_size}
      --trust-remote-code
      --dtype bfloat16
      --enable-prefix-caching
      --max-model-len 32768
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: {self.tensor_parallel_size}
              capabilities: [gpu]
    restart: unless-stopped
"""
        elif self.deployment_type == "sglang":
            compose_content = f"""version: '3.8'

services:
  dots-llm-sglang:
    image: lmsysorg/sglang:latest
    container_name: dots-llm-sglang
    ports:
      - "{self.port}:8000"
    volumes:
      - {self.model_path}:/model
      - ~/.cache/huggingface:/root/.cache/huggingface
    environment:
      - CUDA_VISIBLE_DEVICES=0
    command: >
      python -m sglang.launch_server
      --model-path /model
      --port 8000
      --mem-fraction-static {self.gpu_memory_utilization}
      --tp {self.tensor_parallel_size}
      --trust-remote-code
      --context-length 32768
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: {self.tensor_parallel_size}
              capabilities: [gpu]
    restart: unless-stopped
"""
        else:
            raise ValueError(f"Unknown deployment type: {self.deployment_type}")

        # 保存
        with open(output_path, 'w') as f:
            f.write(compose_content)

        logger.info(f"Docker Compose config saved to {output_path}")

    def generate_kubernetes_yaml(self, output_path: str = "./dots-llm-deployment.yaml"):
        """
        生成 Kubernetes 部署配置

        用于 K8s 集群部署
        """
        if self.deployment_type == "vllm":
            k8s_content = f"""apiVersion: apps/v1
kind: Deployment
metadata:
  name: dots-llm-vllm
spec:
  replicas: 1
  selector:
    matchLabels:
      app: dots-llm-vllm
  template:
    metadata:
      labels:
        app: dots-llm-vllm
    spec:
      containers:
      - name: vllm
        image: vllm/vllm-openai:latest
        ports:
        - containerPort: 8000
        env:
        - name: CUDA_VISIBLE_DEVICES
          value: "0"
        command:
        - python
        - -m
        - vllm.entrypoints.openai.api_server
        - --model
        - {self.model_path}
        - --gpu-memory-utilization
        - "{self.gpu_memory_utilization}"
        - --tensor-parallel-size
        - "{self.tensor_parallel_size}"
        - --trust-remote-code
        - --dtype
        - bfloat16
        - --enable-prefix-caching
        - --max-model-len
        - "32768"
        resources:
          limits:
            nvidia.com/gpu: {self.tensor_parallel_size}
        volumeMounts:
        - name: model-storage
          mountPath: /model
      volumes:
      - name: model-storage
        persistentVolumeClaim:
          claimName: dots-llm-model-pvc
---
apiVersion: v1
kind: Service
metadata:
  name: dots-llm-service
spec:
  selector:
    app: dots-llm-vllm
  ports:
  - protocol: TCP
    port: 8000
    targetPort: 8000
  type: LoadBalancer
"""
        else:
            k8s_content = f"""# SGLang K8s deployment
# Similar structure to vLLM
"""

        # 保存
        with open(output_path, 'w') as f:
            f.write(k8s_content)

        logger.info(f"Kubernetes config saved to {output_path}")


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description="Deploy Dots LLM")
    parser.add_argument("--model-path", type=str, required=True, help="Model path")
    parser.add_argument("--deployment-type", type=str, default="vllm", choices=["vllm", "sglang"])
    parser.add_argument("--port", type=int, default=8000, help="Service port")
    parser.add_argument("--gpu-memory-utilization", type=float, default=0.9)
    parser.add_argument("--tensor-parallel-size", type=int, default=1, help="Number of GPUs")
    parser.add_argument("--generate-docker-compose", action="store_true")
    parser.add_argument("--generate-k8s", action="store_true")

    args = parser.parse_args()

    deployer = DotsLLMDeployer(
        model_path=args.model_path,
        deployment_type=args.deployment_type,
        port=args.port,
        gpu_memory_utilization=args.gpu_memory_utilization,
        tensor_parallel_size=args.tensor_parallel_size
    )

    if args.generate_docker_compose:
        deployer.generate_docker_compose()
    elif args.generate_k8s:
        deployer.generate_kubernetes_yaml()
    else:
        deployer.deploy()


if __name__ == "__main__":
    main()
