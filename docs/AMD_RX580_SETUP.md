# AMD Radeon RX 580 eGPU Setup Guide for Nexus OS
# Installation instructions for optimal AI acceleration

## Hardware Requirements
- AMD Radeon RX 580 (8GB recommended)
- Thunderbolt 3 or USB4 eGPU enclosure
- Thunderbolt 3/4 cable

## Windows Setup (Current Development Environment)

### 1. AMD Drivers
```powershell
# Download latest AMD Adrenalin drivers
# https://www.amd.com/en/support
# Select: Radeon RX 580
# Install: "Adrenalin Edition" (Full package)
```

### 2. ROCm for Windows (PyTorch AMD Support)
```powershell
# ROCm is not officially supported on Windows
# Use DirectML instead (Microsoft's DirectX ML acceleration)

pip install torch-directml
pip install tensorflow-directml-plugin
```

### 3. OpenCL for OpenCV
```powershell
# AMD OpenCL drivers are included in Adrenalin
# Verify OpenCL:
clinfo
```

### 4. Test GPU Detection
```powershell
cd "E:\MTTGG\PYTHON SOURCE FILES"
python gpu_manager.py
```

## Linux Setup (For Nexus OS)

### 1. AMD GPU Drivers (AMDGPU)
```bash
# Ubuntu/Debian
sudo apt update
sudo apt install -y mesa-utils mesa-vulkan-drivers

# Verify detection
lspci | grep -i amd
glxinfo | grep "OpenGL renderer"
```

### 2. ROCm Installation (Full AMD ML Support)
```bash
# Add ROCm repository (Ubuntu 22.04)
wget -q -O - https://repo.radeon.com/rocm/rocm.gpg.key | sudo apt-key add -
echo 'deb [arch=amd64] https://repo.radeon.com/rocm/apt/5.7 ubuntu main' | sudo tee /etc/apt/sources.list.d/rocm.list

sudo apt update
sudo apt install -y rocm-dkms rocm-libs rocm-dev

# Add user to render group
sudo usermod -a -G render,video $USER

# Reboot required
sudo reboot
```

### 3. PyTorch with ROCm
```bash
# Install PyTorch ROCm build
pip3 install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/rocm5.7
```

### 4. TensorFlow with ROCm
```bash
# Install TensorFlow ROCm
pip3 install tensorflow-rocm
```

### 5. OpenCV with OpenCL
```bash
sudo apt install -y libopencv-dev python3-opencv
```

### 6. Verify Installation
```bash
# Check ROCm
rocm-smi

# Test PyTorch
python3 -c "import torch; print(torch.cuda.is_available()); print(torch.cuda.get_device_name(0))"

# Test OpenCL
clinfo
```

## Performance Optimization

### RX 580 Specifications
- Architecture: Polaris 20
- Stream Processors: 2304
- Memory: 8GB GDDR5
- Memory Bandwidth: 256 GB/s
- Compute Units: 36
- FP32 Performance: ~6.2 TFLOPS

### Optimal Settings for AI Workloads
```python
# In .env file or local.json
GPU_ENABLED=true
EGPU_ENABLED=true
GPU_DEVICE=auto
GPU_MEMORY_FRACTION=0.85  # Leave some VRAM for system
MIXED_PRECISION=true      # FP16 for faster inference
```

### Expected Performance Gains
- **Card Recognition**: 10-15x faster than CPU
- **Batch Processing**: 100+ cards/second
- **Image Enhancement**: Real-time processing
- **AI Deck Building**: 5x faster optimization

## Troubleshooting

### eGPU Not Detected
```bash
# Linux: Check Thunderbolt authorization
sudo boltctl list
sudo boltctl enroll <device-id>

# Windows: Check Device Manager
# Ensure eGPU appears under "Display adapters"
```

### ROCm Not Working
```bash
# Check kernel modules
lsmod | grep amdgpu

# Verify ROCm runtime
/opt/rocm/bin/rocminfo

# Check OpenCL
clinfo | grep -i "AMD"
```

### Low Performance
```python
# Increase batch size in gpu_manager.py
# RX 580 can handle larger batches:
base_batch_size = 64  # Instead of 32
```

## Nexus OS Integration

The AMD RX 580 will be automatically detected when:
1. Nexus OS boots with eGPU connected
2. ROCm drivers are pre-installed in the OS image
3. GPU manager auto-configures PyTorch/TensorFlow

### Auto-Start Configuration
```bash
# /etc/systemd/system/nexus-gpu-init.service
[Unit]
Description=Nexus GPU Initialization
After=multi-user.target

[Service]
Type=oneshot
ExecStart=/usr/local/bin/nexus-gpu-init.sh
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
```

## Benchmark Results (Expected)

| Task | CPU (Intel i5) | RX 580 eGPU | Speedup |
|------|---------------|-------------|---------|
| Single Card Recognition | 0.5s | 0.03s | 16x |
| Batch 100 Cards | 50s | 3s | 17x |
| AI Deck Optimization | 30s | 6s | 5x |
| Image Upscaling (4K) | 10s | 0.8s | 12x |

## Direct Download Links

### Windows
- AMD Adrenalin: https://www.amd.com/en/support/graphics/radeon-500-series/radeon-rx-500-series/radeon-rx-580
- DirectML: `pip install torch-directml`

### Linux (for Nexus OS ISO)
- ROCm 5.7: https://repo.radeon.com/rocm/apt/5.7/
- PyTorch ROCm: https://download.pytorch.org/whl/rocm5.7/
- TensorFlow ROCm: https://pypi.org/project/tensorflow-rocm/

## Notes
- RX 580 is Polaris architecture (GCN 4.0)
- ROCm 5.7+ required for best compatibility
- DirectML works on Windows without ROCm
- eGPU has ~20% overhead vs internal PCIe (still 13x faster than CPU)
