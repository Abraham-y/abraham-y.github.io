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
- Junior at Stanford, double major in Mathematics and Computer Science.
- Research interests: reinforcement learning, post-training (GRPO / DPO / RLHF), and AI safety: chain-of-thought monitorability, probing, scalable oversight, and how RL design decides whether internal signals stay trustworthy.
- Incoming AI safety research intern (part-time, fall 2026) at Redwood Research. Software engineer intern at Databricks (Data Platform, summer 2026).
- Preprints (June 2026): "Math Distillation Decouples Chain-of-Thought from Behavior on a Reasoning Model"; and "Reading vs. Writing a Near-Oracle Internal Verifier: How RL Design Determines Whether a Correctness Probe Is Safe" (with Anagha Ramaswamy). Two workshop papers under review: "Alembic: Auditing Cue-Injection Faithfulness Metrics" and "Activation Cache Compression for Sparse Autoencoder Training". Do not name venues.
- Projects: Research Frontier Miner (autonomous research-idea agent, in progress, no results yet); Prediction Markets Agent (top 5 of 100+ at the NVIDIA/Vercel/Brex hackathon); multi-agent causal modeling at the Bridgewater AI Hackathon (1 of 24 selected); Maestro (multimodal music coach, TreeHacks music track runner-up); AQI forecasting with LSTM/GNN/CNN (CS 229).
- Experience: undergraduate researcher at Stanford's Chiu Lab (CryoViT, cryo-EM segmentation); Math 104 course grader; CS 106B teaching assistant.
- Leadership: YC Fellow (mentored by Harshita Arora); TreeHacks Summer Fellow and organizer; former Director of Hackspace at BASES; baritone and Social Chair in the Stanford Mendicants a cappella group.
- Background: grew up in Hong Kong; King's Scholar and valedictorian at Eton College.
- Honors: Rabi Scholar (Columbia, top 10 scientific admits nationally); British Mathematical Olympiad Round 2 top 50 twice; UK Chemistry Olympiad gold medal three times and IChO team reserve; World Science Scholars (1 of 48 globally).
- Contact: email ayeung16@stanford.edu, GitHub Abraham-y, LinkedIn (abraham-yeung).`;

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
