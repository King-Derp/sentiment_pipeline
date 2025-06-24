# GPU Support for Sentiment Analysis

This document outlines the steps taken to enable GPU acceleration for the sentiment analysis service, particularly for the FinBERT model.

## Table of Contents
- [Verification Script](#verification-script)
- [Installation Steps](#installation-steps)
- [Configuration](#configuration)
- [Troubleshooting](#troubleshooting)
- [Performance Considerations](#performance-considerations)

## Verification Script

We created a verification script to check GPU availability and configuration. Save this as `gpu_check.py` in your project root:

```python
import torch
import platform

def check_gpu_support():
    print("=" * 50)
    print("System Information:")
    print(f"OS: {platform.system()} {platform.release()}")
    print(f"Python: {platform.python_version()}")
    print(f"PyTorch Version: {torch.__version__}")
    
    print("\n" + "=" * 50)
    print("CUDA Availability Check:")
    cuda_available = torch.cuda.is_available()
    print(f"CUDA Available: {cuda_available}")
    
    if cuda_available:
        print("\n" + "=" * 50)
        print("GPU Information:")
        gpu_count = torch.cuda.device_count()
        print(f"Number of GPUs available: {gpu_count}")
        
        for i in range(gpu_count):
            print(f"\nGPU {i}: {torch.cuda.get_device_name(i)}")
            print(f"  - Memory Allocated: {torch.cuda.memory_allocated(i) / 1024**2:.2f} MB")
            print(f"  - Memory Cached: {torch.cuda.memory_reserved(i) / 1024**2:.2f} MB")
            print(f"  - CUDA Capability: {torch.cuda.get_device_capability(i)}")
    else:
        print("\n" + "=" * 50)
        print("No CUDA-capable GPU found or CUDA is not properly installed.")
        print("You can still run the project on CPU, but it will be slower.")

if __name__ == "__main__":
    check_gpu_support()
```

## Installation Steps

### 1. Uninstall CPU-only PyTorch (if installed)
```bash
pip uninstall torch torchvision torchaudio
```

### 2. Install PyTorch with CUDA Support
For CUDA 12.1 (compatible with RTX 4090):
```bash
pip3 install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
```

### 3. Verify Installation
Run the verification script:
```bash
python gpu_check.py
```

### 4. Install Additional Dependencies
```bash
pip install -r requirements.txt
```

## Configuration

The sentiment analysis service will automatically use available GPUs. This is controlled by the `USE_GPU_IF_AVAILABLE` setting in `sentiment_analyzer/config/settings.py`:

```python
# In settings.py
USE_GPU_IF_AVAILABLE: bool = True  # Set to False to force CPU usage
```

## Troubleshooting

### CUDA Not Detected
1. **Check NVIDIA Drivers**:
   ```bash
   nvidia-smi
   ```
   Should show your GPU and driver version.

2. **Verify CUDA Installation**:
   ```bash
   nvcc --version
   ```

3. **Check PyTorch CUDA Support**:
   ```python
   import torch
   print(f"PyTorch CUDA Version: {torch.version.cuda if hasattr(torch.version, 'cuda') else 'N/A'}")
   ```

### Common Issues

#### 1. Version Mismatch
Ensure your PyTorch CUDA version matches your system's CUDA version. For CUDA 12.x:
```bash
# For CUDA 12.1
pip3 install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
```

#### 2. Out of Memory
If you encounter CUDA out of memory errors:
- Reduce batch size in the configuration
- Clear GPU cache:
  ```python
  import torch
  torch.cuda.empty_cache()
  ```

## Performance Considerations

### Expected Performance
- **RTX 4090**: 
  - Batch size: 32-64 (adjust based on model size)
  - Inference speed: ~1000 samples/second (varies by model)

### Monitoring GPU Usage
```bash
nvidia-smi -l 1  # Updates GPU stats every second
```

### Disabling GPU
To force CPU usage (e.g., for debugging):
```bash
export USE_GPU_IF_AVAILABLE=False
```
Or modify `settings.py`:
```python
USE_GPU_IF_AVAILABLE = False
```

## Known Issues
- **Mixed Precision Training**: Not yet implemented in the current version
- **Multi-GPU Training**: Currently uses single GPU only
