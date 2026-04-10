# PhishingMKT - n8n Crawl Workflows

## Kien truc

```
docker-compose.yml
├── postgres (PostgreSQL 16)        - port 6868
├── n8n (n8n 2.12.2 + curl)        - port 6789
│   ├── auto-import workflows khi khoi dong
│   ├── luu du lieu crawl vao PostgreSQL
│   └── ho tro Python Code node (external runner)
├── n8n-runner (n8nio/runners)      - Python + JS task runner
├── vllm (vllm-openai:gptoss)      - port 6969 (GPU H200, gpt-oss-20b)
├── openclaw-gateway                - port 18789 (Control UI) / 18790 (Bridge)
├── openclaw-cli                    - CLI companion (tail -f, dung voi docker exec)
└── chromium (browserless)          - headless browser cho n8n
```

## Khoi dong

```bash
# Tao file .env tu mau (neu chua co)
cp .env.example .env  # chinh sua cac secret

# Build va khoi dong
docker compose build
docker compose up -d
```

### Truy cap

| Service          | URL                                                        |
|------------------|------------------------------------------------------------|
| n8n UI           | http://localhost:6789                                      |
| OpenClaw UI      | http://localhost:18789/#token=my_secret_openclaw_token      |
| vLLM API         | http://localhost:6969/v1                                    |
| PostgreSQL       | localhost:6868 (user: n8n / pass: n8n_password)            |

> **Luu y OpenClaw UI:** Phai truy cap qua `localhost`, KHONG dung `127.0.0.1` (WebCrypto secure context).

## Cau truc thu muc

```
├── docker/
│   └── n8n/
│       ├── Dockerfile              # Multi-stage build: Alpine (curl) + n8n
│       ├── import-workflows.sh     # Script tu dong import workflow khi container start
│       └── fetch-page.js           # Script fetch page
├── workflows/
│   ├── crawl-bachhoaxanh.json
│   ├── seo-audit-bachhoaxanh.json
│   └── test-python.json            # Test Python Code node
├── init-db/
│   └── 01-create-tables.sql        # Tao bang khi postgres khoi dong lan dau
├── mnt/
│   ├── n8n/
│   │   ├── n8n_data/               # n8n persistent data
│   │   └── postgres_data/          # PostgreSQL data
│   ├── openclaw/
│   │   ├── config/                 # OpenClaw config (.openclaw)
│   │   └── workspace/              # OpenClaw workspace
│   └── vllm/
│       └── cache/                  # HuggingFace model cache
├── .env                            # Secrets va config
├── .dockerignore                   # Exclude mnt/ khoi build context
└── docker-compose.yml
```

## OpenClaw

### Truy cap UI

```
http://localhost:18789/#token=my_secret_openclaw_token
```

### Hatch TUI (terminal)

```bash
# Chay tu trong container
docker exec -it n8n-openclaw-cli node openclaw.mjs hatch

# Hoac tu host (can set env)
export OPENCLAW_GATEWAY_URI=ws://localhost:18789
openclaw hatch
```

### Lenh CLI huu ich

```bash
# Xem danh sach agents
docker exec n8n-openclaw-cli node openclaw.mjs agents list

# Xem danh sach models
docker exec n8n-openclaw-cli node openclaw.mjs models list

# Xem tat ca models (bao gom built-in)
docker exec n8n-openclaw-cli node openclaw.mjs models list --all
```

### Pairing required (khi truy cap UI hoac TUI)

Khi mo UI hoac chay `openclaw tui` ma gap loi **"pairing required"**, can truyen token trong URL:

```
http://localhost:18789/#token=my_secret_openclaw_token
```

Hoac voi TUI:

```bash
docker exec -it n8n-openclaw-cli node openclaw.mjs tui --token my_secret_openclaw_token
```

Quan ly devices (tu trong container):

```bash
# Xem danh sach devices (paired + pending)
docker exec n8n-openclaw-cli node openclaw.mjs devices list

# Approve device dang cho pair
docker exec n8n-openclaw-cli node openclaw.mjs devices approve <device-id>

# Reject device dang cho pair
docker exec n8n-openclaw-cli node openclaw.mjs devices reject <device-id>

# Xoa device da pair
docker exec n8n-openclaw-cli node openclaw.mjs devices remove <device-id>

# Probe gateway
docker exec n8n-openclaw-cli node openclaw.mjs gateway probe
```

