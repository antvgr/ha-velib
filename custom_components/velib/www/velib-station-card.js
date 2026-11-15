/*! velib-station-card.js — Carte Lovelace Home Assistant pour une station Vélib' Métropole.
 *  Fichier unique, sans build. 3 layouts : realistic (A), list (B), summary (D).
 *  Config : { type:'custom:velib-station-card', entity:'sensor.…', layout:'realistic|list|summary', title:'…' }
 *  L'entité porte les attributs : station_name, station_code, capacity, free_docks,
 *  mechanical_available, ebike_available, bikes:[{number,type,dock,battery_level,battery_max,
 *  battery_percent,charging,rating,rates,status,available,last_rate_date}]
 */
(function () {
  "use strict";

  // --- Paths Material Design Icons (officiels, inline, aucune dépendance) ---
  var MDI = {
    bike: "M19 10C18.44 10 17.91 10.11 17.41 10.28L14.46 4.5H11V6H13.54L14.42 7.72L12 13.13L10.23 8.95C10.5 8.85 10.74 8.58 10.74 8.25C10.74 7.84 10.41 7.5 10 7.5H8C7.58 7.5 7.24 7.84 7.24 8.25S7.58 9 8 9H8.61L10.86 14.25H9.92C9.56 11.85 7.5 10 5 10C2.24 10 0 12.24 0 15S2.24 20 5 20C7.5 20 9.56 18.15 9.92 15.75H12.5L15.29 9.43L16.08 10.96C14.82 11.87 14 13.34 14 15C14 17.76 16.24 20 19 20S24 17.76 24 15 21.76 10 19 10M5 18.5C3.07 18.5 1.5 16.93 1.5 15S3.07 11.5 5 11.5C6.67 11.5 8.07 12.68 8.41 14.25H4V15.75H8.41C8.07 17.32 6.67 18.5 5 18.5M19 18.5C17.07 18.5 15.5 16.93 15.5 15C15.5 13.92 16 12.97 16.77 12.33L18.57 15.85L19.89 15.13L18.1 11.63C18.39 11.56 18.69 11.5 19 11.5C20.93 11.5 22.5 13.07 22.5 15S20.93 18.5 19 18.5Z",
    bikeE: "M19 7C18.44 7 17.91 7.11 17.41 7.28L14.46 1.5H11V3H13.54L14.42 4.72L12 10.13L10.23 5.95C10.5 5.85 10.74 5.58 10.74 5.25C10.74 4.84 10.41 4.5 10 4.5H8C7.58 4.5 7.24 4.84 7.24 5.25S7.58 6 8 6H8.61L10.86 11.25H9.92C9.56 8.85 7.5 7 5 7C2.24 7 0 9.24 0 12S2.24 17 5 17C7.5 17 9.56 15.15 9.92 12.75H12.5L15.29 6.43L16.08 7.96C14.82 8.87 14 10.34 14 12C14 14.76 16.24 17 19 17S24 14.76 24 12 21.76 7 19 7M5 15.5C3.07 15.5 1.5 13.93 1.5 12S3.07 8.5 5 8.5C6.67 8.5 8.07 9.68 8.41 11.25H4V12.75H8.41C8.07 14.32 6.67 15.5 5 15.5M19 15.5C17.07 15.5 15.5 13.93 15.5 12C15.5 10.92 16 9.97 16.77 9.33L18.57 12.85L19.89 12.13L18.1 8.63C18.39 8.56 18.69 8.5 19 8.5C20.93 8.5 22.5 10.07 22.5 12S20.93 15.5 19 15.5M11 20H7L13 23V21H17L11 18V20Z",
    battOut: "M16,20H8V6H16M16.67,4H15V2H9V4H7.33A1.33,1.33 0 0,0 6,5.33V20.67C6,21.4 6.6,22 7.33,22H16.67A1.33,1.33 0 0,0 18,20.67V5.33C18,4.6 17.4,4 16.67,4Z",
    battLow: "M16 20H8V6H16M16.67 4H15V2H9V4H7.33C6.6 4 6 4.6 6 5.33V20.67C6 21.4 6.6 22 7.33 22H16.67C17.41 22 18 21.41 18 20.67V5.33C18 4.6 17.4 4 16.67 4M15 16H9V19H15V16",
    battMed: "M16 20H8V6H16M16.67 4H15V2H9V4H7.33C6.6 4 6 4.6 6 5.33V20.67C6 21.4 6.6 22 7.33 22H16.67C17.41 22 18 21.41 18 20.67V5.33C18 4.6 17.4 4 16.67 4M15 16H9V19H15V16M15 11.5H9V14.5H15V11.5Z",
    battHigh: "M16 20H8V6H16M16.67 4H15V2H9V4H7.33C6.6 4 6 4.6 6 5.33V20.67C6 21.4 6.6 22 7.33 22H16.67C17.41 22 18 21.41 18 20.67V5.33C18 4.6 17.4 4 16.67 4M15 16H9V19H15V16M15 7H9V10H15V7M15 11.5H9V14.5H15V11.5Z",
    battChg: "M16.67,4H15V2H9V4H7.33A1.33,1.33 0 0,0 6,5.33V20.66C6,21.4 6.6,22 7.33,22H16.66C17.4,22 18,21.4 18,20.67V5.33C18,4.6 17.4,4 16.67,4M11,20V14.5H9L13,7V12.5H15",
    star: "M12,17.27L18.18,21L16.54,13.97L22,9.24L14.81,8.62L12,2L9.19,8.62L2,9.24L7.45,13.97L5.82,21L12,17.27Z",
    starO: "M12,15.39L8.24,17.66L9.23,13.38L5.91,10.5L10.29,10.13L12,6.09L13.71,10.13L18.09,10.5L14.77,13.38L15.76,17.66M22,9.24L14.81,8.63L12,2L9.19,8.63L2,9.24L7.45,13.97L5.82,21L12,17.27L18.18,21L16.54,13.97L22,9.24Z",
    lock: "M12,17A2,2 0 0,0 14,15C14,13.89 13.1,13 12,13A2,2 0 0,0 10,15A2,2 0 0,0 12,17M18,8A2,2 0 0,1 20,10V20A2,2 0 0,1 18,22H6A2,2 0 0,1 4,20V10C4,8.89 4.9,8 6,8H7V6A5,5 0 0,1 12,1A5,5 0 0,1 17,6V8H18M12,3A3,3 0 0,0 9,6V8H15V6A3,3 0 0,0 12,3Z",
    parking: "M13.2,11H10V7H13.2A2,2 0 0,1 15.2,9A2,2 0 0,1 13.2,11M13,3H6V21H10V15H13A6,6 0 0,0 19,9C19,5.68 16.31,3 13,3Z"
  };

  // --- Styles (shadow DOM), thémés HA + couleurs de marque Vélib' ---
  var STYLE = [
    ":host{display:block;",
    "--elec:#00A9E0;--meca:#82BC00;",
    "--batt-lo:#d64540;--batt-mid:#e9a51b;--batt-hi:#2e9b47;",
    "--metal:#8a9099;--dock:#b8bdc4;--dock-lo:#a4aab1;--dock-hi:#cfd4da;",
    "--card:var(--ha-card-background,var(--card-background-color,#fff));",
    "--fg:var(--primary-text-color,#212121);--muted:var(--secondary-text-color,#70757a);",
    "--faint:var(--disabled-text-color,#9aa0a6);--divider:var(--divider-color,#e4e7ea);",
    "--accent:var(--primary-color,#2b7be4);--chip:var(--secondary-background-color,rgba(127,127,127,.12));}",
    "@media (prefers-color-scheme:dark){:host{",
    "--elec:#2cbdf0;--meca:#9ad21f;--batt-lo:#e85c51;--batt-mid:#f0b63c;--batt-hi:#49c46a;",
    "--metal:#aab0b6;--dock:#5b6066;--dock-lo:#4a4f55;--dock-hi:#71777e;}}",
    "ha-card{display:block;overflow:hidden;color:var(--fg);",
    "background:var(--card);border-radius:var(--ha-card-border-radius,12px);}",
    "*{box-sizing:border-box}",
    ".empty-msg{padding:24px 16px;text-align:center;color:var(--muted);font-size:14px}",
    /* header */
    ".hd{display:flex;align-items:center;gap:13px;padding:14px 16px}",
    ".hd .mk{width:40px;height:40px;border-radius:50%;flex:none;display:grid;place-items:center;",
    "background:color-mix(in srgb,var(--accent) 15%,transparent);color:var(--accent)}",
    ".hd .mk svg{width:23px;height:23px;fill:currentColor}",
    ".hd .ti{min-width:0;flex:1}",
    ".hd .nm{font-size:16px;font-weight:500;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}",
    ".hd .sub{font-size:12px;color:var(--muted);margin-top:1px}",
    ".state{flex:none;font-size:11.5px;font-weight:500;padding:4px 10px;border-radius:999px;background:var(--chip);color:var(--muted)}",
    ".state.alert{background:color-mix(in srgb,var(--batt-lo) 16%,transparent);color:var(--batt-lo)}",
    ".sep{height:1px;background:var(--divider)}",
    /* footer chips */
    ".chips{display:flex;flex-wrap:wrap;gap:8px;padding:13px 16px}",
    ".chip{display:inline-flex;align-items:center;gap:7px;background:var(--chip);border-radius:999px;padding:6px 11px;font-size:13px;font-weight:500}",
    ".chip .dot{width:9px;height:9px;border-radius:50%}",
    ".chip.libre{color:var(--muted)}",
    /* A : scène */
    ".scene{overflow-x:auto;overflow-y:hidden;-webkit-overflow-scrolling:touch;padding:4px 0 2px}",
    ".scene svg{width:100%;height:auto}",
    ".scene svg text{font-family:var(--paper-font-body1_-_font-family,Roboto,sans-serif)}",
    /* B : liste */
    ".row{display:flex;align-items:center;gap:13px;padding:11px 16px}",
    ".row+.row{border-top:1px solid var(--divider)}",
    ".row .ic{width:34px;height:34px;border-radius:9px;flex:none;display:grid;place-items:center;color:#fff}",
    ".row .ic svg{width:22px;height:22px;fill:currentColor}",
    ".row .mid{min-width:0;flex:1}",
    ".row .nb{font-size:14px;font-weight:500;display:flex;align-items:center;gap:7px;flex-wrap:wrap}",
    ".row .meta{font-size:12px;color:var(--muted);margin-top:1px}",
    ".row .right{display:flex;align-items:center;gap:12px;flex:none}",
    ".charge{display:inline-flex;align-items:center;gap:3px;font-size:11px;font-weight:500;color:var(--batt-hi)}",
    ".charge svg{width:12px;height:12px;fill:currentColor}",
    ".row.off{opacity:.5}",
    ".row.off .ic{background:var(--dock)!important}",
    ".battic{width:24px;height:24px;flex:none;fill:currentColor}",
    ".lockpill{display:inline-flex;align-items:center;gap:4px;font-size:11px;color:var(--muted)}",
    ".lockpill svg{width:15px;height:15px;fill:currentColor}",
    ".stars{display:inline-flex;flex:none}",
    ".stars svg{width:15px;height:15px;fill:currentColor}",
    ".stars .on{color:var(--batt-mid)}.stars .offstar{color:var(--divider)}",
    /* D : résumé */
    ".gl{display:flex;gap:10px;padding:15px 16px 8px}",
    ".stat{flex:1;text-align:center;padding:4px 0}",
    ".stat .si{width:22px;height:22px;margin:0 auto 3px;fill:currentColor;display:block}",
    ".stat .v{font-size:25px;font-weight:500;line-height:1.1;font-variant-numeric:tabular-nums}",
    ".stat .k{font-size:11px;color:var(--muted);margin-top:2px}",
    ".occwrap{padding:4px 16px 10px}",
    ".occ{height:9px;border-radius:999px;background:var(--divider);overflow:hidden;display:flex}",
    ".occ span{display:block;height:100%}",
    ".occlbl{display:flex;justify-content:space-between;font-size:11px;color:var(--muted);margin-top:7px}",
    ".sortcap{font-size:10.5px;color:var(--faint);padding:2px 16px 0}",
    ".glance{display:flex;flex-wrap:wrap;gap:8px;padding:4px 16px 15px}",
    ".gpill{display:inline-flex;align-items:center;gap:6px;background:var(--chip);border-radius:999px;padding:5px 10px;font-size:12px;font-weight:500;font-variant-numeric:tabular-nums}",
    ".gpill .dot{width:8px;height:8px;border-radius:50%;flex:none}",
    ".gpill .bat{width:15px;height:15px;fill:currentColor;flex:none}"
  ].join("");

  // --- Définitions SVG réutilisées par la scène A (vélo 3/4 + bornette + icônes) ---
  var DEFS =
    '<defs>' +
    sym("s-batt-out", MDI.battOut) + sym("s-batt-low", MDI.battLow) +
    sym("s-batt-med", MDI.battMed) + sym("s-batt-high", MDI.battHigh) +
    sym("s-batt-chg", MDI.battChg) + sym("s-star", MDI.star) +
    sym("s-star-o", MDI.starO) + sym("s-lock", MDI.lock) +
    '<g id="bikeS">' +
    '<ellipse cx="0" cy="2" rx="33" ry="5" fill="rgba(0,0,0,.13)"/>' +
    '<circle cx="-24" cy="-17" r="17" fill="none" stroke="var(--metal)" stroke-width="3"/>' +
    '<circle cx="-24" cy="-17" r="2.6" fill="var(--metal)"/>' +
    '<circle cx="24" cy="-17" r="17" fill="none" stroke="var(--metal)" stroke-width="3"/>' +
    '<circle cx="24" cy="-17" r="2.6" fill="var(--metal)"/>' +
    '<path d="M2,-18 A22,22 0 0 1 46,-18 L39,-18 A15,15 0 0 0 9,-18 Z" fill="currentColor"/>' +
    '<path d="M-37,-18 A13,13 0 0 1 -11,-18 L-16,-18 A8,8 0 0 0 -32,-18 Z" fill="currentColor"/>' +
    '<path d="M-14,-37 L-24,-17 M0,-17 L-14,-35 M7,-17 L5,-39 M0,-17 L24,-17 M5,-39 L24,-17 M5,-39 Q-6,-30 -14,-36" fill="none" stroke="var(--metal)" stroke-width="3.2" stroke-linecap="round" stroke-linejoin="round"/>' +
    '<circle cx="0" cy="-17" r="3" fill="none" stroke="var(--metal)" stroke-width="2"/>' +
    '<path d="M-3,-40 Q5,-44 13,-40" fill="none" stroke="var(--metal)" stroke-width="4" stroke-linecap="round"/>' +
    '<path d="M-14,-37 L-17,-45" stroke="var(--metal)" stroke-width="3" stroke-linecap="round"/>' +
    '<path d="M-28,-43 Q-18,-50 -10,-44" fill="none" stroke="var(--metal)" stroke-width="3.2" stroke-linecap="round"/>' +
    '<circle cx="-28" cy="-43" r="2.3" fill="var(--metal)"/>' +
    '<path d="M-35,-44 H-15 L-18,-32 H-32 Z" fill="currentColor" fill-opacity=".2" stroke="var(--metal)" stroke-width="2" stroke-linejoin="round"/>' +
    '<path d="M-28,-44 L-27,-32 M-22,-44 L-22,-32 M-33,-38 H-17" stroke="var(--metal)" stroke-width="1.3"/>' +
    '</g>' +
    '<g id="post">' +
    '<path d="M-40,2 L-30,2 L-20,-27 L-28,-27 Z" fill="var(--dock)"/>' +
    '<path d="M-30,2 L-20,-27 L-15,-23 L-25,2 Z" fill="var(--dock-lo)"/>' +
    '<path d="M-28,-27 L-20,-27 L-15,-23 L-23,-23 Z" fill="var(--dock-hi)"/>' +
    '<rect x="-33" y="-24" width="14" height="8" rx="2" fill="var(--dock-lo)"/>' +
    '</g>' +
    '</defs>';

  function sym(id, d) {
    return '<symbol id="' + id + '" viewBox="0 0 24 24"><path fill="currentColor" d="' + d + '"/></symbol>';
  }
  function icon(path, cls, style) {
    return '<svg viewBox="0 0 24 24"' + (cls ? ' class="' + cls + '"' : "") +
      (style ? ' style="' + style + '"' : "") + '><path d="' + path + '"/></svg>';
  }
  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"]/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c];
    });
  }
  function num(v, d) { var n = Number(v); return isFinite(n) ? Math.round(n) : (d == null ? 0 : d); }

  // batterie -> {sym,color}
  function battInfo(b) {
    if (b.charging) return { s: "s-batt-chg", c: "var(--batt-hi)" };
    var lvl = b.battery_level;
    if (lvl == null || lvl <= 0) return { s: "s-batt-out", c: "var(--muted)" };
    if (lvl === 1) return { s: "s-batt-low", c: "var(--batt-lo)" };
    if (lvl === 2) return { s: "s-batt-med", c: "var(--batt-mid)" };
    return { s: "s-batt-high", c: "var(--batt-hi)" };
  }
  function battPath(b) {
    if (b.charging) return MDI.battChg;
    var l = b.battery_level;
    if (l == null || l <= 0) return MDI.battOut;
    if (l === 1) return MDI.battLow;
    if (l === 2) return MDI.battMed;
    return MDI.battHigh;
  }
  function battColor(b) {
    if (b.charging) return "var(--batt-hi)";
    var l = b.battery_level;
    if (l == null || l <= 0) return "var(--muted)";
    if (l === 1) return "var(--batt-lo)";
    if (l === 2) return "var(--batt-mid)";
    return "var(--batt-hi)";
  }
  // étoiles HTML (B et D)
  function starsHTML(rating, label) {
    var r = num(rating, 0), out = '<span class="stars" role="img" aria-label="' +
      (label || ("Note " + r + " sur 3")) + '">';
    for (var i = 1; i <= 3; i++) {
      out += i <= r
        ? '<svg class="on" viewBox="0 0 24 24"><path d="' + MDI.star + '"/></svg>'
        : '<svg class="offstar" viewBox="0 0 24 24"><path d="' + MDI.starO + '"/></svg>';
    }
    return out + "</span>";
  }
  // étoiles SVG <use> (scène A)
  function starsUse(rating, sx, sy) {
    var r = num(rating, 0), out = "";
    for (var j = 0; j < 3; j++) {
      var on = j < r;
      out += '<use href="#' + (on ? "s-star" : "s-star-o") + '" xlink:href="#' + (on ? "s-star" : "s-star-o") +
        '" x="' + (sx + j * 11) + '" y="' + sy + '" width="13" height="13" style="color:' +
        (on ? "var(--batt-mid)" : "var(--divider)") + '"/>';
    }
    return out;
  }
  function useIcon(id, x, y, w, color) {
    return '<use href="#' + id + '" xlink:href="#' + id + '" x="' + x + '" y="' + y +
      '" width="' + w + '" height="' + w + '" style="color:' + color + '"/>';
  }

  // comparateur D : meilleur -> pire
  function bestFirst(a, b) {
    var ra = a.rating == null ? -1 : a.rating, rb = b.rating == null ? -1 : b.rating;
    if (ra !== rb) return rb - ra;                               // 1) note décroissante (null en dernier)
    var da = a.last_rate_date ? Date.parse(a.last_rate_date) : -Infinity;
    var db = b.last_rate_date ? Date.parse(b.last_rate_date) : -Infinity;
    da = isNaN(da) ? -Infinity : da; db = isNaN(db) ? -Infinity : db;
    if (da !== db) return db - da;                               // 2) avis le plus récent
    if (a.type === "electric" && b.type === "electric") {        // 3) batterie (électriques seulement)
      var la = a.battery_level == null ? -1 : a.battery_level, lb = b.battery_level == null ? -1 : b.battery_level;
      if (la !== lb) return lb - la;
    }
    return 0;
  }

  function stateChip(a) {
    var s = a.station_state || a.state_label;
    if (!s) return "";
    var n = String(s).toLowerCase();
    if (n.indexOf("oper") >= 0 || n.indexOf("ouvert") >= 0 || n.indexOf("open") >= 0) return "";
    var alert = n.indexOf("ferm") >= 0 || n.indexOf("clos") >= 0 || n.indexOf("out") >= 0;
    return '<span class="state' + (alert ? " alert" : "") + '">' + esc(s) + "</span>";
  }

  function headerHTML(path, title, sub, a) {
    return '<div class="hd"><div class="mk" aria-hidden="true">' + icon(path) + "</div>" +
      '<div class="ti"><div class="nm">' + esc(title) + "</div>" +
      (sub ? '<div class="sub">' + esc(sub) + "</div>" : "") + "</div>" + stateChip(a) + "</div>";
  }

  // ---------- Layout A : scène réaliste 3/4 ----------
  function buildDocks(a) {
    var bikes = Array.isArray(a.bikes) ? a.bikes : [];
    var cap = a.capacity != null ? num(a.capacity) : (bikes.length + num(a.free_docks, 0));
    var N = Math.max(cap, bikes.length, 1);
    var docks = [], i;
    for (i = 0; i < N; i++) docks.push({ num: ("0" + (i + 1)).slice(-2), bike: null });
    var unplaced = [];
    bikes.forEach(function (b) {
      var idx = b.dock != null ? parseInt(b.dock, 10) - 1 : NaN;
      if (!isNaN(idx) && idx >= 0 && idx < N && !docks[idx].bike) docks[idx].bike = b;
      else unplaced.push(b);
    });
    var fi = 0;
    unplaced.forEach(function (b) {
      while (fi < N && docks[fi].bike) fi++;
      if (fi < N) docks[fi].bike = b;
    });
    return docks;
  }

  function sceneSVG(docks) {
    var N = docks.length, pos = [], x = 64, y = 170, i, s;
    for (i = 0; i < N; i++) { s = Math.max(0.5, Math.pow(0.957, i)); pos.push({ x: x, y: y, s: s }); x += 78 * s; y -= 6.5 * s; }
    var W = Math.round(x + 36);
    var groups = "";
    for (i = N - 1; i >= 0; i--) groups += dockGroup(docks[i], pos[i]);
    return '<div class="scene"><svg viewBox="0 0 ' + W + ' 212" style="min-width:' + W +
      'px" role="img" aria-label="Rangée des bornes de la station, vue en trois-quarts ; faites défiler horizontalement.">' +
      DEFS + groups + "</svg></div>";
  }

  function dockGroup(d, p) {
    var b = d.bike, s = p.s.toFixed(3), inner, badge = "", colorStyle = "";
    if (!b) {
      inner = '<use href="#post" xlink:href="#post"/>';
    } else if (b.available === false) {
      inner = '<g style="color:var(--dock)" opacity=".5"><use href="#bikeS" xlink:href="#bikeS"/></g><use href="#post" xlink:href="#post"/>';
      badge = '<rect x="-12" y="-78" width="28" height="20" rx="10" fill="var(--card)" stroke="var(--divider)"/>' +
        useIcon("s-lock", -8, -75, 16, "var(--muted)");
    } else {
      colorStyle = ' style="color:' + (b.type === "electric" ? "var(--elec)" : "var(--meca)") + '"';
      inner = '<use href="#bikeS" xlink:href="#bikeS"/><use href="#post" xlink:href="#post"/>';
      if (b.type === "electric") {
        var bi = battInfo(b);
        badge = '<rect x="-28" y="-78" width="60" height="20" rx="10" fill="var(--card)" stroke="var(--divider)"/>' +
          useIcon(bi.s, -24, -75, 14, bi.c) + starsUse(b.rating, -5, -74.5);
      } else {
        badge = '<rect x="-19" y="-78" width="42" height="20" rx="10" fill="var(--card)" stroke="var(--divider)"/>' +
          starsUse(b.rating, -15, -74.5);
      }
    }
    var dim = (!b || b.available === false);
    var numFill = dim ? "var(--muted)" : "var(--fg)";
    var subFill = dim ? "var(--faint)" : "var(--muted)";
    var subTxt = b ? "#" + esc(b.number) : "Libre";
    var labels = '<text x="2" y="24" text-anchor="middle" font-size="13" font-weight="500" fill="' + numFill + '">' + d.num + "</text>" +
      '<text x="2" y="35" text-anchor="middle" font-size="10" fill="' + subFill + '">' + subTxt + "</text>";
    return '<g transform="translate(' + p.x.toFixed(1) + "," + p.y.toFixed(1) + ") scale(" + s + ")" + '"' + colorStyle + ">" +
      inner + badge + labels + "</g>";
  }

  // ---------- Layout B : liste native ----------
  function listHTML(a) {
    var bikes = (Array.isArray(a.bikes) ? a.bikes.slice() : []).sort(function (x, y) {
      return (parseInt(x.dock, 10) || 999) - (parseInt(y.dock, 10) || 999);
    });
    if (!bikes.length) return '<div class="empty-msg">Aucun vélo sur cette station pour le moment.</div>';
    return bikes.map(function (b) {
      var elec = b.type === "electric";
      var typeLabel = elec ? "Électrique" : "Mécanique";
      if (b.available === false) {
        return '<div class="row off"><div class="ic" aria-hidden="true">' + icon(MDI.lock, null, "fill:#fff") + "</div>" +
          '<div class="mid"><div class="nb">Vélo ' + esc(b.number) + '</div><div class="meta">' + typeLabel +
          " · borne " + esc(b.dock || "—") + '</div></div>' +
          '<div class="right"><span class="lockpill">' + icon(MDI.lock) + "Indisponible</span></div></div>";
      }
      var ic = '<div class="ic" style="background:' + (elec ? "var(--elec)" : "var(--meca)") + '" aria-hidden="true">' +
        icon(elec ? MDI.bikeE : MDI.bike, null, "fill:#fff") + "</div>";
      var charge = b.charging ? '<span class="charge">' + icon(MDI.battChg) + "en charge</span>" : "";
      var right;
      if (elec) {
        right = '<svg class="battic" viewBox="0 0 24 24" style="color:' + battColor(b) +
          '" role="img" aria-label="Batterie ' + num(b.battery_level, 0) + " sur " + num(b.battery_max, 3) +
          '"><path d="' + battPath(b) + '"/></svg>' + starsHTML(b.rating);
      } else {
        right = '<span class="meta" aria-label="Pas de batterie">—</span>' + starsHTML(b.rating);
      }
      return '<div class="row">' + ic +
        '<div class="mid"><div class="nb">Vélo ' + esc(b.number) + " " + charge + '</div><div class="meta">' +
        typeLabel + " · borne " + esc(b.dock || "—") + "</div></div>" +
        '<div class="right">' + right + "</div></div>";
    }).join("");
  }

  // ---------- Layout D : résumé compact ----------
  function summaryHTML(a, stateNum) {
    var eb = num(a.ebike_available, 0), me = num(a.mechanical_available, 0), fd = num(a.free_docks, 0);
    var bikes = Array.isArray(a.bikes) ? a.bikes : [];
    var cap = a.capacity != null ? num(a.capacity) : (bikes.length + fd);
    var total = cap > 0 ? cap : (eb + me + fd) || 1;
    var ebW = (eb / total * 100), meW = (me / total * 100), fdW = (fd / total * 100);
    var tiles =
      '<div class="gl">' +
      statTile(MDI.bikeE, "var(--elec)", eb, "électriques") +
      statTile(MDI.bike, "var(--meca)", me, "mécaniques") +
      statTile(MDI.parking, "var(--muted)", fd, "bornes libres") +
      "</div>";
    var bar =
      '<div class="occwrap"><div class="occ" role="img" aria-label="Occupation : ' + eb + " électriques, " +
      me + " mécaniques, " + fd + " bornes libres sur " + total + '">' +
      '<span style="width:' + ebW + '%;background:var(--elec)"></span>' +
      '<span style="width:' + meW + '%;background:var(--meca)"></span>' +
      '<span style="width:' + fdW + '%;background:var(--divider)"></span></div>' +
      '<div class="occlbl"><span>' + (eb + me) + " vélos disponibles</span><span>" + total + " bornes</span></div></div>";

    var avail = bikes.filter(function (b) { return b.available !== false; }).sort(bestFirst);
    var pills = "";
    if (avail.length) {
      pills = '<div class="sortcap">Vélos disponibles, du meilleur au moins bon :</div><div class="glance">' +
        avail.map(function (b) {
          var elec = b.type === "electric";
          var bat = elec
            ? '<svg class="bat" viewBox="0 0 24 24" style="color:' + battColor(b) + '"><path d="' + battPath(b) + '"/></svg>'
            : "";
          var title = (elec ? "Électrique" : "Mécanique") +
            (b.rating != null ? " · note " + b.rating + "/3" : " · non noté") +
            (b.last_rate_date ? " · avis " + esc(b.last_rate_date) : "") +
            (elec && b.battery_level != null ? " · batterie " + b.battery_level + "/" + num(b.battery_max, 3) : "");
          return '<span class="gpill" title="' + title + '">' +
            '<i class="dot" style="background:' + (elec ? "var(--elec)" : "var(--meca)") + '"></i>' + esc(b.number) +
            bat + starsHTML(b.rating) + "</span>";
        }).join("") + "</div>";
    }
    return tiles + bar + pills;
  }
  function statTile(path, color, value, label) {
    return '<div class="stat">' + icon(path, "si", "color:" + color) +
      '<div class="v" style="color:' + color + '">' + value + '</div><div class="k">' + label + "</div></div>";
  }

  // --- Custom element ---
  class VelibStationCard extends HTMLElement {
    setConfig(config) {
      if (!config || !config.entity) {
        throw new Error('Carte Vélib\' : veuillez définir "entity" (le capteur de la station).');
      }
      var layout = config.layout || "realistic";
      if (["realistic", "list", "summary"].indexOf(layout) < 0) layout = "realistic";
      this._config = { entity: config.entity, layout: layout, title: config.title || null };
      this._lastKey = null;
      if (!this.shadowRoot) this.attachShadow({ mode: "open" });
    }

    set hass(hass) { this._hass = hass; this._render(); }

    // Éditeur visuel dans l'UI « Ajouter une carte »
    static getConfigElement() {
      return document.createElement("velib-station-card-editor");
    }
    static getStubConfig(hass) {
      var ent = "";
      if (hass && hass.states) {
        ent = Object.keys(hass.states).find(function (e) {
          var s = hass.states[e];
          return e.indexOf("sensor.") === 0 && s && s.attributes && s.attributes.bikes !== undefined;
        }) || "";
      }
      return { entity: ent, layout: "realistic" };
    }

    getCardSize() {
      var l = this._config && this._config.layout;
      if (l === "list") {
        var n = (this._hass && this._config && this._hass.states[this._config.entity] &&
          (this._hass.states[this._config.entity].attributes.bikes || []).length) || 3;
        return 1 + Math.min(n, 12);
      }
      if (l === "summary") return 3;
      return 5;
    }

    _set(html) {
      if (!this.shadowRoot) this.attachShadow({ mode: "open" });
      this.shadowRoot.innerHTML = "<style>" + STYLE + "</style>" + html;
    }

    _render() {
      if (!this._hass || !this._config) return;
      var entity = this._config.entity;
      var st = this._hass.states[entity];
      if (!st) { this._set('<ha-card><div class="empty-msg">Entité « ' + esc(entity) + ' » introuvable.</div></ha-card>'); this._lastKey = null; return; }
      var a = st.attributes || {};
      var layout = this._config.layout;

      if (a.bikes === undefined && a.ebike_available === undefined && a.free_docks === undefined) {
        this._set('<ha-card>' + headerHTML(MDI.bike, this._config.title || a.station_name || "Station Vélib'", null, a) +
          '<div class="empty-msg">En attente de données…</div></ha-card>');
        this._lastKey = null;
        return;
      }

      var key = layout + "|" + st.state + "|" + (st.last_changed || "") + "|" + (a.station_state || "") +
        "|" + JSON.stringify(a.bikes || []) + "|" + a.free_docks + "|" + a.capacity +
        "|" + a.ebike_available + "|" + a.mechanical_available;
      if (key === this._lastKey) return;
      this._lastKey = key;

      var title = this._config.title || a.station_name || "Station Vélib'";
      var stateNum = num(st.state, 0);
      var body;

      if (layout === "list") {
        var subB = [a.ebike_available != null ? a.ebike_available + " élec" : null,
        a.mechanical_available != null ? a.mechanical_available + " méca" : null,
        a.free_docks != null ? a.free_docks + " bornes libres" : null].filter(Boolean).join(" · ");
        body = headerHTML(MDI.bike, title, subB, a) + '<div class="sep"></div>' + listHTML(a);
      } else if (layout === "summary") {
        var subD = a.station_code ? "n° " + a.station_code : null;
        body = headerHTML(MDI.bike, title, subD, a) + summaryHTML(a, stateNum);
      } else {
        var subA = a.station_code ? "Station n° " + a.station_code : null;
        var chips = '<div class="chips">' +
          '<span class="chip"><i class="dot" style="background:var(--elec)"></i>' + num(a.ebike_available, 0) + " élec</span>" +
          '<span class="chip"><i class="dot" style="background:var(--meca)"></i>' + num(a.mechanical_available, 0) + " méca</span>" +
          '<span class="chip libre">' + num(a.free_docks, 0) + " bornes libres</span></div>";
        body = headerHTML(MDI.bike, title, subA, a) + '<div class="sep"></div>' +
          sceneSVG(buildDocks(a)) + '<div class="sep"></div>' + chips;
      }

      this._set("<ha-card>" + body + "</ha-card>");
    }
  }

  // --- Éditeur de configuration (ha-form natif) ---
  var EDITOR_SCHEMA = [
    { name: "entity", required: true, selector: { entity: { domain: "sensor", integration: "velib" } } },
    { name: "layout", selector: { select: { mode: "dropdown", options: [
      { value: "realistic", label: "Réaliste (vue 3/4)" },
      { value: "list", label: "Liste" },
      { value: "summary", label: "Résumé" }
    ] } } },
    { name: "title", selector: { text: {} } }
  ];
  var EDITOR_LABELS = {
    entity: "Capteur de station (Vélos disponibles)",
    layout: "Mise en page",
    title: "Titre (optionnel)"
  };

  class VelibStationCardEditor extends HTMLElement {
    setConfig(config) {
      this._config = Object.assign({ layout: "realistic" }, config || {});
      this._render();
    }
    set hass(hass) { this._hass = hass; this._render(); }
    _render() {
      if (!this._hass || !this._config) return;
      if (!this._form) {
        this._form = document.createElement("ha-form");
        this._form.computeLabel = function (s) { return EDITOR_LABELS[s.name] || s.name; };
        this._form.addEventListener("value-changed", function (ev) {
          ev.stopPropagation();
          this.dispatchEvent(new CustomEvent("config-changed", {
            detail: { config: ev.detail.value }, bubbles: true, composed: true
          }));
        }.bind(this));
        this.appendChild(this._form);
      }
      this._form.hass = this._hass;
      this._form.schema = EDITOR_SCHEMA;
      this._form.data = this._config;
    }
  }
  if (!customElements.get("velib-station-card-editor")) {
    customElements.define("velib-station-card-editor", VelibStationCardEditor);
  }

  if (!customElements.get("velib-station-card")) {
    customElements.define("velib-station-card", VelibStationCard);
  }
  window.customCards = window.customCards || [];
  window.customCards.push({
    type: "velib-station-card",
    name: "Vélib' Station Card",
    description: "Station Vélib' : vélos, batterie, note, état",
    preview: true,
    documentationURL: "https://github.com/antvgr/ha-velib"
  });
  // Bannière console (optionnelle)
  try {
    console.info("%c VELIB-STATION-CARD %c v1.1 ", "background:#00A9E0;color:#fff;border-radius:3px 0 0 3px;padding:2px 4px",
      "background:#82BC00;color:#fff;border-radius:0 3px 3px 0;padding:2px 4px");
  } catch (e) { }
})();
