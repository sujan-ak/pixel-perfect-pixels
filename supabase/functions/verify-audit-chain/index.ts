import { createClient } from "npm:@supabase/supabase-js@2";

const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
  "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
};

const GENESIS_HASH = "0000...0000";

async function computeShortHash(
  previousHash: string,
  actor: string,
  action: string,
  timestamp: string
): Promise<string> {
  const payload = `${previousHash}|${actor}|${action}|${timestamp}`;
  const data = new TextEncoder().encode(payload);
  const hashBuf = await crypto.subtle.digest("SHA-256", data);
  const hashArr = Array.from(new Uint8Array(hashBuf));
  const fullHex = hashArr.map((b) => b.toString(16).padStart(2, "0")).join("");
  return `${fullHex.slice(0, 4)}...${fullHex.slice(-4)}`;
}

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") {
    return new Response("ok", { headers: corsHeaders });
  }

  try {
    const supabaseUrl = Deno.env.get("SUPABASE_URL");
    const serviceRoleKey =
      Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") ||
      Deno.env.get("SERVICE_ROLE_KEY") ||
      Deno.env.get("SUPABASE_SERVICE_KEY") ||
      Deno.env.get("SUPABASE_ANON_KEY");

    if (!supabaseUrl || !serviceRoleKey) {
      return new Response(
        JSON.stringify({
          error: "Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY",
        }),
        {
          status: 500,
          headers: { ...corsHeaders, "Content-Type": "application/json" },
        }
      );
    }

    const supabase = createClient(supabaseUrl, serviceRoleKey, {
      auth: { persistSession: false },
    });

    const { data, error } = await supabase
      .from("audit_log")
      .select("id, ts, actor, action, previous_hash, current_hash")
      .order("id", { ascending: true });

    if (error) {
      return new Response(
        JSON.stringify({ error: error.message }),
        {
          status: 500,
          headers: { ...corsHeaders, "Content-Type": "application/json" },
        }
      );
    }

    if (!data || data.length === 0) {
      return new Response(
        JSON.stringify({
          valid: true,
          checked_blocks: 0,
          broken_at: null,
        }),
        {
          headers: { ...corsHeaders, "Content-Type": "application/json" },
        }
      );
    }

    let checkedBlocks = 0;
    let brokenAt: number | null = null;
    let valid = true;

    for (let i = 0; i < data.length; i++) {
      const row = data[i];
      const expectedPrev = i === 0 ? GENESIS_HASH : data[i - 1].current_hash;

      if (row.previous_hash !== expectedPrev) {
        valid = false;
        brokenAt = row.id;
        break;
      }

      let ts = row.ts;
      if (typeof ts === "string" && ts.endsWith("+00:00")) {
        ts = ts.slice(0, -6) + "Z";
      }

      const recomputed = await computeShortHash(
        row.previous_hash,
        row.actor,
        row.action,
        ts
      );

      if (row.current_hash !== recomputed) {
        valid = false;
        brokenAt = row.id;
        break;
      }

      checkedBlocks++;
    }

    return new Response(
      JSON.stringify({
        valid,
        checked_blocks: valid ? data.length : checkedBlocks,
        broken_at: brokenAt,
      }),
      {
        headers: { ...corsHeaders, "Content-Type": "application/json" },
      }
    );
  } catch (err: any) {
    return new Response(
      JSON.stringify({ error: err.message || String(err) }),
      {
        status: 500,
        headers: { ...corsHeaders, "Content-Type": "application/json" },
      }
    );
  }
});