> **Luu y:** Phai dung `localhost`, KHONG dung `127.0.0.1`. Vi `127.0.0.1` khong phai secure context cho WebCrypto, se gay loi "control ui requires device identity".
>
> **Luu y:** Neu CLI bao loi "gateway closed (1006)", restart lai CLI container: `docker compose restart openclaw-cli`. Loi nay xay ra khi gateway restart nhung CLI khong tu reconnect (do `network_mode: service:openclaw-gateway`).

### Fix quyen truy cap config tren host

Docker userns-remap map container UID 1000 (node) -> host UID 1018503.
Neu khong doc duoc `mnt/openclaw/config/` tren host:

```bash
docker run --rm -v ./mnt/openclaw/config:/data alpine sh -c "chmod 755 /data && chmod -R o+rX /data"
```

> OpenClaw co the reset permission ve 600 khi ghi config. Chay lai lenh tren neu can.

## vLLM (GPT-OSS-20B)

- Image: `vllm/vllm-openai:gptoss`
- Model: `openai/gpt-oss-20b`
- GPU: NVIDIA H200 (full precision)
- API tuong thich OpenAI: `http://localhost:6969/v1`

```bash
# Test API
curl http://localhost:6969/v1/models

# Chat completion
curl http://localhost:6969/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model": "gpt-oss-20b", "messages": [{"role": "user", "content": "Hello"}]}'
```

---

## Tong hop loi va cach fix

### Loi 1: Workflow khong tu dong import khi container khoi dong

**Loi:** `null value in column "id" of relation "workflow_entity" violates not-null constraint`

**Nguyen nhan:** File workflow JSON thieu truong `id` o cap ngoai cung. n8n `import:workflow` yeu cau truong nay.

**Cach fix:** Them truong `id` vao dau file JSON:

```json
{
  "id": "crawl-bachhoaxanh-001",
  "name": "Crawl Bach Hoa Xanh - Save to PostgreSQL",
  "nodes": [...]
}
```

---

### Loi 2: HTTP Request node bi ECONNRESET trong Docker container

**Loi:** Node `n8n-nodes-base.httpRequest` tra ve `ECONNRESET` khi goi toi `bachhoaxanh.com`.

**Nguyen nhan:** Website su dung **TLS fingerprinting** (JA3/JA4) trong WAF. Node.js co TLS fingerprint khac voi trinh duyet, nen server tu choi ket noi. Test xac nhan:
- `curl` tu host: **200 OK**
- Node.js `https.get` tu container: **ECONNRESET**
- `openssl s_client`: TLS handshake thanh cong (chung to khong phai loi SSL cert)

**Cach fix:** Thay the HTTP Request node bang **Execute Command** node chay `curl`:

```json
{
  "parameters": {
    "command": "curl -s --max-time 30 --retry 3 --retry-delay 2 --retry-all-errors -L -k -H 'User-Agent: Mozilla/5.0 ...' 'https://www.bachhoaxanh.com'"
  },
  "type": "n8n-nodes-base.executeCommand",
  "typeVersion": 1
}
```

Dong thoi can cai `curl` vao Docker image vi n8n hardened image khong co `apk`:

```dockerfile
# Multi-stage build de copy curl vao n8n image
FROM alpine:3.22 AS curl-builder
RUN apk add --no-cache curl

FROM n8nio/n8n:2.11.4
COPY --from=curl-builder /usr/bin/curl /usr/bin/curl
COPY --from=curl-builder /usr/lib/libcurl* /usr/lib/
COPY --from=curl-builder /usr/lib/libbrotli* /usr/lib/
COPY --from=curl-builder /usr/lib/libnghttp2* /usr/lib/
COPY --from=curl-builder /usr/lib/libidn2* /usr/lib/
COPY --from=curl-builder /usr/lib/libunistring* /usr/lib/
COPY --from=curl-builder /usr/lib/libpsl* /usr/lib/
```

---

### Loi 3: Code node khong cho phep `require('child_process')`

**Loi:** `Module 'child_process' is disallowed [line 1]`

**Nguyen nhan:** n8n Code node chay trong sandbox, chan tat ca module he thong nhu `child_process`, `fs`, `net`...

**Cach fix:** Dung node `n8n-nodes-base.executeCommand` thay vi Code node. Execute Command chay lenh shell truc tiep, khong can `require`.

---

### Loi 4: Execute Command node bao "not currently installed"

**Loi:** `This node is not currently installed. It is either from a newer version of n8n, a custom node, or has an invalid structure`

**Nguyen nhan:** n8n 2.x **mac dinh exclude** node `executeCommand` vi ly do bao mat:

