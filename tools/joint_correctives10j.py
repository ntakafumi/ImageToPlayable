"""Pose-space, joint-local stretch repair. Bone tracks are retained byte-for-byte."""

from pathlib import Path
import json, argparse
import numpy as np
from scipy.spatial import cKDTree
from scipy.linalg import svd
from glb10 import GLB, digest
from transfer10j import worlds, mapping


def sparse_acc(g, indices, values, total):
    values = np.asarray(values, dtype="<f4")
    indices = np.asarray(indices, dtype="<u4")
    ia = g.add_acc(indices[:, None], "SCALAR", 5125)
    va = g.add_acc(values, "VEC3")
    i = g.meta["accessors"][ia]
    v = g.meta["accessors"][va]
    a = dict(
        componentType=5126,
        count=total,
        type="VEC3",
        sparse=dict(
            count=len(indices),
            indices=dict(bufferView=i["bufferView"], componentType=5125),
            values=dict(bufferView=v["bufferView"]),
        ),
    )
    g.meta["accessors"].append(a)
    return len(g.meta["accessors"]) - 1


def correct(folder):
    folder = Path(folder)
    g = GLB(folder / "character.glb")
    if len(g.primitives) != 1:
        raise ValueError("10J corrective currently requires one skinned primitive")
    ar = json.loads((folder / "animation-report.json").read_text())
    roles, ends = mapping(g, ar)
    ni, p, raw, faces = g.primitives[0]
    base = g.pose()[0][0][1]
    h = np.ptp(base[:, 1])
    rest = worlds(g)
    # Only anatomical joint neighbourhoods can receive a mesh correction.
    jointnodes = set(roles.values()) - set(
        roles[s + "_foot"] for s in ["left", "right"] if s + "_foot" in roles
    )
    jointcenters = np.array([rest[n][:3, 3] for n in jointnodes])
    nearjoint = cKDTree(jointcenters).query(base)[0] < h * 0.14
    # Keep the head and visible hands/soles untouched.
    skin = g.meta["skins"][g.nodes[ni]["skin"]]
    ji = g.acc(p["attributes"]["JOINTS_0"]).astype(int)
    bw = g.acc(p["attributes"]["WEIGHTS_0"])
    head_name = ar["arm_anatomy"]["trunk"][-1]
    head = next(i for i, n in enumerate(g.nodes) if n.get("name") == head_name)
    hi = skin["joints"].index(head)
    headmass = ((ji == hi) * bw).sum(1)
    nearjoint &= headmass < 0.3
    # Weld UV split vertices for the positional solve.
    _, first, inv = np.unique(
        np.round(base, 5), axis=0, return_index=True, return_inverse=True
    )
    B = base[first]
    mask = nearjoint[first]
    f = inv[faces]
    e = np.unique(
        np.sort(np.concatenate([f[:, [0, 1]], f[:, [1, 2]], f[:, [0, 2]]]), axis=1),
        axis=0,
    )
    e = e[e[:, 0] != e[:, 1]]
    length = np.linalg.norm(B[e[:, 0]] - B[e[:, 1]], axis=1)
    valid = length > h * 1e-5
    e = e[valid]
    length = length[valid]
    # Repair large growth; tiny triangles are also constrained in a small joint patch.
    cap = np.maximum(length * 1.45, length + h * 0.0025)
    ibm = g.acc(skin["inverseBindMatrices"]).reshape(-1, 4, 4).transpose(0, 2, 1)
    deltas = []
    samples = []
    tracks = []
    posecache = {}
    maxmove = 0.0
    maxerror = 0.0
    affected = set()
    for clip in g.meta["animations"]:
        times = np.unique(
            np.concatenate([g.acc(s["input"]).ravel() for s in clip["samplers"]])
        )
        if len(times) > 31:
            times = np.linspace(times[0], times[-1], 31)
        track = []
        for time in times:
            pp, props = g.pose(clip, float(time))
            key = tuple(np.round(np.array([p["rotation"] for p in props]).ravel(), 5))
            if key in posecache:
                local = posecache[key]
                ids = np.where(np.linalg.norm(local, axis=1) > 1e-7)[0]
                affected.update(ids.tolist())
                deltas.append(local)
                track.append(len(deltas) - 1)
                continue
            P = pp[0][1]
            V = P[first].copy()
            initial = V.copy()
            lengths = np.linalg.norm(V[e[:, 0]] - V[e[:, 1]], axis=1)
            hot = lengths > cap
            active = np.zeros(len(V), bool)
            active[e[hot].ravel()] = True
            for _ in range(2):
                active[e[active[e].any(1)].ravel()] = True
            active &= mask
            edges = e[active[e].any(1)]
            caps = cap[active[e].any(1)]
            movable = active.astype(float)
            A = edges[:, 0]
            C = edges[:, 1]
            den = movable[A] + movable[C]
            keep = den > 0
            A = A[keep]
            C = C[keep]
            caps = caps[keep]
            den = den[keep]
            degree = np.bincount(np.r_[A, C], minlength=len(V))
            degree = np.maximum(1, degree)
            for iteration in range(12):
                d = V[C] - V[A]
                L = np.linalg.norm(d, axis=1)
                excess = np.maximum(0, L - caps)
                if excess.max(initial=0) < h * 0.0003:
                    break
                correction = d * (excess / np.maximum(L, 1e-10) / den)[:, None]
                accum = np.zeros_like(V)
                np.add.at(accum, A, correction * movable[A, None])
                np.add.at(accum, C, -correction * movable[C, None])
                V += accum / degree[:, None] * 0.95
            move = V - initial
            # Limit correction region rather than shrinking animation tracks.
            sizes = np.linalg.norm(move, axis=1)
            clamp = np.minimum(1, h * 0.11 / np.maximum(sizes, 1e-10))
            move *= clamp[:, None]
            target = P + move[inv]
            maxmove = max(maxmove, float(np.linalg.norm(move, axis=1).max()))
            w = worlds(g, props)
            mats = np.stack([w[n] for n in skin["joints"]]) @ ibm
            M = np.sum(mats[ji] * bw[:, :, None, None], axis=1)
            local = np.linalg.solve(M[:, :3, :3], (target - P)[:, :, None])[:, :, 0]
            ids = np.where(np.linalg.norm(local, axis=1) > 1e-7)[0]
            affected.update(ids.tolist())
            posecache[key] = local
            deltas.append(local)
            track.append(len(deltas) - 1)
        tracks.append((clip, times, track))
        print("Joint corrective sampled:", clip["name"], flush=True)
    ids = np.array(sorted(affected))
    D = np.array([d[ids].reshape(-1) for d in deltas], dtype=np.float64)
    if not len(ids):
        ar["pose_correctives"] = dict(vertices=0, bone_tracks_unchanged=True)
        (folder / "animation-report.json").write_text(json.dumps(ar, indent=2))
        return
    U, S, V = svd(D, full_matrices=False, check_finite=False)
    energy = np.cumsum(S * S) / max(float((S * S).sum()), 1e-20)
    rank = min(64, len(S))
    for candidate in range(min(16, len(S)), min(64, len(S)) + 1, 4):
        residual = ((U[:, :candidate] * S[:candidate]) @ V[:candidate] - D).reshape(
            len(D), len(ids), 3
        )
        if np.linalg.norm(residual, axis=2).max() < h * 0.0015:
            rank = candidate
            break
    bases = V[:rank].reshape(rank, len(ids), 3)
    weights = U[:, :rank] * S[:rank]
    error = float(
        np.linalg.norm(
            (weights @ V[:rank] - D).reshape(len(D), len(ids), 3), axis=2
        ).max()
    )
    p["targets"] = [
        dict(POSITION=sparse_acc(g, ids, basis, len(raw))) for basis in bases
    ]
    mesh = g.meta["meshes"][g.nodes[ni]["mesh"]]
    mesh["weights"] = [0.0] * rank
    g.nodes[ni]["weights"] = [0.0] * rank
    mesh.setdefault("extras", {})["targetNames"] = [
        "JointCorrective_" + str(i) for i in range(rank)
    ]
    for clip, times, track in tracks:
        ti = g.add_acc(times[:, None], "SCALAR")
        oi = g.add_acc(weights[track].reshape(-1, 1), "SCALAR")
        clip["samplers"].append(dict(input=ti, output=oi, interpolation="LINEAR"))
        clip["channels"].append(
            dict(
                sampler=len(clip["samplers"]) - 1, target=dict(node=ni, path="weights")
            )
        )
    g.write(folder / "character.glb")
    ar["pose_correctives"] = dict(
        vertices=len(ids),
        total_vertices=len(raw),
        basis_count=rank,
        retained_energy=float(energy[rank - 1]),
        max_compression_error_world_approx=error,
        maximum_joint_displacement=maxmove,
        bone_tracks_unchanged=True,
        global_amplitude=1.0,
        scope="joint neighbourhoods only; no hand/head correction; no rotation attenuation",
    )
    (folder / "animation-report.json").write_text(json.dumps(ar, indent=2))
    info = json.loads((folder / "character.json").read_text())
    info["output_sha256"] = digest(folder / "character.glb")
    (folder / "character.json").write_text(json.dumps(info, indent=2))
    print(ar["pose_correctives"], flush=True)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--folder", type=Path, required=True)
    a = p.parse_args()
    correct(a.folder)
