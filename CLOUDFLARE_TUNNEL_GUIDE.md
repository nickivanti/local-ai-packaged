# Cloudflare Tunnel Setup Guide for n8n

## Overview

This guide documents the complete setup of a Cloudflare Tunnel to expose n8n externally while maintaining local access through Caddy. This configuration is essential for Azure OAuth2 authentication, which requires a publicly accessible callback URL.

## Why Cloudflare Tunnel?

- **No port forwarding required**: Securely expose services without opening firewall ports
- **Automatic HTTPS**: Cloudflare provides SSL/TLS certificates automatically
- **OAuth2 compatibility**: Provides stable public URLs required for OAuth callbacks
- **Dual access**: Maintains local development access while providing external endpoints

## Architecture

```
┌─────────────────┐
│  Azure OAuth2   │
│   Callbacks     │
└────────┬────────┘
         │
         ▼
┌─────────────────────────────────────┐
│   Cloudflare Edge Network           │
│   https://iv-n8n.echogridai.eu      │
└────────────┬────────────────────────┘
             │ Cloudflare Tunnel
             ▼
┌─────────────────────────────────────┐
│   Local Server (localhost:5678)     │
│   ┌──────────────────┐              │
│   │  n8n Container   │              │
│   │  (port 5678)     │              │
│   └──────────────────┘              │
│          ▲                           │
│          │                           │
│   ┌──────┴──────┐                   │
│   │    Caddy    │                   │
│   │ (local dev) │                   │
│   └─────────────┘                   │
│ http://n8n.localhost:8001           │
└─────────────────────────────────────┘
```

## Prerequisites

- Cloudflare account with a domain configured
- Docker and Docker Compose running
- n8n service running in local-ai-packaged stack
- sudo/root access on Linux system

## Installation Steps

### 1. Download and Install Cloudflared

```bash
# Download the latest cloudflared binary
wget -q https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb

# Install the package
sudo dpkg -i cloudflared-linux-amd64.deb
```

**Expected Output:**
```
Selecting previously unselected package cloudflared.
(Reading database ... 83217 files and directories currently installed.)
Preparing to unpack cloudflared-linux-amd64.deb ...
Unpacking cloudflared (2025.11.1) ...
Setting up cloudflared (2025.11.1) ...
Processing triggers for man-db (2.12.0-4build2) ...
```

### 2. Authenticate with Cloudflare

```bash
cloudflared tunnel login
```

This command will:
1. Open a browser window
2. Prompt you to select your Cloudflare domain
3. Save credentials to `~/.cloudflared/cert.pem`

**Expected Output:**
```
Please open the following URL and log in with your Cloudflare account:

https://dash.cloudflare.com/argotunnel?aud=&callback=https%3A%2F%2Flogin.cloudflareaccess.org%2F...

Leave cloudflared running to download the cert automatically.
2025-12-22T15:12:09Z INF You have successfully logged in.
If you wish to copy your credentials to a server, they have been saved to:
/home/nickivanti/.cloudflared/cert.pem
```

### 3. Create the Tunnel

```bash
# Create a tunnel with a descriptive name
cloudflared tunnel create iv-n8n-local-ai
```

**Expected Output:**
```
Tunnel credentials written to /home/nickivanti/.cloudflared/c56ce6c9-4600-44be-90df-50fe3062910e.json. 
cloudflared chose this file based on where your origin certificate was found. Keep this file secret. 
To revoke these credentials, delete the tunnel.

Created tunnel iv-n8n-local-ai with id c56ce6c9-4600-44be-90df-50fe3062910e
```

**Important:** Note your tunnel ID - you'll need it for the configuration file.

### 4. Create Tunnel Configuration File

Create the configuration file at `~/.cloudflared/config.yml`:

```bash
code ~/.cloudflared/config.yml
# or use nano, vim, etc.
```

