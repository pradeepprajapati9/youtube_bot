/* ============================================================
   YouTube_Bot — front-end config
   Paste your own values here. Safe to commit: a Google OAuth
   *Client ID* is public by design (it is NOT a secret).
   ============================================================ */
const CONFIG = {
  // Google OAuth Client ID (from Google Cloud Console — see "My Channel" tab
  // for step-by-step). Leave "" to show setup instructions instead.
  GOOGLE_CLIENT_ID: "",

  // Your GitHub repo (used to trigger the video-build Action).
  GITHUB_OWNER: "pradeepprajapati9",
  GITHUB_REPO: "youtube_bot",
  WORKFLOW_FILE: "daily.yml",   // the workflow that builds + uploads the video
  GITHUB_REF: "main",           // branch to run it on
};
