#!/bin/bash
# One-time setup for an Amazon Linux 2023 EC2 instance: Docker, Compose, git and 2 GB of swap.
#   bash scripts/ec2-setup.sh      (then log out and back in so the docker group applies)
set -euo pipefail

sudo dnf update -y
sudo dnf install -y docker git
sudo systemctl enable --now docker
sudo usermod -aG docker "$USER"

# Docker Compose v2 plugin
ARCH=$(uname -m)
sudo mkdir -p /usr/local/lib/docker/cli-plugins
sudo curl -fsSL "https://github.com/docker/compose/releases/download/v2.29.7/docker-compose-linux-${ARCH}" \
  -o /usr/local/lib/docker/cli-plugins/docker-compose
sudo chmod +x /usr/local/lib/docker/cli-plugins/docker-compose

# Swap keeps the Angular/React builds from running out of memory on a 4 GB instance.
if [ ! -f /swapfile ]; then
  sudo fallocate -l 2G /swapfile
  sudo chmod 600 /swapfile
  sudo mkswap /swapfile
  sudo swapon /swapfile
  echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
fi

echo
echo "Done. Log out and SSH back in, then check with: docker compose version"