```js
// File: @n8n/config/dist/configs/nodes.config.js
this.exclude = ['n8n-nodes-base.executeCommand', 'n8n-nodes-base.localFileTrigger'];
```

**Cach fix:** Them bien moi truong `NODES_EXCLUDE=[]` trong docker-compose.yml:

```yaml
environment:
  - NODES_EXCLUDE=[]
```

---

### Loi 5: curl tra ve exit code 92 (HTTP/2 stream error)

**Loi:** `curl: (92) HTTP/2 stream 1 was closed cleanly, but before getting all response header fields`

**Nguyen nhan:** WAF cua website phat hien `User-Agent: curl/x.x.x` va tu choi. Ngoai ra WAF cung rate-limit khi goi qua nhieu lan.

**Cach fix:** Luon gui `User-Agent` gia lap trinh duyet va them retry:

```bash
curl -s --max-time 30 \
  --retry 3 --retry-delay 2 --retry-all-errors \
  -L -k \
  -H 'User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36' \
  -H 'Accept: text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8' \
  -H 'Accept-Language: vi-VN,vi;q=0.9,en;q=0.8' \
  -H 'Accept-Encoding: identity' \
  'https://www.bachhoaxanh.com'
```

---

### Loi 6: Credential PostgreSQL "does not exist"

**Loi:** `Credential with ID "REPLACE_WITH_CREDENTIAL_ID" does not exist for type "postgres"`

**Nguyen nhan:** File workflow chua placeholder thay vi credential ID that.

**Cach fix:** Tim credential ID that trong database:

```bash
docker exec n8n-postgres psql -U n8n -d n8n -c "SELECT id, name, type FROM credentials_entity;"
```

Thay `REPLACE_WITH_CREDENTIAL_ID` bang ID that trong file workflow JSON.

---

### Loi 7: PostgreSQL credential "Connection refused"

**Loi:** Save to PostgreSQL node bao `Connection refused`.

**Nguyen nhan:** Credential PostgreSQL trong n8n dang dung `localhost` lam host. Trong Docker network, cac container giao tiep qua **ten service**, khong phai `localhost`.

**Cach fix:** Vao n8n UI > Credentials > Postgres account, cap nhat:

| Field    | Gia tri        |
|----------|----------------|
| Host     | `postgres`     |
| Port     | `5432`         |
| Database | `n8n`          |
| User     | `n8n`          |
| Password | `n8n_password` |

> **Luu y:** Host la `postgres` (ten service trong docker-compose), KHONG phai `localhost` hay `n8n-postgres`.

---

### Loi 8: Workflow bi trung lap trong database

**Nguyen nhan:** Import nhieu lan workflow khong co truong `id` se tao ban ghi moi moi lan (n8n sinh random ID). Khi mo n8n UI co the dang mo ban cu voi node type sai.

**Cach fix:** Xoa cac ban ghi trung lap:

```bash
# Xem tat ca workflow
docker exec n8n-postgres psql -U n8n -d n8n -c "SELECT id, name FROM workflow_entity;"

# Xoa trung lap, giu lai ban co id chuan
docker exec n8n-postgres psql -U n8n -d n8n -c \
  "DELETE FROM workflow_entity WHERE name = 'Ten Workflow' AND id <> 'id-giu-lai';"
```

---

### Loi 9: HTML Extract node khong doc duoc du lieu tu Execute Command

**Nguyen nhan:** Execute Command node tra ve HTML trong truong `stdout`, nhung HTML Extract mac dinh doc tu truong `data`.

**Cach fix:** Them option `sourceData` va `dataProperty` vao HTML Extract node:

```json
{
  "options": {
    "sourceData": "json",
    "dataProperty": "stdout"
  }
}
```

---

### Loi 10: Transform Data node loi vi tham chieu node "Webhook" khong ton tai

**Loi:** `$('Webhook').first().json` throw error.

**Nguyen nhan:** Workflow dung Manual Trigger nhung code van tham chieu node `Webhook` (copy tu workflow khac).

**Cach fix:** Xoa dong tham chieu `$('Webhook')`, hardcode URL hoac lay tu node khac:

```js
// SAI
const webhookData = $('Webhook').first().json;
const url = webhookData.url || 'https://...';

// DUNG
const url = 'https://www.bachhoaxanh.com';
```

---

## Lenh huu ich

