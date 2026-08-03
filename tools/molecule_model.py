#!/usr/bin/env python3
"""Build a 3D molecular model of the OpenTrader codebase.

Each module = an atom (color-coded by role); each dependency/import = a bond.
Emits a PDB molecule file (renderable in any molecular viewer AND buildable
with a physical molecular-model kit) plus a legend/recipe for the physical
build and a 3D preview.

Usage: python3 -m tools.molecule_model
"""

import json
import os
import random
import re
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
OUT = PROJECT / "data"
random.seed(7)

# ── 1. Dependency graph (top-level modules) ──
MODULES = ["harness.py", "mcp_server.py", "dashboard.py", "tui_dashboard.py",
           "mot", "exchange", "risk", "setup_search", "training", "data",
           "state", "agent", "tools", "charts", "scripts", "coordinator.py",
           "connections.py", "model_manager.py", "onchain.py", "gpu_sync.py",
           "run_harness.py", "tests", "data_mgmt.py"]

ROLE = {  # module -> color role for the physical kit
    "harness.py": "hub", "mcp_server.py": "service", "dashboard.py": "ui",
    "tui_dashboard.py": "ui", "mot": "agents", "exchange": "data-io",
    "risk": "risk", "setup_search": "research", "training": "training",
    "data": "core", "state": "core", "agent": "agents", "tools": "util",
    "charts": "ui", "scripts": "util", "coordinator.py": "training",
    "connections.py": "core", "model_manager.py": "training", "onchain.py": "data-io",
    "gpu_sync.py": "service", "run_harness.py": "service", "tests": "util",
    "data_mgmt.py": "core",
}
COLOR = {
    "hub": "#e63946", "service": "#457b9d", "ui": "#a8dadc", "agents": "#f4a261",
    "data-io": "#2a9d8f", "risk": "#e9c46a", "research": "#9b5de5", "training": "#f15bb5",
    "core": "#4cc9f0", "util": "#8d99ae",
}
ELEMENT = {  # element letter per module (for the PDB)
    m: "C" if ROLE[m] == "core" else "N" if ROLE[m] == "hub" else
       "O" if ROLE[m] == "agents" else "S" if ROLE[m] in ("data-io", "risk") else
       "P" if ROLE[m] in ("training", "research") else "F"
    for m in MODULES
}


def build_graph():
    deps = {m: set() for m in MODULES}
    for root in MODULES:
        files = []
        if os.path.isdir(PROJECT / root):
            files = [str(PROJECT / root / f) for f in os.listdir(PROJECT / root) if f.endswith(".py")]
        elif (PROJECT / root).exists():
            files = [str(PROJECT / root)]
        for f in files:
            try:
                src = open(f, encoding="utf-8", errors="ignore").read()
            except Exception:
                continue
            for m in MODULES:
                if m == root:
                    continue
                pat = re.compile(r"\b(from\s+" + re.escape(m) + r"|import\s+" +
                                 re.escape(m) + r"[\\.\s]|\bfrom\s+" +
                                 re.escape(m.replace("/", ".")) + r"\b)")
                if pat.search(src):
                    deps[root].add(m)
    return deps


