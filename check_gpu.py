import torch
print(f"PyTorch: {torch.__version__}")
print(f"CUDA: {torch.cuda.is_available()}")
print(f"GPU: {torch.cuda.get_device_name(0)}")
print(f"VRAM: {torch.cuda.get_device_properties(0).total_memory / 1e9:.1f} GB")

try:
    import pybullet
    print(f"PyBullet: OK")
except:
    print("PyBullet: MISSING")

try:
    import stable_baselines3 as sb3
    print(f"SB3: {sb3.__version__}")
except:
    print("SB3: MISSING")

try:
    import gymnasium
    print(f"Gymnasium: {gymnasium.__version__}")
except:
    print("Gymnasium: MISSING")

try:
    import numpy as np
    print(f"NumPy: {np.__version__}")
except:
    print("NumPy: MISSING")
