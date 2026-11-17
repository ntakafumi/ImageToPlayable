from pathlib import Path
import json, argparse
import numpy as np
from glb10 import GLB, digest
from transfer10j import worlds, mapping


def validate(folder, original):
    folder = Path(folder)
    g = GLB(folder / "character.glb")
    old = GLB(Path(original) / "character.glb")
    ar = json.loads((folder / "animation-report.json").read_text())
    roles, ends = mapping(g, ar)
    rest = worlds(g)
    poses = g.pose()[0]
    h = np.ptp(np.concatenate([p for _, p in poses])[:, 1])
    head = next((i for i, n in enumerate(g.nodes) if n.get("name") == "bone_5"), None)
    edges = []
    restlen = []
    for (_, p, raw, f), (_, points) in zip(g.primitives, poses):
        e = np.unique(
            np.sort(np.concatenate([f[:, [0, 1]], f[:, [1, 2]], f[:, [0, 2]]]), axis=1),
            axis=0,
        )
        length = np.linalg.norm(points[e[:, 0]] - points[e[:, 1]], axis=1)
        e = e[length > h * 1e-5]
        edges.append(e)
        restlen.append(length[length > h * 1e-5])
    reports = []
    for c in g.meta["animations"]:
        d = g.duration(c)
        p99 = 1.0
        maxratio = 1.0
        fraction = 0.0
        miny = 1e9
        lowest = []
        max_edge_over_height = 0.0
        handpaths = {s: [] for s in ["left", "right"]}
        feet = {s: [] for s in ["left", "right"]}
        for t in np.linspace(0, d, max(2, round(d * 30) + 1)):
            samples, props = g.pose(c, float(t))
            w = worlds(g, props)
            vals = []
            for (_, P), e, L in zip(samples, edges, restlen):
                r = np.linalg.norm(P[e[:, 0]] - P[e[:, 1]], axis=1) / L
                vals.append(r)
                lengths = np.linalg.norm(P[e[:, 0]] - P[e[:, 1]], axis=1)
                max_edge_over_height = max(max_edge_over_height, float(lengths.max()/h))
                miny = min(miny, float(P[:, 1].min()))
            ratios = np.concatenate(vals)
            p99 = max(p99, float(np.quantile(ratios, 0.99)))
            maxratio = max(maxratio, float(ratios.max()))
            fraction = max(fraction, float(np.mean(ratios > 2)))
            lowest.append(min(float(p[:, 1].min()) for _, p in samples))
            for s in ["left", "right"]:
                upper = roles[s + "_arm"]
                wrist = ends[roles[s + "_forearm"]]
                hip = roles[s + "_thigh"]
                foot = ends[roles[s + "_knee"]]
                handpaths[s].append((w[wrist][:3, 3] - w[upper][:3, 3]).tolist())
                feet[s].append((w[foot][:3, 3] - w[hip][:3, 3]).tolist())
        reports.append(
            dict(
                name=c["name"],
                max_edge_over_height=max_edge_over_height,
                edge_ratio_p99=p99,
                max_edge_ratio=maxratio,
                fraction_edges_over_2=fraction,
                min_y=miny,
                sole_peak=max(lowest),
                hand_forward_span={
                    s: float(np.ptp(np.array(v)[:, 2])) for s, v in handpaths.items()
                },
                foot_vertical_span_relative_hip={
                    s: float(np.ptp(np.array(v)[:, 1])) for s, v in feet.items()
                },
            )
        )
    textures = [
        digest_bytes(
            bytes(g.binary[v["byteOffset"] : v["byteOffset"] + v["byteLength"]])
        )
        for im in g.meta.get("images", [])
        for v in [g.meta["bufferViews"][im["bufferView"]]]
    ]
    oldtextures = [
        digest_bytes(
            bytes(old.binary[v["byteOffset"] : v["byteOffset"] + v["byteLength"]])
        )
        for im in old.meta.get("images", [])
        for v in [old.meta["bufferViews"][im["bufferView"]]]
    ]
    # Calibrate only the root's constant ground offset; preserve every bone angle and stride.
    root = next(i for i, n in enumerate(g.nodes) if n.get("name") == "Armature")
    rest_world = worlds(g)
    parent = g.parents.get(root)
    matrix = rest_world[parent][:3, :3] if parent is not None else np.eye(3)
    ground_offsets = {}
    for clip, record in zip(g.meta["animations"], reports):
        offset = max(0.0, record["min_y"])
        if clip["name"] != "Jump_preview" and offset > 0.001:
            channel = next(
                ch
                for ch in clip["channels"]
                if ch["target"].get("node") == root
                and ch["target"]["path"] == "translation"
            )
            sampler = clip["samplers"][channel["sampler"]]
            values = g.acc(sampler["output"]).copy()
            values -= np.linalg.solve(matrix, np.array([0.0, offset, 0.0]))
            sampler["output"] = g.add_acc(values, "VEC3")
            record["min_y"] -= offset
            record["sole_peak"] -= offset
            ground_offsets[clip["name"]] = offset
    if ground_offsets:
        g.write(folder / "character.glb")
        ar["constant_ground_offsets"] = ground_offsets
        (folder / "animation-report.json").write_text(json.dumps(ar, indent=2))
    accepted = all(
        c["edge_ratio_p99"] < 1.7
        and c["fraction_edges_over_2"] < 0.04
        and c["min_y"] > -0.005
        and c["max_edge_over_height"] < 0.20
        for c in reports
    )
    foot_bound = max(ar.get("foot_frame_calibration", {}).get("rotation_degrees", {}).values(), default=0.0)
    direction_passed = all(c.get("maximum_direction_error_degrees", 180) + foot_bound < 45 for c in ar["clips"])
    accepted = accepted and direction_passed
    result = dict(
        direction_gate_passed=direction_passed,
        source_sha256=digest(Path(original) / "character.glb"),
        output_sha256=digest(folder / "character.glb"),
        texture_bytes_identical=textures == oldtextures,
        global_amplitude=1.0,
        clips=reports,
        numeric_gate_passed=accepted,
        scope="Finite poses, 30fps mesh edge strain, floor, joint excursions; no universal collision or visual guarantee",
    )
    (folder / "validation-report.json").write_text(json.dumps(result, indent=2))
    info = json.loads((folder / "character.json").read_text())
    info.update(
        validation_passed=accepted, clips=reports, output_sha256=result["output_sha256"]
    )
    (folder / "character.json").write_text(json.dumps(info, indent=2))
    print("数値検査:", folder.name, "合格" if accepted else "要確認", flush=True)
    for record in reports:
        print(
            record["name"],
            "伸長p99=",
            round(record["edge_ratio_p99"], 3),
            "床の最低位置=",
            round(record["min_y"], 5),
            flush=True,
        )
    return result


def digest_bytes(b):
    import hashlib

    return hashlib.sha256(b).hexdigest()


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--folder", type=Path, required=True)
    p.add_argument("--original", type=Path, required=True)
    a = p.parse_args()
    validate(a.folder, a.original)
