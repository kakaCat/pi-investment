#!/usr/bin/env python
"""quant.watch_news_alerts 建表（2026-10-20 · 消息监控闭环 流程图 M/N）

盯盘消息监控的已报留痕：同一条新闻（symbol+标题哈希）只报一次。
幂等键 (symbol, title_hash) 唯一。
"""
import argparse
import os

from sqlalchemy import create_engine, text

DDL = """
CREATE TABLE IF NOT EXISTS quant.watch_news_alerts (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    title_hash VARCHAR(64) NOT NULL,
    title VARCHAR(300) NOT NULL DEFAULT '',
    matched_words JSONB,
    tier VARCHAR(10) NOT NULL DEFAULT 'soft',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (symbol, title_hash)
)
"""

COMMENT = ("COMMENT ON TABLE quant.watch_news_alerts IS "
           "'消息监控已报留痕（2026-10-20）：同一条新闻只报一次'")


def _engine(dsn: str | None = None):
    if dsn:
        return create_engine(dsn)
    url = os.environ.get('QUANT_DATABASE_URL') or 'postgresql+psycopg2:///quant_investment'
    return create_engine(url)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()

    eng = _engine()
    with eng.begin() as conn:
        if args.apply:
            conn.execute(text(DDL))
            conn.execute(text(COMMENT))
        print(('APPLY ' if args.apply else 'DRY   ') + 'CREATE TABLE quant.watch_news_alerts')
    if args.apply:
        with eng.connect() as conn:
            conn.execute(text('SELECT id FROM quant.watch_news_alerts LIMIT 1')).fetchone()
        print('VERIFY OK')
    else:
        print('DRY-RUN done（--apply 生效；请对生产库与 *_test 库各执行一次）')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