# ── 2. Force-directed 3D layout ──
def layout(deps):
    nodes = list(MODULES)
    idx = {m: i for i, m in enumerate(nodes)}
    pos = {m: [random.uniform(-1, 1), random.uniform(-1, 1), random.uniform(-1, 1)] for m in nodes}
    edges = set()
    for a, bs in deps.items():
        for b in bs:
            edges.add(tuple(sorted((idx[a], idx[b]))))
    for _ in range(400):
        forces = {m: [0.0, 0.0, 0.0] for m in nodes}
        for i in range(len(nodes)):
            for j in range(i + 1, len(nodes)):
                a, b = nodes[i], nodes[j]
                d = sum((pos[a][k] - pos[b][k]) ** 2 for k in range(3)) ** 0.5 + 1e-6
                f = 0.02 / d ** 2  # repulsion
                for k in range(3):
                    forces[a][k] += f * (pos[a][k] - pos[b][k]) / d
                    forces[b][k] += f * (pos[b][k] - pos[a][k]) / d
        for (i, j) in edges:
            a, b = nodes[i], nodes[j]
            d = sum((pos[a][k] - pos[b][k]) ** 2 for k in range(3)) ** 0.5 + 1e-6
            f = 0.01 * (d - 1.0)  # spring
            for k in range(3):
                forces[a][k] += f * (pos[b][k] - pos[a][k]) / d
                forces[b][k] += f * (pos[a][k] - pos[b][k]) / d
        for m in nodes:
            for k in range(3):
                pos[m][k] += forces[m][k]
    # normalize
    xs = [pos[m][0] for m in nodes]; ys = [pos[m][1] for m in nodes]; zs = [pos[m][2] for m in nodes]
    maxv = max(max(abs(x) for x in xs), max(abs(y) for y in ys), max(abs(z) for z in zs))
    for m in nodes:
        pos[m] = [v / maxv for v in pos[m]]
    return nodes, edges, pos


def write_pdb(nodes, edges, pos, out):
    lines = []
    atom_i = 1
    for i, m in enumerate(nodes, 1):
        el = ELEMENT[m]
        name = (m[:4] + ".").ljust(5) if len(m) > 4 else (m + " ").ljust(5)
        lines.append(f"HETATM{atom_i:5d} {name:5s} {m[:4].upper():3s} MOL     1    "
                     f"{pos[m][0]:8.3f}{pos[m][1]:8.3f}{pos[m][2]:8.3f}  1.00  0.00          {el:>2s}")
        atom_i += 1
    for i, j in edges:
        lines.append(f"CONECT{i:5d}{j:5d}")
    out.write_text("\n".join(lines) + "\n")


def write_xyz(nodes, pos, out):
    lines = [str(len(nodes)), "OpenTrader codebase molecule"]
    for m in nodes:
        lines.append(f"{ELEMENT[m]:2s} {pos[m][0]:8.3f} {pos[m][1]:8.3f} {pos[m][2]:8.3f} {m}")
    out.write_text("\n".join(lines) + "\n")


def write_legend(nodes, edges, pos, out):
    lines = ["# OpenTrader codebase — physical molecular model recipe",
             "",
             "Build a ball-and-stick model: each **module is a colored atom**, each",
             "**dependency (import) is a bond stick**. Colors match the render.",
             "",
             "## Atoms (modules)", "", "| # | Atom (module) | Role | Element | Kit color |", "|---|---------------|------|---------|-----------|"]
    for i, m in enumerate(nodes, 1):
        lines.append(f"| {i} | {m} | {ROLE[m]} | {ELEMENT[m]} | {COLOR[ROLE[m]]} |")
    lines += ["", "## Bonds (dependencies)", ""]
    for i, j in sorted(edges):
        lines.append(f"- {nodes[i]} → {nodes[j]}")
    lines += ["", "## Color legend", ""]
    for role, c in COLOR.items():
        lines.append(f"- {role}: {c}")
    out.write_text("\n".join(lines) + "\n")


def render(nodes, edges, pos):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from mpl_toolkits.mplot3d import Axes3D  # noqa
        fig = plt.figure(figsize=(12, 10))
        ax = fig.add_subplot(111, projection="3d")
        for (i, j) in edges:
            a, b = nodes[i], nodes[j]
            ax.plot([pos[a][0], pos[b][0]], [pos[a][1], pos[b][1]],
                    [pos[a][2], pos[b][2]], color="#999", lw=1.2, alpha=0.6)
        for i, m in enumerate(nodes):
            ax.scatter(*pos[m], s=500, c=COLOR[ROLE[m]], depthshade=True,
                       edgecolors="black", linewidths=1)
            ax.text(pos[m][0] * 1.18, pos[m][1] * 1.18, pos[m][2] * 1.18, m, fontsize=7)
        ax.set_axis_off()
        plt.tight_layout()
        plt.savefig(OUT / "codebase_molecule.png", dpi=150, bbox_inches="tight")
        print("render -> data/codebase_molecule.png")
    except Exception as e:
        print("render skipped:", e)