**Configuration Content:**
```yaml
tunnel: c56ce6c9-4600-44be-90df-50fe3062910e
credentials-file: /home/nickivanti/.cloudflared/c56ce6c9-4600-44be-90df-50fe3062910e.json

ingress:
  - hostname: iv-n8n.echogridai.eu
    service: http://localhost:5678
  # Catch-all rule (required)
  - service: http_status:404
```

**Configuration Breakdown:**
- `tunnel`: Your unique tunnel ID
- `credentials-file`: Path to the JSON credentials file created in step 3
- `hostname`: Your public domain/subdomain
- `service`: Local service URL (n8n runs on localhost:5678)

### 5. Create DNS Record

```bash
# Route your domain to the tunnel
cloudflared tunnel route dns iv-n8n-local-ai iv-n8n.echogridai.eu
```

**Expected Output:**
```
2025-12-22T15:22:19Z INF Added CNAME iv-n8n.echogridai.eu which will route to this tunnel 
tunnelID=c56ce6c9-4600-44be-90df-50fe3062910e
```

This creates a CNAME record in your Cloudflare DNS pointing to the tunnel.

### 6. Verify File Structure

```bash
ls -la ~/.cloudflared/
```

**Expected Output:**
```
total 20
drwx------  2 nickivanti nickivanti 4096 Dec 22 16:20 .
drwxr-x--- 16 nickivanti nickivanti 4096 Dec 22 16:11 ..
-r--------  1 nickivanti nickivanti  175 Dec 22 16:12 c56ce6c9-4600-44be-90df-50fe3062910e.json
-rw-------  1 nickivanti nickivanti  266 Dec 22 16:12 cert.pem
-rw-r--r--  1 nickivanti nickivanti  273 Dec 22 16:20 config.yml
```

### 7. Install Cloudflared as System Service

```bash
# Install the service (note the --config flag is required)
sudo cloudflared --config ~/.cloudflared/config.yml service install

# Start the service
sudo systemctl start cloudflared

# Enable it to start on boot
sudo systemctl enable cloudflared

# Verify it's running
sudo systemctl status cloudflared
```

**Expected Output:**
```
2025-12-22T15:29:39Z INF Using Systemd
2025-12-22T15:29:41Z INF Linux service for cloudflared installed successfully

● cloudflared.service - cloudflared
     Loaded: loaded (/etc/systemd/system/cloudflared.service; enabled; preset: enabled)
     Active: active (running) since Mon 2025-12-22 16:29:41 CET; 15s ago
   Main PID: 59922 (cloudflared)
      Tasks: 15 (limit: 18696)
     Memory: 18.8M (peak: 19.9M)
        CPU: 158ms
     CGroup: /system.slice/cloudflared.service
             └─59922 /usr/bin/cloudflared --no-autoupdate --config /etc/cloudflared/config.yml tunnel run

Dec 22 16:29:41 IVNT-DQMHMN3 cloudflared[59922]: 2025-12-22T15:29:41Z INF Registered tunnel connection connIndex=0
Dec 22 16:29:41 IVNT-DQMHMN3 cloudflared[59922]: 2025-12-22T15:29:41Z INF Registered tunnel connection connIndex=1
Dec 22 16:29:42 IVNT-DQMHMN3 cloudflared[59922]: 2025-12-22T15:29:42Z INF Registered tunnel connection connIndex=2
Dec 22 16:29:43 IVNT-DQMHMN3 cloudflared[59922]: 2025-12-22T15:29:43Z INF Registered tunnel connection connIndex=3
```

You should see 4 registered tunnel connections (high availability).

## Update n8n Configuration

### 1. Update Environment Variables

Edit `/home/nickivanti/dev/local-ai-packaged/.env`:

```bash
# Change from:
N8N_HOSTNAME=n8n.localhost

# To:
N8N_HOSTNAME=iv-n8n.echogridai.eu
```

This tells n8n to use the public domain for webhooks and OAuth callbacks.

### 2. Restart n8n

```bash
cd /home/nickivanti/dev/local-ai-packaged
docker compose restart n8n
```

## Verification & Testing

### 1. Check Cloudflared Service Status

```bash
sudo systemctl status cloudflared
```

