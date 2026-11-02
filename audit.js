/* Client-side audit math for the static UI.
 *
 * This is a deliberate port of audit.py. The page has no backend, so the
 * honesty rules have to hold here too:
 *   - no AA score for the current model means no quality claim and no
 *     recommendation, only spend;
 *   - every alternative carries score_delta, because a savings figure without
 *     the quality it costs is the exact dishonesty this project opposes;
 *   - free tiers are never recommended (rate limits make them unusable);
 *   - two models at the same price are one offer, best scorer wins.
 *
 * Works in the browser as window.SpendAudit and in node via module.exports, so
 * tests/test_ui_math.py can compare it against audit.py on the same rows.
 */
(function (root, factory) {
  if (typeof module === "object" && module.exports) {
    module.exports = factory();
  } else {
    root.SpendAudit = factory();
  }
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";

  function cost(row, w) {
    return row.input_per_m * w.monthly_input_m +
           row.output_per_m * w.monthly_output_m;
  }

  function round(x, places) {
    var f = Math.pow(10, places);
    return Math.round(x * f) / f;
  }

  function hasScore(row) {
    return row.aa_score !== null && row.aa_score !== undefined;
  }

  function needsMet(row, needs) {
    if (!needs || needs.length === 0) {
      return true;
    }
    var tags = row.tags ? String(row.tags).split(",") : [];
    for (var i = 0; i < needs.length; i++) {
      if (tags.indexOf(needs[i]) === -1) {
        return false;
      }
    }
    return true;
  }

  function offer(item, baseCost, curScore) {
    return {
      model_id: item.row.model_id,
      provider: item.row.provider,
      input_per_m: item.row.input_per_m,
      output_per_m: item.row.output_per_m,
      monthly_cost: round(item.cost, 2),
      score: item.row.aa_score,
      score_delta: item.row.aa_score - curScore,
      savings_pct: baseCost ? round(100 * (1 - item.cost / baseCost), 1) : 0.0
    };
  }

  /* Audit one workload against the price rows.
   *
   * Returns either {error} (no paid rows for the model) or:
   *   current_cost, current_provider, current_score, quality_verified,
   *   providers (how many provider rows the median came from),
   *   alternatives (up to `top`, cheapest first), same_or_better.
   */
  function audit(w, prices, top) {
    var limit = top || 3;
    var paid = prices.filter(function (p) { return !p.is_free; });
    var cur = paid.filter(function (p) { return p.model_id === w.current_model; });
    if (cur.length === 0) {
      return { error: "no_paid_rows" };
    }

    // Median provider price is what a typical buyer pays; min() picked stale
    // reseller discounts and understated the current bill.
    cur = cur.slice().sort(function (a, b) { return cost(a, w) - cost(b, w); });
    var base = cur[Math.floor(cur.length / 2)];
    var baseCost = cost(base, w);

    var curScore = null;
    cur.forEach(function (p) {
      if (hasScore(p) && (curScore === null || p.aa_score > curScore)) {
        curScore = p.aa_score;
      }
    });

    if (curScore === null) {
      return {
        current_cost: round(baseCost, 2),
        current_provider: base.provider,
        current_input_per_m: base.input_per_m,
        current_output_per_m: base.output_per_m,
        current_score: null,
        quality_verified: false,
        providers: cur.length,
        alternatives: [],
        same_or_better: null
      };
    }

    var best = {};
    paid.forEach(function (p) {
      if (p.model_id === w.current_model || !hasScore(p) || !needsMet(p, w.needs)) {
        return;
      }
      var c = cost(p, w);
      if (c < baseCost && (!best[p.model_id] || c < best[p.model_id].cost)) {
        best[p.model_id] = { cost: c, row: p };
      }
    });

    var ranked = Object.keys(best).map(function (k) { return best[k]; });
    ranked.sort(function (a, b) {
      if (a.cost !== b.cost) {
        return a.cost - b.cost;
      }
      return b.row.aa_score - a.row.aa_score;
    });

    // Two models at one price are the same offer; keep the higher scorer so the
    // list shows distinct trade-offs instead of near-duplicates.
    var seen = {};
    var deduped = [];
    ranked.forEach(function (item) {
      var key = item.row.input_per_m + "|" + item.row.output_per_m;
      if (seen[key]) {
        return;
      }
      seen[key] = true;
      deduped.push(item);
    });

    var sameOrBetter = null;
    for (var i = 0; i < deduped.length; i++) {
      if (deduped[i].row.aa_score >= curScore) {
        sameOrBetter = offer(deduped[i], baseCost, curScore);
        break;
      }
    }

    return {
      current_cost: round(baseCost, 2),
      current_provider: base.provider,
      current_input_per_m: base.input_per_m,
      current_output_per_m: base.output_per_m,
      current_score: curScore,
      quality_verified: true,
      providers: cur.length,
      alternatives: deduped.slice(0, limit).map(function (item) {
        return offer(item, baseCost, curScore);
      }),
      same_or_better: sameOrBetter
    };
  }

  return { audit: audit, cost: cost, needsMet: needsMet };
});
