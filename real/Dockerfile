# The measurement arm has no third-party dependencies; the behavioural arm needs a client for the
# model API. Everything else is stdlib, keeping the reproduction claim intact for the capacity work
# while letting the Tier 3 agent reach a provider.
#
# Two clients, because the providers are not interchangeable at the wire level: `openai` covers
# every OpenAI-compatible endpoint (the gateway, Groq, NVIDIA NIM, OpenRouter), and `google-genai`
# is required for Gemini, whose SDK takes `types.Content` rather than the OpenAI message dict.
FROM python:3.12-slim
WORKDIR /work
RUN pip install --no-cache-dir "openai>=1.40" "google-genai>=1.0"
COPY src/ /work/src/
COPY runner/ /work/runner/
COPY real/ /work/real/
COPY .env /work/.env
ENV PYTHONPATH=/work/src:/work/runner