```bash
# Build va khoi dong
docker compose build && docker compose up -d

# Xem log tung service
docker logs n8n
docker logs n8n-openclaw-gateway
docker logs vllm

# Restart de re-import workflow
docker compose restart n8n

# Kiem tra workflow trong DB
docker exec n8n-postgres psql -U n8n -d n8n -c "SELECT id, name FROM workflow_entity;"

# Kiem tra credentials
docker exec n8n-postgres psql -U n8n -d n8n -c "SELECT id, name, type FROM credentials_entity;"

# Test curl tu trong container
docker exec n8n curl -s -o /dev/null -w "%{http_code}" --max-time 10 -H "User-Agent: Mozilla/5.0" "https://www.bachhoaxanh.com"

# Import workflow thu cong
docker exec n8n n8n import:workflow --input=/home/node/workflows/ten-file.json

# Fix openclaw config permissions
docker run --rm -v ./mnt/openclaw/config:/data alpine sh -c "chmod 755 /data && chmod -R o+rX /data"
```

---

## OpenClaw + vLLM Integration

### Kien truc

OpenClaw gateway ket noi toi vLLM local (GPT-OSS-20B) qua Docker network `n8n-network`:

```
OpenClaw UI (port 18789)
    │
    ▼
openclaw-gateway ──► vllm (http://vllm:8000/v1)
    │                    │
    │                    └── Model: openai/gpt-oss-20b (GPU 1, ~13.5 GiB)
    │
    └──► OpenRouter (fallback)
```

### Cau hinh vLLM trong OpenClaw

OpenClaw can 2 thu de nhan vLLM lam provider:

**1. Environment variables** (trong `docker-compose.yml` cua openclaw-gateway):

```yaml
environment:
  - VLLM_API_KEY=vllm-local      # bat ky gia tri nao, can thiet de OpenClaw register provider
  - VLLM_BASE_URL=http://vllm:8000/v1
```

**2. Model provider config** (trong `mnt/openclaw/config/openclaw.json`):

```json
{
  "models": {
    "providers": {
      "vllm": {
        "baseUrl": "http://vllm:8000/v1",
        "apiKey": "vllm-local",
        "api": "openai-completions",
        "models": [
          {
            "id": "gpt-oss-20b",
            "name": "GPT-OSS 20B",
            "contextWindow": 131072,
            "maxTokens": 8192,
            "cost": { "input": 0, "output": 0, "cacheRead": 0, "cacheWrite": 0 }
          }
        ]
      }
    }
  },
  "agents": {
    "defaults": {
      "model": {
        "primary": "vllm/gpt-oss-20b",
        "fallbacks": ["openrouter/auto"]
      }
    }
  }
}
```

**3. Agent-level model config** (trong `mnt/openclaw/config/agents/main/agent/models.json`):

```json
{
  "providers": {
    "vllm": {
      "baseUrl": "http://vllm:8000/v1",
      "api": "openai-completions",
      "apiKey": "vllm-local",
      "models": [
        {
          "id": "gpt-oss-20b",
          "name": "GPT-OSS 20B",
          "contextWindow": 131072,
          "maxTokens": 8192,
          "cost": { "input": 0, "output": 0, "cacheRead": 0, "cacheWrite": 0 }
        }
      ]
    }
  }
}
```

### Kiem tra vLLM dang hoat dong

```bash
# Container status
docker ps --format "table {{.Names}}\t{{.Status}}" | grep vllm

# Health check
docker exec vllm python3 -c "import urllib.request; r=urllib.request.urlopen('http://localhost:8000/health'); print(r.status)"

# List models
curl http://localhost:6969/v1/models

# Test chat completion
curl http://localhost:6969/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model": "gpt-oss-20b", "messages": [{"role": "user", "content": "Hello"}], "max_tokens": 50}'

# GPU memory usage
nvidia-smi --query-compute-apps=pid,process_name,used_memory --format=csv,noheader

# Xem throughput realtime
docker logs vllm --tail 5 2>&1 | grep "throughput"
```

### Kiem tra OpenClaw dang dung vLLM

```bash
# Xem model dang active
docker logs n8n-openclaw-gateway 2>&1 | grep "agent model"
# Ket qua dung: agent model: vllm/gpt-oss-20b

# Kiem tra gateway ket noi duoc toi vLLM
docker exec n8n-openclaw-gateway node -e "fetch('http://vllm:8000/v1/models').then(r=>r.json()).then(d=>console.log(d))"

# Xem co fallback sang OpenRouter khong (khong nen co sau khi fix)
docker logs n8n-openclaw-gateway 2>&1 | grep "model-fallback"

# Test truc tiep tu gateway
docker exec n8n-openclaw-gateway node -e "
fetch('http://vllm:8000/v1/chat/completions', {
  method: 'POST',
  headers: {'Content-Type': 'application/json'},
  body: JSON.stringify({model: 'gpt-oss-20b', messages: [{role: 'user', content: 'hi'}], max_tokens: 50})
}).then(r=>r.json()).then(d=>console.log(d.choices[0].message.content))
"
```

