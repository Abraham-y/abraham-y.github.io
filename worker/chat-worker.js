/**
 * Cloudflare Worker — open-source chatbot for abrahamyeung.com
 * Runs an open model on Cloudflare Workers AI. The site calls this Worker;
 * the Worker calls the model. No API keys live in the website.
 *
 * Deploy:
 *   1. Create a free Cloudflare account, then `npm i -g wrangler` and `wrangler login`.
 *   2. From the worker/ folder run:  wrangler deploy
 *   3. Copy the printed URL (e.g. https://abraham-chat.<you>.workers.dev)
 *      into CHAT_ENDPOINT in index.html, commit, and push.
 *
 * Cost: Workers AI has a free daily allowance; this stays well within it for a
 * personal site. The history cap + max_tokens below also bound usage.
 */

// Open instruct model. Upgrade to '@cf/meta/llama-3.3-70b-instruct-fp8-fast'
// for stronger answers (uses more of the free allowance per call).
const MODEL = '@cf/meta/llama-3.1-8b-instruct';

const SYSTEM_PROMPT = `You are a friendly, concise assistant embedded on the personal website of Abraham Yeung. Answer visitors' questions about Abraham only, in a warm and professional tone. If asked something unrelated to Abraham, gently redirect to his work. Keep replies under ~120 words and never invent facts.

About Abraham:
- Sophomore at Stanford, double major in Mathematics and Computer Science.
- Research interests: reinforcement learning, post-training (RLHF / RLAIF), and AI safety & alignment — steering capable models toward reliable, human-aligned behavior.
- Preprints (Stanford, 2026): "Math Distillation Decouples Chain-of-Thought from Behavior on a Reasoning Model"; and "Reading vs. Writing a Near-Oracle Internal Verifier: How RL Design Determines Whether a Correctness Probe Is Safe" (with Anagha Ramaswamy).
- Projects: Maestro (multimodal AI music coach, TreeHacks); a Prediction Market Agent (top-5 at SF Tech Week); CryoViT (vision transformers for cryo-EM in Stanford's Chiu Lab); AQI Forecasting (LSTM/GNN/CNN, CS229).
- Experience: incoming SWE intern at Databricks (2026); Math 104 grader and CS 106 section leader at Stanford; Director of Hackspace at BASES; ML intern at the Chiu Lab.
- Background: grew up in Hong Kong; King's Scholar and valedictorian at Eton College. Sings baritone with the Stanford Mendicants. Cares about environmentalism and mentorship.
- Honors: Rabi Scholarship (Columbia), UK Chemistry Olympiad (top 4), British Math Olympiad (top 50, twice), World Science Scholars, COP27 youth delegate.
- Contact: email ayeung1616@gmail.com, GitHub Abraham-y, LinkedIn (abraham-yeung).`;

const ALLOWED_ORIGINS = [
  'https://abrahamyeung.com',
  'https://www.abrahamyeung.com',
  'http://localhost:8000',
  'http://127.0.0.1:8000',
];

function corsHeaders(origin) {
  const allow = ALLOWED_ORIGINS.includes(origin) ? origin : ALLOWED_ORIGINS[0];
  return {
    'Access-Control-Allow-Origin': allow,
    'Access-Control-Allow-Methods': 'POST, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type',
    'Vary': 'Origin',
  };
}
function json(obj, status, headers) {
  return new Response(JSON.stringify(obj), {
    status,
    headers: { 'Content-Type': 'application/json', ...headers },
  });
}

export default {
  async fetch(request, env) {
    const origin = request.headers.get('Origin') || '';
    const cors = corsHeaders(origin);

    if (request.method === 'OPTIONS') return new Response(null, { headers: cors });
    if (request.method !== 'POST') return json({ error: 'POST only' }, 405, cors);

    let body;
    try { body = await request.json(); } catch { return json({ error: 'invalid JSON' }, 400, cors); }

    // Sanitize: keep only the last few turns, cap content length, force valid roles.
    const incoming = Array.isArray(body.messages) ? body.messages : [];
    const history = incoming.slice(-6).map(m => ({
      role: m && m.role === 'assistant' ? 'assistant' : 'user',
      content: String((m && m.content) || '').slice(0, 1000),
    })).filter(m => m.content);

    if (!history.length) return json({ error: 'no message' }, 400, cors);

    const messages = [{ role: 'system', content: SYSTEM_PROMPT }, ...history];

    try {
      const result = await env.AI.run(MODEL, { messages, max_tokens: 320 });
      const reply = (result && result.response ? result.response : '').trim();
      if (!reply) return json({ error: 'empty reply' }, 502, cors);
      return json({ reply }, 200, cors);
    } catch (e) {
      return json({ error: 'ai_error' }, 500, cors);
    }
  },
};