Should show: `Active: active (running)`

### 2. Test External Access

```bash
curl -I https://iv-n8n.echogridai.eu
```

**Expected Output:**
```
HTTP/2 200 
date: Mon, 22 Dec 2025 15:31:31 GMT
content-type: text/html; charset=utf-8
accept-ranges: bytes
cache-control: public, max-age=86400
server: cloudflare
cf-ray: 9b20aaa828daba9f-MXP
```

### 3. Verify n8n Container

```bash
docker ps | grep n8n
```

**Expected Output:**
```
72b7aad368ae   n8nio/n8n:latest   "tini -- /docker-ent…"   4 hours ago   Up 4 hours   127.0.0.1:5678->5678/tcp   n8n
```

### 4. Test Local Access (via Caddy)

Open in browser: `http://n8n.localhost:8001`

This should still work for local development.

### 5. Test Public Access (via Cloudflare Tunnel)

Open in browser: `https://iv-n8n.echogridai.eu`

This should show the n8n login/interface.

## Azure OAuth2 Configuration

Now that n8n is publicly accessible, you can configure Azure OAuth2:

### Azure App Registration Setup

1. Go to **Azure Portal** → **App Registrations**
2. Select your app or create a new one
3. Navigate to **Authentication** → **Add a platform** → **Web**
4. Add the redirect URI:
   ```
   https://iv-n8n.echogridai.eu/rest/oauth2-credential/callback
   ```
5. Save the configuration

### In n8n

1. Create new credentials (e.g., Microsoft OAuth2)
2. Enter your Azure App's:
   - **Client ID** (Application ID)
   - **Client Secret** (from Certificates & secrets)
   - **Tenant ID** (from Overview page)
3. The OAuth redirect URL will automatically use: `https://iv-n8n.echogridai.eu/rest/oauth2-credential/callback`
4. Click "Connect" to authorize

## Access Patterns

### Local Development
- **URL:** `http://n8n.localhost:8001`
- **Route:** Browser → Caddy → n8n container
- **Use for:** Daily workflow development, testing

### Production/External
- **URL:** `https://iv-n8n.echogridai.eu`
- **Route:** Internet → Cloudflare Edge → Cloudflare Tunnel → n8n container
- **Use for:** OAuth callbacks, webhooks, external integrations

### Internal Webhooks
n8n will generate webhook URLs using `N8N_HOSTNAME`:
- Format: `https://iv-n8n.echogridai.eu/webhook/...`
- These are accessible from external services (Azure, Slack, etc.)

## Maintenance Commands

### View Tunnel Logs
```bash
sudo journalctl -u cloudflared -f
```

### Restart Tunnel Service
```bash
sudo systemctl restart cloudflared
```

### Stop Tunnel Service
```bash
sudo systemctl stop cloudflared
```

### List All Tunnels
```bash
cloudflared tunnel list
```

### Delete a Tunnel
```bash
# First, stop the service
sudo systemctl stop cloudflared

# Delete the tunnel
cloudflared tunnel delete iv-n8n-local-ai

# Remove DNS record manually in Cloudflare dashboard
```

## Troubleshooting

### Tunnel Not Connecting

**Check service status:**
```bash
sudo systemctl status cloudflared
```

**View detailed logs:**
```bash
sudo journalctl -u cloudflared -n 50
```

**Common fix - restart service:**
```bash
sudo systemctl restart cloudflared
```

### n8n Not Accessible Externally

**Verify tunnel is running:**
```bash
cloudflared tunnel list
```

**Check n8n is listening:**
```bash
docker ps | grep n8n
netstat -tlnp | grep 5678
```

**Verify DNS propagation:**
```bash
nslookup iv-n8n.echogridai.eu
dig iv-n8n.echogridai.eu
```

### OAuth Callbacks Failing

**Check N8N_HOSTNAME is set correctly:**
```bash
cd /home/nickivanti/dev/local-ai-packaged
grep N8N_HOSTNAME .env
```

**Restart n8n after changing:**
```bash
docker compose restart n8n
```