### Kiem tra request thuc te di qua vLLM hay OpenRouter

```bash
# Xem vLLM log — neu co POST /v1/chat/completions 200 OK tu 172.18.0.x (gateway IP) la dung
docker logs vllm --tail 20 2>&1 | grep "POST /v1/chat"

# Neu thay "400 Bad Request" -> xem muc "Loi va cach fix" ben duoi
# Neu khong thay POST nao tu gateway -> OpenClaw dang fallback sang OpenRouter
```

> **Luu y:** GPT-OSS-20B tu nhan minh la "ChatGPT" hoac "GPT-4" vi model duoc train dua tren GPT. Day la hanh vi binh thuong, khong phai dang dung OpenRouter.

---

## Tong hop loi va cach fix (OpenClaw + vLLM)

### Loi 11: vLLM tra ve 400 "NoneType object is not iterable"

**Loi:** `harmony_utils.py: TypeError: 'NoneType' object is not iterable`

**Nguyen nhan:** vLLM GPT-OSS image su dung custom "harmony" mode de parse messages. Khi OpenClaw gui conversation history chua assistant message voi `content: null` (do tool_calls), harmony parser crash vi khong handle `None`.

**Cach fix:** Patch 2 file trong vLLM container:

```bash
# Patch harmony_utils.py - handle content: null
docker exec vllm python3 -c "
with open('/usr/local/lib/python3.12/dist-packages/vllm/entrypoints/harmony_utils.py') as f:
    code = f.read()

old = '''    if isinstance(content, str):
        contents = [TextContent(text=content)]
    else:
        # TODO: Support refusal.
        contents = [TextContent(text=c[\"text\"]) for c in content]'''

new = '''    if content is None:
        contents = [TextContent(text=\"\")]
    elif isinstance(content, str):
        contents = [TextContent(text=content)]
    else:
        # TODO: Support refusal.
        contents = [TextContent(text=c[\"text\"]) for c in content if c is not None and \"text\" in c]
        if not contents:
            contents = [TextContent(text=\"\")]'''

code = code.replace(old, new)
with open('/usr/local/lib/python3.12/dist-packages/vllm/entrypoints/harmony_utils.py', 'w') as f:
    f.write(code)
print('Patched harmony_utils.py')
"

# Patch serving_chat.py - skip tool role messages
docker exec vllm python3 -c "
with open('/usr/local/lib/python3.12/dist-packages/vllm/entrypoints/openai/serving_chat.py') as f:
    code = f.read()

old = '''        # Add user message.
        for chat_msg in request.messages:
            messages.append(parse_chat_input(chat_msg))'''

new = '''        # Add user message (skip tool role messages that harmony can't handle).
        for chat_msg in request.messages:
            msg_dict = chat_msg if isinstance(chat_msg, dict) else chat_msg.model_dump()
            if msg_dict.get(\"role\") == \"tool\":
                continue
            messages.append(parse_chat_input(msg_dict))'''

code = code.replace(old, new)
with open('/usr/local/lib/python3.12/dist-packages/vllm/entrypoints/openai/serving_chat.py', 'w') as f:
    f.write(code)
print('Patched serving_chat.py')
"

# Restart vLLM de apply
docker compose restart vllm
```

> **Luu y:** Patch se mat khi recreate container (`docker compose up -d vllm`). Chi con hieu luc khi `restart`. Neu can persistent, build custom Docker image.

---

### Loi 12: OpenClaw fallback sang OpenRouter thay vi dung vLLM

**Loi:** Gateway log hien `model fallback decision: candidate_failed requested=vllm/gpt-oss-20b reason=format next=openrouter/openrouter/auto`

**Nguyen nhan:** Sau khi vLLM tra ve loi 400 (truoc khi patch), OpenClaw ghi nho failure va dat provider vao **cooldown**. Moi request tiep theo tu dong fallback sang OpenRouter ma khong thu lai vLLM.

**Cach fix:**

