#!/bin/sh
# Copy the FalkorDB RDB. A Cypher dump and restore check land with G114.
set -eu
mkdir -p exports
docker compose exec -T falkordb redis-cli BGSAVE >/dev/null
i=0
while [ "$i" -lt 20 ]; do
  pending=$(docker compose exec -T falkordb redis-cli INFO persistence | awk -F: '/rdb_bgsave_in_progress/ {gsub("\r","",$2); print $2}')
  if [ "$pending" = "0" ]; then
    break
  fi
  i=$((i + 1))
  sleep 1
done
docker compose cp falkordb:/var/lib/falkordb/data/dump.rdb exports/falkordb.rdb
echo "export: exports/falkordb.rdb"
