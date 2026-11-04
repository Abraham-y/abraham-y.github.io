// Renders the midterms page from a data object: {updated, chambers, races, live, live_updated}.
// Used by midterms/index.html (fetches data.json) and by the local election-night dashboard (inlined data).
(function () {
  const esc = s => String(s ?? "").replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const pct = p => (p == null ? "–" : (100 * p).toFixed(0) + "%");
  const gap = e => (e == null ? "–" : (e > 0 ? "+" : e < 0 ? "−" : "±") + Math.abs(100 * e).toFixed(0));
  const last = n => (n ? String(n).trim().split(/\s+/).pop() : "");
  const label = id => { const [st, off] = id.split("-"); return `${st} ${off === "SEN" ? "Sen" : "Gov"}`; };
  const margin = (m, side) => (m == null ? "–" : m === 0 ? "even" : m > 0 ? `${side}+${m.toFixed(1)}` : `R+${(-m).toFixed(1)}`);
  // background tint grows with |gap|: 0 at <3 pts, full at 20+ pts
  const tint = e => (e == null ? 0 : Math.max(0, Math.min(1, (Math.abs(e) - 0.03) / 0.17)));

  function bar(model, market) {
    if (model == null || market == null) return "";
    const lo = Math.min(model, market), hi = Math.max(model, market);
    return `<div class="track" title="model ${pct(model)} · market ${pct(market)}">
      <span class="span" style="left:${100 * lo}%;width:${100 * (hi - lo)}%"></span>
      <span class="mk" style="left:${100 * market}%"></span><span class="md" style="left:${100 * model}%"></span></div>`;
  }

  function matchup(r) {
    const side = r.ind_race ? "I" : "D";
    return `${esc(last(r.challenger))} <span class="pty">(${side})</span> v. ${esc(last(r.rep))} <span class="pty">(R)</span>`;
  }

  function row(cells, e, extraCls) {
    const t = tint(e);
    return `<tr class="${extraCls || ""}" style="--t:${(t * 34).toFixed(1)}">${cells.join("")}</tr>`;
  }

  function chambers(d) {
    return d.chambers.map(c => `<div class="card"><div class="lbl">${esc(c.name)} · Democratic control</div>
      <div class="big">${pct(c.p_model)}</div>
      <div class="sub">${d.final
        ? `pre-election model · forecasters ${pct(c.p_forecasters)} · market before the count ${pct(c.p_market)} · at the end of the night ${pct(c.p_market_final)}`
        : `pre-election model · forecasters ${pct(c.p_forecasters)} · market now ${pct(c.p_market)}`}</div>
      ${bar(c.p_model, c.p_market)}</div>`).join("");
  }

  function liveTable(d) {
    const ind = Object.fromEntries((d.races || []).map(r => [r.race_id, r.ind_race]));
    // held: the projection is still learning how Election Day votes differ from early votes, so its gap isn't ranked;
    // nofeed (final snapshot): no results ever reached the model, so it isn't compared with the market at all
    const nofeed = r => d.final && r.no_count;
    const key = r => (r.held || nofeed(r) ? -1 : Math.abs(r.edge ?? 0));
    const rows = [...(d.live || [])].map(r => ({ ...r, ind_race: r.ind_race ?? ind[r.race_id] }))
      .sort((a, b) => key(b) - key(a));
    const counting = rows.some(r => (r.pct_counted || 0) > 0);
    const held = rows.some(r => r.held);
    const body = rows.map(r => {
      const side = r.ind_race ? "I" : "D";
      const pre = !(r.pct_counted > 0);
      const nf = nofeed(r);
      return row([
        `<td class="l"><b>${label(r.race_id)}</b><div class="mu">${matchup(r)}</div></td>`,
        `<td>${nf ? '<span class="tag">no results</span>' : pre ? '<span class="tag">not yet</span>' : r.pct_counted.toFixed(0) + "%"}</td>`,
        `<td>${pre ? "–" : margin(r.counted_margin, side)}</td>`,
        `<td>${margin(r.proj_margin, side)}<div class="mu">${nf ? "pre-election" : `${margin(r.lo80, side)} to ${margin(r.hi80, side)}`}</div></td>`,
        `<td class="num">${pct(r.p_live)}${r.held ? `<div class="mu"><span class="tag">held</span> E-day gap: ${r.gap_counties ?? 0} of 5 counties</div>` : ""}</td><td class="num">${pct(r.p_market)}</td>`,
        `<td class="num gap">${gap(r.edge)}</td>`,
        `<td class="bar">${nf ? "" : bar(r.p_live, r.p_market)}</td>`,
      ], r.held || nf ? null : r.edge);
    }).join("");
    return { counting, held, html: `<div class="tw"><table><thead><tr><th class="l">Race</th><th>Counted</th><th>Count margin</th>
      <th>Projected (80% range)</th><th>Live</th><th>Market</th><th>Gap</th><th class="bar"></th></tr></thead><tbody>${body}</tbody></table></div>` };
  }

  function raceTable(d) {
    const rows = [...d.races].sort((a, b) => Math.abs(b.edge ?? 0) - Math.abs(a.edge ?? 0));
    const body = rows.map(r => row([
      `<td class="l"><b>${label(r.race_id)}</b><div class="mu">${matchup(r)}</div></td>`,
      `<td>${r.poll_avg == null ? "–" : margin(r.poll_avg, r.ind_race ? "I" : "D")}<div class="mu">${r.n_polls ?? 0} recent</div></td>`,
      `<td class="num">${pct(r.p_final)}</td><td class="num">${pct(r.p_market)}</td>`,
      `<td class="num gap">${gap(r.edge)}</td>`,
      `<td>${r.robust ? '<span class="tag ok">holds</span>' : '<span class="tag">fragile</span>'}<div class="mu">${gap(r.edge_lo)} to ${gap(r.edge_hi)}</div></td>`,
      `<td class="bar">${bar(r.p_final, r.p_market)}</td>`,
    ], r.edge, r.robust ? "" : "fragile")).join("");
    return `<div class="tw"><table><thead><tr><th class="l">Race</th><th>Polls</th><th>Model</th><th>Market</th><th>Gap</th>
      <th>Across 11 variants</th><th class="bar"></th></tr></thead><tbody>${body}</tbody></table></div>`;
  }

  window.renderMidterms = function (d, root) {
    const when = d.updated ? new Date(d.updated).toLocaleString([], { dateStyle: "medium", timeStyle: "short" }) : "–";
    const lt = liveTable(d);
    root.querySelector("#updated").textContent = when + (d.live_updated ? ` · live pass ${d.live_updated}` : "") + (d.final ? " · final snapshot" : "");
    root.querySelector("#chambers").innerHTML = chambers(d);
    const racesNote = root.querySelector("#races-note");
    if (d.final && racesNote) racesNote.textContent = `Market prices as of ${d.prices_asof}, before any votes were counted. ` +
      `Races the market priced between 4% and 96%, sorted by the size of the gap. "Holds" means the gap kept its sign and stayed above 3 points under all 11 alternative model settings.`;
    root.querySelector("#live-note").textContent = d.final
      ? `Last update of election night (live pass ${d.live_updated} PT); this page no longer updates. Market is the price at that time, so in decided races it sits near 0% or 100%. ` +
        `Rows marked "no results" never received state results here, so they show the pre-election projection and are not compared with the market.`
      : lt.counting
      ? "Sorted by the gap between the live projection and the market. Shading grows with the gap." +
        (lt.held ? " Rows marked held are still learning how much the Election Day vote differs from the early vote (it needs Election Day votes from 5 counties), so they sit at the bottom unshaded." : "")
      : "No votes counted yet. Until results arrive, the live column equals the pre-election model. Rows sort by gap; shading grows with it.";
    root.querySelector("#live").innerHTML = lt.html;
    root.querySelector("#races").innerHTML = raceTable(d);
  };
})();