**Verify webhook URL in n8n:**
- Go to Settings → n8n configuration
- Check "Webhook URL" shows `https://iv-n8n.echogridai.eu`

### SSL/Certificate Issues

Cloudflare automatically handles SSL. If you see certificate errors:

1. Check Cloudflare SSL/TLS settings (should be "Full" or "Full (strict)")
2. Verify the tunnel is running
3. Clear browser cache/try incognito mode

### Port Conflicts

If localhost:5678 is not accessible:

```bash
# Check what's using port 5678
sudo lsof -i :5678

# Check docker port mapping
docker port n8n
```

## Security Considerations

### Protect Tunnel Credentials
```bash
# Ensure proper permissions
chmod 600 ~/.cloudflared/*.json
chmod 600 ~/.cloudflared/cert.pem
```

### Firewall Configuration
No inbound firewall rules needed - Cloudflare Tunnel creates outbound connections only.

### Access Control
Consider enabling Cloudflare Access for additional authentication:
```bash
# Add to config.yml ingress rule
ingress:
  - hostname: iv-n8n.echogridai.eu
    service: http://localhost:5678
    originRequest:
      noTLSVerify: false
```

### Rate Limiting
Cloudflare provides DDoS protection automatically. For additional rate limiting, configure in Cloudflare dashboard.

## Advanced Configuration

### Multiple Services

To expose additional services (Open WebUI, Flowise, etc.), modify `~/.cloudflared/config.yml`:

```yaml
tunnel: c56ce6c9-4600-44be-90df-50fe3062910e
credentials-file: /home/nickivanti/.cloudflared/c56ce6c9-4600-44be-90df-50fe3062910e.json

ingress:
  - hostname: iv-n8n.echogridai.eu
    service: http://localhost:5678
  - hostname: webui.echogridai.eu
    service: http://localhost:8080
  - hostname: flowise.echogridai.eu
    service: http://localhost:3001
  - service: http_status:404
```

Create DNS routes for each:
```bash
cloudflared tunnel route dns iv-n8n-local-ai webui.echogridai.eu
cloudflared tunnel route dns iv-n8n-local-ai flowise.echogridai.eu
```

Restart the service:
```bash
sudo systemctl restart cloudflared
```

## Files and Locations

| File | Location | Purpose |
|------|----------|---------|
| Tunnel credentials | `~/.cloudflared/*.json` | Authentication credentials (keep secret) |
| Certificate | `~/.cloudflared/cert.pem` | Cloudflare authentication |
| Configuration | `~/.cloudflared/config.yml` | Tunnel routing configuration |
| Service file | `/etc/systemd/system/cloudflared.service` | Systemd service definition |
| Environment config | `/home/nickivanti/dev/local-ai-packaged/.env` | n8n hostname configuration |

## Summary

✅ **Cloudflared installed** and running as system service  
✅ **Tunnel created** with ID: `c56ce6c9-4600-44be-90df-50fe3062910e`  
✅ **DNS configured** for `iv-n8n.echogridai.eu`  
✅ **n8n accessible** both locally and externally  
✅ **OAuth callbacks** working via public URL  
✅ **Automatic HTTPS** provided by Cloudflare  

Your n8n instance is now securely accessible from the internet while maintaining local development capabilities. Azure OAuth2 and other webhook-based integrations will work seamlessly using the public URL.

## Additional Resources

- [Cloudflare Tunnel Documentation](https://developers.cloudflare.com/cloudflare-one/connections/connect-apps/)
- [n8n Webhook Documentation](https://docs.n8n.io/integrations/builtin/core-nodes/n8n-nodes-base.webhook/)
- [Azure OAuth2 Setup](https://docs.microsoft.com/en-us/azure/active-directory/develop/v2-oauth2-auth-code-flow)

---

**Last Updated:** December 22, 2025  
**Setup Verified:** n8n in local-ai-packaged stack with Cloudflare Tunnel  
**Tunnel Name:** iv-n8n-local-ai  
**Public URL:** https://iv-n8n.echogridai.eu
