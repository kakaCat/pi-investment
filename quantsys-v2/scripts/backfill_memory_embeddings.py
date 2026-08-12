#!/usr/bin/env python
"""存量 memory_entries embedding 回填脚本（W1.3）

对 embedding IS NULL 的条目逐条调用 ollama bge-m3 计算向量并写回。
幂等：只处理 NULL 行，重复执行无副作用。

用法（在 quantsys-v2 目录下）：
    venv/bin/python scripts/backfill_memory_embeddings.py            # 回填生产库（.env）
    venv/bin/python scripts/backfill_memory_embeddings.py --dry-run  # 只统计不写
    PGDATABASE=quant_test venv/bin/python scripts/backfill_memory_embeddings.py  # 回填测试库
"""
import argparse
import sys
from pathlib import Path

# 项目根入 sys.path（与 conftest 同套路）
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv

load_dotenv(PROJECT_ROOT / ".env")

import structlog  # noqa: E402

from adapters.outbound.repositories.memory_repository import MemoryRepository  # noqa: E402
from domain.memory.embedding import OllamaEmbeddingService  # noqa: E402

logger = structlog.get_logger(__name__)


def main() -> int:
    parser = argparse.ArgumentParser(description="回填 memory_entries.embedding")
    parser.add_argument("--dry-run", action="store_true", help="只统计待回填数量，不写入")
    args = parser.parse_args()

    repo = MemoryRepository()
    embedder = OllamaEmbeddingService()

    rows = repo.list_filtered()
    pending = [r for r in rows if not r.get("embedding")]
    print(f"总条目 {len(rows)}，待回填 {len(pending)}")

    if args.dry_run:
        return 0

    ok, failed = 0, 0
    for r in pending:
        vec = embedder.embed(f"{r['title']}\n{r['content']}")
        if vec is None:
            failed += 1
            print(f"  ❌ id={r['id']} embedding 失败（ollama 不可用？）：{r['title'][:40]}")
            continue
        import json

        repo.update(r["id"], {"embedding": json.dumps(vec)})
        ok += 1
        print(f"  ✅ id={r['id']} {r['title'][:40]} dims={len(vec)}")

    print(f"回填完成：成功 {ok}，失败 {failed}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
