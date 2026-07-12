#!/usr/bin/env python3
# Copyright (c) 2026 Dr. Yoram Segal / Gal Technologies Artificial Intelligence Ltd. (GTAI).
# All rights reserved. Educational Use EULA - see LICENSE. Contact: segal@gal-tech.ai
"""Render the README GUI images from a saved match log (dev/docs tool, Pillow).

Reconstructs the belief heatmap exactly like the Replay player and draws the
board with BoardView's colours, then composes (1) a heatmap-progression figure
and (2) a fully annotated GUI screenshot. Run: uv run python scripts/render_docs_images.py
"""
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from police_thief.domain.belief import BeliefGrid

LOG = Path("logs/police_match.json")
OUT = Path("docs/images")
GRID = json.loads(Path("config/police/game.json").read_text())["board_and_agents"]["grid_size"]
CELL = 46
POLICE, THIEF, INK = "#2980b9", "#e67e22", "#263238"


def font(size, bold=False):
    return ImageFont.truetype("arialbd.ttf" if bold else "arial.ttf", size)


def heat(prob, peak):
    if peak <= 0:
        return (255, 255, 255)
    gb = int(255 * (1 - 0.8 * min(1.0, prob / peak)))
    return (255, gb, gb)


def reconstruct(summary, upto):
    """State AFTER `upto` moves: belief matrix, my position, visited, barriers."""
    belief = BeliefGrid(GRID)
    barriers, visited, pos = set(), set(), None
    for h in summary["history"][:upto]:
        belief.diffuse()
        belief.observe_smell(h["smell_grid"])
        if h.get("barrier_placed"):
            barriers.add(tuple(h["barrier_placed"]))
    for entry in summary["my_log"][:upto]:
        pos = tuple(entry["position"])
        visited.add(pos)
        if entry.get("barrier"):
            barriers.add(tuple(entry["barrier"]))
    return belief.as_matrix(), pos, visited, barriers


def draw_board(draw, ox, oy, matrix, pos, visited, barriers, role):
    peak = max((p for row in matrix for p in row), default=0.0)
    for r in range(GRID):
        for c in range(GRID):
            x0, y0 = ox + c * CELL, oy + r * CELL
            draw.rectangle([x0, y0, x0 + CELL, y0 + CELL],
                           fill=heat(matrix[r][c], peak), outline="#cccccc")
    for (r, c) in visited:
        x0, y0 = ox + c * CELL, oy + r * CELL
        draw.ellipse([x0 + 18, y0 + 18, x0 + CELL - 18, y0 + CELL - 18], fill="#b0bec5")
    for (r, c) in barriers:
        x0, y0 = ox + c * CELL, oy + r * CELL
        draw.rectangle([x0 + 5, y0 + 5, x0 + CELL - 5, y0 + CELL - 5], fill=INK)
    if pos is not None:
        r, c = pos
        x0, y0 = ox + c * CELL, oy + r * CELL
        col = POLICE if role == "police" else THIEF
        draw.ellipse([x0 + 7, y0 + 7, x0 + CELL - 7, y0 + CELL - 7],
                     fill=col, outline="black", width=2)
        draw.text((x0 + CELL / 2, y0 + CELL / 2), role[0].upper(), fill="white",
                  font=font(18, True), anchor="mm")
    draw.rectangle([ox, oy, ox + GRID * CELL, oy + GRID * CELL], outline="#888888", width=2)


def peak_cell(matrix):
    best, bp = (0, 0), -1.0
    for r in range(GRID):
        for c in range(GRID):
            if matrix[r][c] > bp:
                best, bp = (r, c), matrix[r][c]
    return best