```bash
# Xoa session cu (co the chua tool_calls history gay loi)
docker exec n8n-openclaw-gateway sh -c 'rm -f /home/node/.openclaw/agents/main/sessions/*.jsonl && echo "{}" > /home/node/.openclaw/agents/main/sessions/sessions.json'

# Restart gateway de xoa cooldown state
docker compose restart openclaw-gateway

# Kiem tra lai
docker logs n8n-openclaw-gateway 2>&1 | grep "agent model"
# Phai thay: agent model: vllm/gpt-oss-20b
```

---

### Loi 13: OpenClaw bao "vLLM requires authentication to be registered as a provider"

**Loi:** `FailoverError: Unknown model: vllm/gpt-oss-20b. vLLM requires authentication...`

**Nguyen nhan:** Thieu env var `VLLM_API_KEY` trong openclaw-gateway container.

**Cach fix:** Them vao docker-compose.yml (service openclaw-gateway):

```yaml
environment:
  - VLLM_API_KEY=vllm-local
  - VLLM_BASE_URL=http://vllm:8000/v1
```

Sau do: `docker compose up -d openclaw-gateway`

---

### Loi 14: vLLM crash "Free memory < desired" khi start

**Loi:** `torch.OutOfMemoryError: Free memory (64.32 GiB) < desired (125.82 GiB)`

**Nguyen nhan:** GPU khong du memory (co process khac dang chiem).

**Cach fix:**

```bash
# Kiem tra process dang chiem GPU
nvidia-smi --query-compute-apps=pid,process_name,used_memory --format=csv,noheader

# Xem ai so huu process
ps -p <PID> -o pid,user,etime,cmd --no-headers

# Kill process zombie (can sudo)
sudo kill <PID>

# Hoac doi GPU (trong docker-compose.yml)
environment:
  - NVIDIA_VISIBLE_DEVICES=1   # dung GPU 1 thay vi 0
```

---

### Loi 15: vLLM healthcheck fail (container unhealthy)

**Nguyen nhan:** vLLM image `vllm/vllm-openai` khong co `curl`. Healthcheck dung curl se luon fail.

**Cach fix:** Dung `python3` cho healthcheck (da co san trong image):

```yaml
healthcheck:
  test: ["CMD-SHELL", "python3 -c \"import urllib.request; urllib.request.urlopen('http://localhost:8000/health')\" 2>/dev/null || exit 1"]
  interval: 30s
  timeout: 10s
  retries: 5
  start_period: 120s   # model load mat ~3-5 phut
```

---

### Loi 16: OPENCLAW_CONFIG_PATH override lam mat Telegram va model config

**Loi:** Telegram bot khong start, model config khong duoc load, zero log lien quan.

**Nguyen nhan:** Env var `OPENCLAW_CONFIG_PATH=/home/node/.openclaw/config.json5` trong docker-compose lam gateway doc `config.json5` (chi co allowedOrigins) thay vi `openclaw.json` (co Telegram, model, auth config).

**Cach fix:** Xoa `OPENCLAW_CONFIG_PATH` khoi environment cua openclaw-gateway. De gateway tu dong doc `openclaw.json` (default).

---

### Loi 17: openclaw-cli "Cannot restart container" sau khi gateway recreate

**Loi:** `docker compose restart openclaw-cli` bao loi `cannot join network of a non-running container`

**Nguyen nhan:** CLI dung `network_mode: "service:openclaw-gateway"`, tham chieu toi container ID cu. Khi gateway bi recreate (ID moi), CLI khong the restart vi ID cu khong con.

**Cach fix:** Dung `up -d` (recreate) thay vi `restart`:

```bash
docker compose up -d openclaw-cli
```

---

Google is blocking all automated access from your server IP (5.183.90.113) — both Firecrawl and the headless browser get CAPTCHA/429. Direct Google scraping won't work.

Options to fix this:

SerpAPI (recommended) — returns structured Google results including AI Overview as JSON. Free tier: 100 searches/month.
Google Custom Search API — free 100 queries/day, but no AI Overview.
Brave Search API — free tier, bot-friendly, no CAPTCHA.


Google blocks 5.183.90.113 because:

1. Datacenter IP — Your server is on a VPS/cloud provider (likely in Europe). Google aggressively blocks datacenter IPs vs residential IPs since bots almost always run from datacenters.

2. Shared IP reputation — Other users on the same hosting provider have likely been scraping Google too, getting the entire IP range flagged.

3. Automated traffic detection — Headless browsers (browserless/Firecrawl) send patterns Google detects: missing cookies, no browsing history, specific TLS fingerprints, no mouse movements.

4. Rate limiting — Even a single request from a flagged IP triggers CAPTCHA/429.