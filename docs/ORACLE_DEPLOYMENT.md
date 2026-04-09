# Oracle Cloud "Always Free" Deployment Guide
## Deploying the Legal AI Agent on ARM (Ampere A1)

Oracle Cloud’s **Always Free** tier is the best way to host this project because it provides **24GB of RAM**, which is more than enough to run the Agent, the Vector DB, and the Monitoring Stack (Grafana/Prometheus) simultaneously.

---

### Step 1: Create Your Compute Instance
1. Log in to your Oracle Cloud Console.
2. Go to **Compute > Instances > Create Instance**.
3. **Image**: Choose **Canonical Ubuntu 22.04** (Standard ARM image).
4. **Shape**: Choose **Ampere (ARM)** — select the maximum free resources (**4 OCPUs** and **24 GB RAM**).
5. **Networking**: Ensure you assign a **Public IP address**.
6. **SSH Keys**: Download your private key (`.key` file)—you will need this to log in.

---

### Step 2: Open Ports in Oracle VCN
Oracle blocks all ports by default. You MUST open them in the Virtual Cloud Network:
1. Click your Instance name → **Virtual Cloud Network**.
2. Click **Security Lists** → **Default Security List**.
3. Add **Ingress Rules** for these ports (Source CIDR: `0.0.0.0/0`):
   - `3000` (Frontend)
   - `8000` (Backend API)
   - `3001` (Grafana Dashboard)
   - `9090` (Prometheus - Optional)

---

### Step 3: Prepare the Server
Connect to your server via SSH:
```bash
ssh -i your-key.key ubuntu@your-oracle-ip
```

Then, install Docker and Docker Compose:
```bash
sudo apt update && sudo apt install -y docker.io docker-compose-v2
sudo usermod -aG docker $USER
newgrp docker
```

---

### Step 4: Deploy the Agent
Clone your repository and run the optimized deployment script:

```bash
git clone <your-repo-url>
cd <your-repo-name>

# 1. Provide your OpenAI API Key
echo "OPENAI_API_KEY=your_key_here" >> infra/.env

# 2. Run the High-MoJo Deploy Script
chmod +x scripts/deploy.sh
./scripts/deploy.sh
```

---

### Step 5: Access Your Application
Once the script finishes (it will take a few minutes to build the images on ARM), your project will be live:
- **Frontend**: `http://your-oracle-ip:3000`
- **Dashboard**: `http://your-oracle-ip:3001` (Login: `admin` / `admin`)

> [!TIP]
> **Performance Optimization**: Since your Oracle server has 24GB of RAM, you can increase the `database_pool_size` in `backend/app/core/config.py` to `50` for even faster concurrent request handling!