def progression(summary):
    side = GRID * CELL
    img = Image.new("RGB", (3 * side + 4 * 26, side + 96), "white")
    d = ImageDraw.Draw(img)
    d.text((26, 16), "Belief heatmap sharpening over one game (Police view) — "
           "redder = more likely the thief is there", fill=INK, font=font(15, True))
    role = summary["role"]
    for i, (step, cap) in enumerate([(4, "Early: belief still diffuse"),
                                     (17, "Mid: belief concentrating"),
                                     (33, "Late: a hot cell (best guess)")]):
        m, pos, vis, bar = reconstruct(summary, step)
        ox = 26 + i * (side + 26)
        draw_board(d, ox, 52, m, pos, vis, bar, role)
        pr, pc = peak_cell(m)
        d.text((ox, 52 + side + 8), f"step {step} · {cap}", fill=INK, font=font(13, True))
        d.text((ox, 52 + side + 28), f"peak cell ({pr},{pc})", fill="#666", font=font(12))
    img.save(OUT / "heatmap-progression.png")


def gui(summary):
    step = 17
    m, pos, vis, bar = reconstruct(summary, step)
    rec = [r for r in summary["records"] if r["payload"].get("step") == step][0]["payload"]
    side = GRID * CELL
    img = Image.new("RGB", (1120, side + 275), "#f4f4f4")
    d = ImageDraw.Draw(img)
    # (1) banner
    d.rectangle([20, 18, 700, 54], fill="#2ecc71")
    d.text((360, 36), "MY TURN - thinking...", fill="white", font=font(15, True), anchor="mm")
    # (2) board
    draw_board(d, 20, 70, m, pos, vis, bar, summary["role"])
    # (3) info panel
    px = 40 + side
    rows = [("Step", str(step)), ("Model", rec.get("model", "-")),
            ("Tokens step / total", f"{rec['tokens_step']:,} / {rec['tokens_total']:,}"),
            ("LLM response (s)", f"{rec['response_seconds']:.2f}"),
            ("Barriers used", f"{len(bar)} / 14"),
            ("Opponent says", summary["history"][step - 1]["hint"]),
            ("I said", rec["hint"]), ("My verdict", rec["verdict"]),
            ("My commit (sealed)", rec["commit"] if isinstance(rec.get("commit"), str)
             else summary["records"][step]["commit"][:26] + "..."),
            ("Status", "Agreement signed & verified")]
    y = 70
    for cap, val in rows:
        d.text((px, y), cap + ":", fill=INK, font=font(11, True))
        d.text((px, y + 15), str(val)[:42], fill="#333", font=font(11))
        y += 40
    # (4) speed slider
    d.text((px, y), "Step time budget (sec)  [0 = no LLM]", fill=INK, font=font(11, True))
    d.line([px, y + 24, px + 250, y + 24], fill="#888", width=3)
    d.ellipse([px + 122, y + 17, px + 138, y + 33], fill=POLICE)
    d.text((px, y + 34), "0", fill="#666", font=font(10))
    d.text((px + 240, y + 34), "60", fill="#666", font=font(10))
    # (5) buttons
    by = y + 66
    for i, name in enumerate(["Pause", "Play", "Stop"]):
        bx = 20 + i * 92
        d.rectangle([bx, by, bx + 82, by + 30], fill="#dddddd", outline="#999")
        d.text((bx + 41, by + 15), name, fill=INK, font=font(12, True), anchor="mm")
    d.rectangle([20 + 3 * 92, by, 20 + 3 * 92 + 150, by + 30], fill="#dddddd", outline="#999")
    d.text((20 + 3 * 92 + 75, by + 15), "About / System spec", fill=INK,
           font=font(11, True), anchor="mm")
    # numbered callouts
    p_x = 20 + pos[1] * CELL + CELL // 2 if pos else 20 + side // 2
    p_y = 70 + pos[0] * CELL + CELL // 2 if pos else 70 + side // 2
    for n, (x, cy) in [("1", (686, 36)), ("2", (p_x, p_y)),
                       ("3", (px - 8, 78)), ("4", (px - 8, y + 24)), ("5", (30, by + 15))]:
        d.ellipse([x - 11, cy - 11, x + 11, cy + 11], fill="#c0392b")
        d.text((x, cy), n, fill="white", font=font(12, True), anchor="mm")
    img.save(OUT / "gui-annotated.png")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    summary = json.loads(LOG.read_text(encoding="utf-8"))["summary"]
    progression(summary)
    gui(summary)
    print("wrote", OUT / "heatmap-progression.png", "and", OUT / "gui-annotated.png")


if __name__ == "__main__":
    main()
