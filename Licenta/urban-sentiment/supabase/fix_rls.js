import pg from 'pg';

const { Client } = pg;
const connectionString = "postgresql://postgres:&sH18jt10.m,mmcVE%qt@db.ujdkiorhdynsrlkhrtcm.supabase.co:5432/postgres";
const client = new Client({ connectionString });

async function run() {
  await client.connect();
  
  console.log("Checking RLS status for Copenhagen_Quarters...");
  const rlsStatus = await client.query(`
    SELECT relname, relrowsecurity 
    FROM pg_class 
    WHERE relname = 'Copenhagen_Quarters';
  `);
  console.log("RLS Enabled:", rlsStatus.rows[0]?.relrowsecurity);

  console.log("Creating SELECT policy for anon user on Copenhagen_Quarters...");
  try {
    // If RLS is not enabled, enable it, or just ensure a SELECT policy allows reads
    await client.query(`ALTER TABLE "Copenhagen_Quarters" ENABLE ROW LEVEL SECURITY;`);
    await client.query(`
      DROP POLICY IF EXISTS "Public select" ON "Copenhagen_Quarters";
      CREATE POLICY "Public select" ON "Copenhagen_Quarters" 
      FOR SELECT USING (true);
    `);
    console.log("✅ Policy created successfully.");
  } catch (e) {
    console.error("❌ Policy creation failed:", e.message);
  }

  await client.end();
}

run().catch(console.error);
