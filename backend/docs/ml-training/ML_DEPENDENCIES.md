# ML Training System Dependencies

## Core Dependencies

### Deep Learning Frameworks
```
torch>=2.1.0
transformers>=4.36.0
peft>=0.7.0
trl>=0.7.0
bitsandbytes>=0.41.0
accelerate>=0.25.0
```

### Data Processing
```
datasets>=2.16.0
numpy>=1.24.0
pandas>=2.0.0
```

### Database
```
sqlalchemy>=2.0.0
psycopg2-binary>=2.9.0
alembic>=1.12.0
```

### API Framework
```
fastapi>=0.104.0
uvicorn>=0.24.0
pydantic>=2.5.0
```

### Utilities
```
python-dotenv>=1.0.0
pyyaml>=6.0
tqdm>=4.66.0
```

## Optional Dependencies

### Monitoring
```
tensorboard>=2.15.0
wandb>=0.16.0
```

### Evaluation
```
rouge-score>=0.1.2
sacrebleu>=2.3.0
```

## Installation

### Method 1: pip install (Recommended)
```bash
cd backend
pip install -r requirements_ml.txt
```

### Method 2: conda environment
```bash
conda create -n growth-flywheel python=3.10
conda activate growth-flywheel
pip install -r requirements_ml.txt
```

### Method 3: Docker
```bash
docker build -t growth-flywheel-ml -f Dockerfile.ml .
docker run --gpus all -p 8000:8000 growth-flywheel-ml
```

## GPU Requirements

### Minimum (SFT Training)
- GPU: NVIDIA RTX 3090 (24GB VRAM)
- RAM: 32GB
- Storage: 100GB SSD

### Recommended (SFT + DPO Training)
- GPU: NVIDIA A100 (40GB VRAM) x 2
- RAM: 64GB
- Storage: 500GB NVMe SSD

### Production (Multi-GPU Training)
- GPU: NVIDIA A100 (80GB VRAM) x 4
- RAM: 128GB
- Storage: 1TB NVMe SSD

## System Requirements

### Operating System
- Ubuntu 20.04+ (Recommended)
- CentOS 7+
- Windows 10/11 with WSL2

### CUDA
- CUDA 11.8+
- cuDNN 8.7+

### Python
- Python 3.10+

## Verification

After installation, verify the setup:

```bash
# Check PyTorch and CUDA
python -c "import torch; print(f'PyTorch: {torch.__version__}'); print(f'CUDA: {torch.cuda.is_available()}')"

# Check Transformers
python -c "import transformers; print(f'Transformers: {transformers.__version__}')"

# Check PEFT
python -c "import peft; print(f'PEFT: {peft.__version__}')"

# Check TRL
python -c "import trl; print(f'TRL: {trl.__version__}')"
```

Expected output:
```
PyTorch: 2.1.0+cu118
CUDA: True
Transformers: 4.36.0
PEFT: 0.7.0
TRL: 0.7.0
```

## Troubleshooting

### Issue: CUDA out of memory
**Solution**: Reduce batch size or use gradient accumulation
```python
per_device_train_batch_size = 2  # Reduce from 4
gradient_accumulation_steps = 8  # Increase from 4
```

### Issue: bitsandbytes not found
**Solution**: Install from source
```bash
pip install bitsandbytes --no-binary bitsandbytes
```

### Issue: Slow training
**Solution**: Enable gradient checkpointing and mixed precision
```python
gradient_checkpointing = True
bf16 = True  # or fp16 = True
```

### Issue: Import errors
**Solution**: Reinstall dependencies
```bash
pip uninstall transformers peft trl -y
pip install transformers peft trl --upgrade
```
