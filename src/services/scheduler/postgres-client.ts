import pg from "pg";

const { Pool } = pg;

export function createSchedulerPgPool(): pg.Pool {
  const connectionString = process.env.SCHEDULER_DATABASE_URL
    || process.env.QUANT_DATABASE_URL
    || process.env.DATABASE_URL
    || process.env.POSTGRES_DSN;

  if (!connectionString) {
    throw new Error("Scheduler requires PostgreSQL. Set SCHEDULER_DATABASE_URL or DATABASE_URL.");
  }

  return new Pool({ connectionString });
}
