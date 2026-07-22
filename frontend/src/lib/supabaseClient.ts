import { createClient } from '@supabase/supabase-js';

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL;
const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;

if (!supabaseUrl || !supabaseAnonKey) {
  // Next.js prerenders pages server-side at build time, and this module is
  // imported (via AuthContext) from the root layout — every page. A missing
  // env var here must never throw at module load, or it takes the entire
  // build down rather than just sign-in. Fall back to a placeholder so
  // createClient() succeeds; real auth calls will simply fail at runtime
  // until the real values are configured.
  console.warn(
    'NEXT_PUBLIC_SUPABASE_URL/NEXT_PUBLIC_SUPABASE_ANON_KEY are not set — sign-in will not work until they are configured.',
  );
}

export const supabase = createClient(
  supabaseUrl || 'https://placeholder.supabase.co',
  supabaseAnonKey || 'placeholder-anon-key',
);
