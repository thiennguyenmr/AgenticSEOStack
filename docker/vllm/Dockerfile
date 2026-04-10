FROM python:3.12-slim

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install uv
RUN curl -Ls https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:$PATH"

# Install vLLM with gpt-oss wheel (CUDA 12.8)
RUN uv pip install --system --pre vllm==0.10.1+gptoss \
    --extra-index-url https://wheels.vllm.ai/gpt-oss/ \
    --extra-index-url https://download.pytorch.org/whl/nightly/cu128 \
    --index-strategy unsafe-best-match

EXPOSE 8000

CMD ["vllm", "serve", "openai/gpt-oss-20b", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--served-model-name", "gpt-oss-20b"]
