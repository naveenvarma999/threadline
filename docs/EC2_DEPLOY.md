# Deploying to one AWS EC2 server

The model is trained on your laptop. The server only runs the apps with Docker Compose.

**Rough cost:** a t3.medium in London is roughly $35/month if left running. While the instance is
stopped you pay only for the disk and public IP, roughly $2–5/month. Check the numbers in the
[AWS Pricing Calculator](https://calculator.aws/), and **stop the instance when you are not using it**.

## 1. Launch the instance (AWS Console → EC2 → Launch instance)

| Setting | Value |
|---|---|
| Name | `threadline` |
| AMI | Amazon Linux 2023 (64-bit x86) |
| Instance type | `t3.medium` (4 GB RAM; smaller ones run out of memory while building) |
| Key pair | Create new → `threadline-key`, type RSA, format `.pem` → it downloads |
| Storage | 30 GB gp3 |
| Security group | SSH (22) from **My IP**, HTTP (80) from **Anywhere**, Custom TCP 8081 from **My IP** |

Move the key somewhere safe, e.g. `C:\projects\keys\threadline-key.pem`.
Note the instance's **Public IPv4 address** (shown as `<IP>` below).

## 2. Connect (Windows PowerShell)

```powershell
ssh -i C:\projects\keys\threadline-key.pem ec2-user@<IP>
```

If Windows complains that the key's permissions are too open:

```powershell
icacls C:\projects\keys\threadline-key.pem /inheritance:r /grant:r "$($env:USERNAME):R"
```

## 3. Install Docker on the server

```bash
git clone https://github.com/naveenvarma999/threadline.git
cd threadline
bash scripts/ec2-setup.sh
exit
```

SSH back in (the docker group only applies to a new login), then check `docker compose version`.

## 4. Upload the trained model and data (from your laptop, a second PowerShell window)

```powershell
cd C:\projects\threadline
scp -i C:\projects\keys\threadline-key.pem -r data\processed ec2-user@<IP>:~/threadline/data/
scp -i C:\projects\keys\threadline-key.pem -r artifacts\bundle ec2-user@<IP>:~/threadline/artifacts/
```

Create the target folders first if scp says they do not exist: on the server run
`mkdir -p ~/threadline/data ~/threadline/artifacts`.

## 5. Configure and start (on the server)

```bash
cd ~/threadline
cp .env.ec2.example .env
nano .env        # replace all four values; Ctrl+O, Enter, Ctrl+X to save
docker compose -f docker-compose.ec2.yml --env-file .env up -d --build
```

The first build takes 10–20 minutes. Follow it with:

```bash
docker compose -f docker-compose.ec2.yml logs -f app_api inference
```

Ready when you see `Loaded 2500 articles, ...` from app_api and `Model ready` from inference.

## 6. Open it

- Storefront: `http://<IP>/`
- Ops console: `http://<IP>:8081/` (use the `OPS_TOKEN` from `.env`)

## Everyday commands (on the server)

```bash
docker compose -f docker-compose.ec2.yml ps              # what is running
docker compose -f docker-compose.ec2.yml logs -f app_api # follow a service's logs
docker compose -f docker-compose.ec2.yml restart inference
docker compose -f docker-compose.ec2.yml down            # stop the apps (data kept)
```

Updating after code changes: `git pull`, then the `up -d --build` command again.
New model: copy a new `artifacts/bundle` with scp, then `restart inference`.

## Stopping the bill

- **Pause:** EC2 console → Instance state → **Stop**. Start it again for demos. The public IP changes
  on each start unless you attach an Elastic IP.
- **Finish:** Instance state → **Terminate**, then delete the volume if it remains.

## Known limits of this setup

- HTTP only (no HTTPS). Fine for a demo; for HTTPS you need a domain name and a reverse proxy such
  as Caddy in front of port 80.
- No MLflow server on the instance, so the ops console's Models page says the registry is not
  configured. The Overview page works.
- One machine: no autoscaling and no failover. The ECS + Terraform setup in `infra/terraform` is the
  production version.
