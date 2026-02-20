# Fix dpkg corruption + enable Docker GPU (CUDA)

## Steps

```bash
# 1. Kill stuck unattended upgrades (cloud-safe)
sudo pkill -9 unattended-upgr || true

# 2. Remove dpkg lock files
sudo rm -f /var/lib/dpkg/lock-frontend
sudo rm -f /var/lib/dpkg/lock

# 3. Remove corrupted dpkg update file
sudo rm -f /var/lib/dpkg/updates/0004

# 4. Repair dpkg state
sudo dpkg --configure -a

# 5. Disable unattended upgrades permanently (recommended on Vast)
sudo systemctl stop unattended-upgrades
sudo systemctl disable unattended-upgrades

# 6. Update packages
sudo apt update

# 7. Install NVIDIA Container Toolkit
sudo apt install -y nvidia-container-toolkit

# 8. Configure Docker to use NVIDIA runtime
sudo nvidia-ctk runtime configure --runtime=docker

# 9. Restart Docker
sudo systemctl restart docker
```

## Verify GPU Access

```bash
# Host GPU
nvidia-smi

# Docker GPU
docker run --rm --gpus all nvidia/cuda:12.4.1-base-ubuntu22.04 nvidia-smi
```
