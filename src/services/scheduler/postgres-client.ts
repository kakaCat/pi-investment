import pg from "pg";

const { Pool } = pg;

function buildConnectionString(): string {
  const connectionString = process.env.SCHEDULER_DATABASE_URL
    || process.env.QUANT_DATABASE_URL
    || process.env.DATABASE_URL
    || process.env.POSTGRES_DSN;

  if (connectionString) {
    return connectionString;
  }

  // Fallback: construct from individual PG env vars (same as server.ts getPostgresHealthInfo)
  const db = process.env.PGDATABASE || 'quant_investment';
  const host = process.env.PGHOST || 'localhost';
  const port = process.env.PGPORT || '5432';
  const user = process.env.PGUSER || '';  // empty = use OS user (same as pg defaults)

  if (user && process.env.PGPASSWORD) {
    return `postgresql://${user}:${process.env.PGPASSWORD}@${host}:${port}/${db}`;
  }
  if (user) {
    return `postgresql://${user}@${host}:${port}/${db}`;
  }
  return `postgresql://${host}:${port}/${db}`;
}

export function createSchedulerPgPool(): pg.Pool {
  const connectionString = buildConnectionString();
  return new Pool({ connectionString });
}
