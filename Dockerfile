# The image is the repository and a Python. There is nothing to install
# because there is nothing to install: the service is standard library only,
# which is also what makes the quickstart in the README true.
FROM python:3.12-slim

WORKDIR /app
COPY gate/ ./gate/
COPY explainer/ ./explainer/
COPY attacks/ ./attacks/
COPY web/ ./web/

# No key is baked in and none is set at deploy time, so the service answers in
# recorded mode and says so on the page. A public demo holding a live key is a
# public demo holding somebody's bill.
# COUNTER_EPHEMERAL: the count lives in the container and dies with it, so
# the page says "on this instance" rather than promising a running public
# total that silently returns to zero on the next cold start.
ENV GATE_PORT=8080 \
    TRUST_FORWARDED_FOR=1 \
    COUNTER_EPHEMERAL=1 \
    PYTHONUNBUFFERED=1

EXPOSE 8080
# --strict: a busy port is a failure to report, not a thing to work around. In
# a container the port is assigned, so moving to another one would leave the
# service unreachable and looking healthy.
CMD ["python", "-m", "web", "--host", "0.0.0.0", "--strict"]
