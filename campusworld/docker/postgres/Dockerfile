FROM postgis/postgis:15-3.4

# Install pgvector for PostgreSQL 15
RUN apt-get update \
  && apt-get install -y --no-install-recommends postgresql-15-pgvector \
  && rm -rf /var/lib/apt/lists/*

