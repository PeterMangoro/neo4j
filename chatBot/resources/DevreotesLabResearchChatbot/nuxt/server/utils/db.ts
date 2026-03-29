import { drizzle } from 'drizzle-orm/node-postgres'
import { Pool } from 'pg'
import * as pgSchema from '../db/schema.pg'

const databaseUrl = process.env.DATABASE_URL?.trim()
if (!databaseUrl) {
  throw new Error('DATABASE_URL is required for server DB access in this deployment')
}

const pool = new Pool({
  connectionString: databaseUrl,
  // Required by Neon and other managed Postgres providers.
  ssl: { rejectUnauthorized: false }
})

export const db = drizzle(pool, { schema: pgSchema })
export const schema = pgSchema

