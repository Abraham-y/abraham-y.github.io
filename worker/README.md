# Chat Worker (Cloudflare Workers AI)

Powers the **Ask my post-trained self** box on abrahamyeung.com with an open-source model
(Llama on Cloudflare Workers AI). Your account/key never touches the website —
the site only talks to this Worker.

## One-time setup

1. Create a free [Cloudflare account](https://dash.cloudflare.com/sign-up).
2. Install Wrangler and log in:
   ```bash
   npm install -g wrangler
   wrangler login
   ```
3. Deploy from this folder:
   ```bash
   cd worker
   wrangler deploy
   ```
4. Wrangler prints a URL like `https://abraham-chat.<your-subdomain>.workers.dev`.
   Put it in `index.html`:
   ```js
   const CHAT_ENDPOINT = 'https://abraham-chat.<your-subdomain>.workers.dev';
   ```
   Commit and push. Done — the panel now uses the live model, and falls back to
   the built-in canned answers if the Worker is ever unreachable.

## Notes

- **Model**: `@cf/meta/llama-3.1-8b-instruct` (fast, cheap). For stronger answers
  switch `MODEL` in `chat-worker.js` to `@cf/meta/llama-3.3-70b-instruct-fp8-fast`.
- **Cost**: Workers AI has a free daily allowance; a personal site stays well
  within it. `max_tokens: 320` and a 6-message history cap bound usage further.
- **Abuse protection**: add a rate-limiting rule in the Cloudflare dashboard
  (Security → WAF → Rate limiting) on the Worker route if you want a hard ceiling.
- **Editing the bio**: update `SYSTEM_PROMPT` in `chat-worker.js`, then
  `wrangler deploy` again.
- **CORS**: `ALLOWED_ORIGINS` already lists abrahamyeung.com + localhost. Add
  any other origins you serve from there.
