import { db as hubDb, schema as hubSchema } from 'hub:db'
import { drizzle } from 'drizzle-orm/node-postgres'
import { Pool } from 'pg'
import * as pgSchema from '../db/schema.pg'

const databaseUrl = process.env.DATABASE_URL?.trim()
const usePostgres = Boolean(databaseUrl)

let pgDb: ReturnType<typeof drizzle> | null = null

if (usePostgres && databaseUrl) {
  const pool = new Pool({
    connectionString: databaseUrl,
    // Required by Neon and other managed Postgres providers.
    ssl: { rejectUnauthorized: false }
  })
  pgDb = drizzle(pool, { schema: pgSchema })
}

export const db = (pgDb ?? hubDb) as typeof hubDb
export const schema = (usePostgres ? pgSchema : hubSchema) as typeof hubSchema

