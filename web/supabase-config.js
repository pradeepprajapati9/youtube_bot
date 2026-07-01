/* ============================================================
   Supabase client config (public — safe to commit).
   The anon key is a PUBLIC key protected by Row Level Security.
   Requires the supabase-js UMD script to load BEFORE this file.
   ============================================================ */
const SUPABASE_URL = "https://wkuxhbyicpiqssqqnmkt.supabase.co";
const SUPABASE_ANON_KEY =
  "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6IndrdXhoYnlpY3BpcXNzcXFubWt0Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODI4ODYwNDAsImV4cCI6MjA5ODQ2MjA0MH0.tQF-0ClEVTxvzLYeTaaZbI4MOLkzHN0wdbyeBo0Spiw";

window.sb = window.supabase.createClient(SUPABASE_URL, SUPABASE_ANON_KEY);