def write_html(nodes, edges, pos, out):
    atoms = [{"n": m, "c": COLOR[ROLE[m]], "x": pos[m][0], "y": pos[m][1], "z": pos[m][2],
              "r": ROLE[m]} for m in nodes]
    bonds = [[i, j] for (i, j) in edges]
    import html as _h
    data = json.dumps({"atoms": atoms, "bonds": bonds}).replace("</", "<\\/")
    page = _h.escape(open("/tmp/mol_template.html").read() if __import__("os").path.exists("/tmp/mol_template.html") else "", quote=False)
    # build template inline
    template = """<!DOCTYPE html><html><head><meta charset="utf-8"><title>OpenTrader codebase molecule</title>
<style>body{margin:0;font-family:monospace;background:#111;color:#eee} #info{position:fixed;top:8px;left:8px;font-size:12px;z-index:5;background:#000a;padding:8px;border-radius:6px}</style></head>
<body><div id="info">OpenTrader codebase — rotate/zoom. Atoms = modules (colored by role), bonds = imports. Use this to guide the physical molecular-kit build.</div>
<script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/controls/OrbitControls.js"></script>
<script>
var DATA = __DATA__;
var scene = new THREE.Scene();
var camera = new THREE.PerspectiveCamera(60, innerWidth/innerHeight, 0.1, 100);
camera.position.set(0,0,6);
var renderer = new THREE.WebGLRenderer({antialias:true});
renderer.setSize(innerWidth, innerHeight);
document.body.appendChild(renderer.domElement);
var controls = new THREE.OrbitControls(camera, renderer.domElement);
new THREE.AmbientLight(0xffffff, 0.6);
var dl = new THREE.DirectionalLight(0xffffff, 0.8); dl.position.set(5,5,5); scene.add(dl);
var nodes = DATA.atoms.map(function(a){
  var m = new THREE.Mesh(new THREE.SphereGeometry(0.28, 24, 24),
    new THREE.MeshPhongMaterial({color: new THREE.Color(a.c)}));
  m.position.set(a.x*2.4, a.y*2.4, a.z*2.4); m.userData={n:a.n};
  scene.add(m); return m; });
DATA.bonds.forEach(function(b){
  var p1=nodes[b[0]].position, p2=nodes[b[1]].position;
  var d=p2.clone().sub(p1); var len=d.length();
  var cyl=new THREE.Mesh(new THREE.CylinderGeometry(0.03,0.03,len,6),
    new THREE.MeshPhongMaterial({color:0x999999}));
  cyl.position.copy(p1).add(d.clone().multiplyScalar(0.5));
  cyl.quaternion.setFromUnitVectors(new THREE.Vector3(0,1,0), d.normalize());
  scene.add(cyl); });
function animate(){ requestAnimationFrame(animate); controls.update(); renderer.render(scene,camera); }
animate();
</script></body></html>"""
    template = template.replace("__DATA__", data)
    out.write_text(template)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    deps = build_graph()
    nodes, edges, pos = layout(deps)
    write_pdb(nodes, edges, pos, OUT / "codebase_molecule.pdb")
    write_xyz(nodes, pos, OUT / "codebase_molecule.xyz")
    write_legend(nodes, edges, pos, OUT / "codebase_molecule_recipe.md")
    render(nodes, edges, pos)
    write_html(nodes, edges, pos, OUT / "codebase_molecule.html")
    print(f"PDB: {len(nodes)} atoms, {len(edges)} bonds")
    print("legend -> data/codebase_molecule_recipe.md")


if __name__ == "__main__":
    main()
