FROM postgres:17-bookworm

# Install PostGIS (3.x) and pgvector for PostgreSQL 17
RUN apt-get update \
  && apt-get install -y --no-install-recommends \
    postgresql-17-postgis-3 \
    postgresql-17-postgis-3-scripts \
    postgresql-17-pgvector \
  && rm -rf /var/lib/apt/lists/*

