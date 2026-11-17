"""Full-amplitude Taka direction retarget; no global attenuation or source geometry."""

from pathlib import Path
import argparse, copy, json, hashlib, zipfile
import numpy as np
from scipy.spatial.transform import Rotation
from scipy.spatial import cKDTree
from glb10 import GLB, trs, digest


def worlds(g, props=None):
    nodes = g.nodes if props is None else props
    parents = {c: i for i, n in enumerate(g.nodes) for c in n.get("children", [])}
    result = {}

    def get(i):
        if i not in result:
            n = nodes[i]
            m = (
                np.array(n["matrix"]).reshape(4, 4).T
                if "matrix" in n
                else trs(
                    n.get("translation", [0, 0, 0]),
                    n.get("rotation", [0, 0, 0, 1]),
                    n.get("scale", [1, 1, 1]),
                )
            )
            result[i] = get(parents[i]) @ m if i in parents else m
        return result[i]

    for i in range(len(nodes)):
        get(i)
    return result


def rot(m):
    u, _, v = np.linalg.svd(m[:3, :3])
    r = u @ v
    if np.linalg.det(r) < 0:
        u[:, -1] *= -1
        r = u @ v
    return r


def aim(a, b):
    a = np.asarray(a, float)
    b = np.asarray(b, float)
    a /= np.linalg.norm(a)
    b /= np.linalg.norm(b)
    axis = np.cross(a, b)
    s = np.linalg.norm(axis)
    d = np.clip(a @ b, -1, 1)
    if s < 1e-9:
        if d > 0:
            return np.eye(3)
        axis = np.cross(a, [1, 0, 0] if abs(a[0]) < 0.9 else [0, 1, 0])
        axis /= np.linalg.norm(axis)
    else:
        axis /= s
    return Rotation.from_rotvec(axis * np.arctan2(s, d)).as_matrix()


def save_rotations(g, props, rotations, rest, order):
    for i, target in [(i, rotations[i]) for i in order if i in rotations]:
        w = worlds(g, props)
        p = g.parents.get(i)
        # Remove parent scale before expressing a world rotation in the local frame.
        parent = rot(w[p]) if p is not None else np.eye(3)
        props[i].pop("matrix", None)
        props[i]["rotation"] = (
            Rotation.from_matrix(parent.T @ target).as_quat().tolist()
        )


def extract_zip(source, out):
    out.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(source) as z:
        for f in [
            "character.glb",
            "character.json",
            "animation-report.json",
            "arms-report.json",
        ]:
            (out / f).write_bytes(z.read("character/" + f))


def mapping(g, report):
    from semantic10l import check_roles
    check_roles(report)
    names = {n.get("name"): i for i, n in enumerate(g.nodes)}
    rest = worlds(g)
    roles = {}
    endpoints = {}
    for side, m in report["mapping"].items():
        arm = report["arm_anatomy"]["arms"][side]
        chain = arm["chain"]
        ui = chain.index(m["arm"])
        upper = m["arm"]
        # Inferred rigs may insert coincident shoulder helpers. Keep them in
        # the hierarchy/skin, but do not assign them anatomical segment roles.
        minimum = float(report["height"]) * 0.015
        anatomical = [upper]
        for name in chain[ui + 1:]:
            distance = np.linalg.norm(rest[names[name]][:3,3] - rest[names[anatomical[-1]]][:3,3])
            if distance >= minimum:
                anatomical.append(name)
        if len(anatomical) < 3:
            raise ValueError(side + ": no non-degenerate shoulder/elbow/wrist chain")
        fore = anatomical[1]
        hand = anatomical[2]
        for role, a, b in [
            ("thigh", m["thigh"], m["knee"]),
            ("knee", m["knee"], m["foot"]),
            ("arm", upper, fore),
            ("forearm", fore, hand),
        ]:
            roles[side + "_" + role] = names[a]
            endpoints[names[a]] = names[b]
        foot = names[m["foot"]]
        kids = g.nodes[foot].get("children", [])
        if kids:
            roles[side + "_foot"] = foot
            endpoints[foot] = max(
                kids, key=lambda j: np.linalg.norm(rest[j][:3, 3] - rest[foot][:3, 3])
            )
    return roles, endpoints


def repair_weights(g, report, roles, ends, mechanical=False):
    """Localize influences at limb joints; keep bind vertices, texture and head unchanged."""
    rest = worlds(g)
    changes = []
    for ni, p, raw, faces in g.primitives:
        skin = g.meta["skins"][g.nodes[ni]["skin"]]
        nodes = skin["joints"]
        idx = {n: i for i, n in enumerate(nodes)}
        j = g.acc(p["attributes"]["JOINTS_0"]).astype(int)
        w = g.acc(p["attributes"]["WEIGHTS_0"]).astype(float)
        dense = np.zeros((len(raw), len(nodes)))
        np.add.at(dense, (np.arange(len(raw))[:, None], j), w)
        original = dense.copy()
        pts = (
            g.pose()[0][g.primitives.index((ni, p, raw, faces))][1]
            if len(g.primitives) > 1
            else g.pose()[0][0][1]
        )
        h = np.ptp(pts[:, 1])
        changed = np.zeros(len(pts), bool)
        for side, m in report["mapping"].items():
            for group, rolekeys in [
                ("arm", ["arm", "forearm"]),
                ("leg", ["thigh", "knee"]),
            ]:
                a, b = [roles[side + "_" + k] for k in rolekeys]
                c = ends[b]
                # Existing branch membership protects the face, torso, opposite limbs and details.
                branch = []
                todo = [a]
                while todo:
                    n = todo.pop()
                    branch.append(n)
                    todo.extend(g.nodes[n].get("children", []))
                membership = original[:, [idx[n] for n in branch if n in idx]].sum(1)
                mask = membership > 0.55
                A, B, C = [rest[n][:3, 3] for n in [a, b, c]]
                axis = C - A
                length = np.linalg.norm(axis)
                axis /= length
                along = (pts - B) @ axis
                width = (0.045 if mechanical else 0.065) * h
                t = np.clip((along + width) / (2 * width), 0, 1)
                t = t * t * (3 - 2 * t)
                local = np.zeros_like(dense)
                local[:, idx[a]] = 1 - t
                local[:, idx[b]] = t
                if group == "leg":
                    # Foot is allowed to follow its own source direction; preserve its rigid sole.
                    footmass = original[:, idx[c]]
                    footmask = mask & (footmass > 0.5)
                    local[footmask] = 0
                    local[footmask, idx[c]] = 1
                # Soft characters retain the existing skin away from the joint band.
                band = mask & (abs(along) < width * 2)
                strength = np.clip((membership - 0.55) / 0.3, 0, 1) * np.clip(
                    (width * 2 - abs(along)) / width, 0, 1
                )
                dense[band] = (
                    dense[band] * (1 - strength[band, None])
                    + local[band] * strength[band, None]
                )
                changed |= band
        # Diffuse abrupt influences only in the corrected joint bands and their immediate neighbours.
        tree = cKDTree(pts)
        dist, near = tree.query(pts, k=10)
        eligible = changed[near].any(1) & (dist[:, -1] < h * 0.025)
        for _ in range(4):
            mean = dense[near].mean(1)
            dense[eligible] = 0.65 * dense[eligible] + 0.35 * mean[eligible]
        # UV split vertices at the same bind location must have identical transforms.
        key = np.round(pts, 5)
        _, inv = np.unique(key, axis=0, return_inverse=True)
        count = np.bincount(inv)
        sums = np.zeros((len(count), len(nodes)))
        np.add.at(sums, inv, dense)
        seam = count[inv] > 1
        dense[seam] = (sums / count[:, None])[inv[seam]]
        top = np.argsort(-dense, axis=1)[:, :4]
        weights = np.take_along_axis(dense, top, axis=1)
        weights /= weights.sum(1, keepdims=True)
        # New inverse bind blend: preserve the visible bind shape exactly after reweighting.
        ibm = g.acc(skin["inverseBindMatrices"]).reshape(-1, 4, 4).transpose(0, 2, 1)
        mats = np.stack([rest[n] for n in nodes]) @ ibm
        M = np.sum(mats[top] * weights[:, :, None, None], axis=1)
        vertices = np.linalg.solve(M, np.c_[pts, np.ones(len(pts))][:, :, None])[
            :, :3, 0
        ]
        p["attributes"]["POSITION"] = g.add_acc(vertices, "VEC3")
        p["attributes"]["JOINTS_0"] = g.add_acc(top.astype("<u2"), "VEC4", 5123)
        p["attributes"]["WEIGHTS_0"] = g.add_acc(weights, "VEC4")
        changes.append(
            dict(
                vertices_changed=int(changed.sum()),
                total_vertices=len(pts),
                method="joint-local mechanical panels"
                if mechanical
                else "joint-local soft transition",
                texture_unchanged=True,
            )
        )
    return changes


def transfer(source, reference, out, mechanical=False, repair=True):
    source = Path(source)
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    report = json.loads((source / "animation-report.json").read_text())
    info = json.loads((source / "character.json").read_text())
    ref = json.loads(Path(reference).read_text())
    g = GLB(source / "character.glb")
    g.parents = {c: i for i, n in enumerate(g.nodes) for c in n.get("children", [])}
    roles, ends = mapping(g, report)
    corrections = repair_weights(g, report, roles, ends, mechanical) if repair else []
    g.write(out / "bind-corrected.glb")
    g = GLB(out / "bind-corrected.glb")
    g.parents = {c: i for i, n in enumerate(g.nodes) for c in n.get("children", [])}
    roles, ends = mapping(g, report)
    g.meta["animations"] = []
    rest = worlds(g)

    def depth(i):
        return 1 + depth(g.parents[i]) if i in g.parents else 0

    names = {n.get("name"): i for i, n in enumerate(g.nodes)}
    trunk = report["arm_anatomy"]["trunk"]
    pelvis = report["arm_anatomy"]["pelvis"]
    compact = report.get("profile") == "compact"
    bodymap = {names[pelvis]: "pelvis"}
    if not compact:
        bodymap[names[trunk[-1]]] = "head"
        if not mechanical and len(trunk) >= 5:
            bodymap.update({names[trunk[2]]: "spine", names[trunk[3]]: "chest"})
    neutral = ref["clips"]["Idle_preview"]["frames"][0]["orientation"]
    order = sorted(set(roles.values()) | set(bodymap), key=depth)
    root = next(i for i, n in enumerate(g.nodes) if n.get("name") == "Armature")
    rootbase = np.array(g.nodes[root].get("translation", [0, 0, 0]), float)
    pr = g.parents.get(root)
    rootparent = rest[pr][:3, :3] if pr is not None else np.eye(3)
    basepositions = np.concatenate([p for _, p in g.pose()[0]])
    height = float(np.ptp(basepositions[:, 1]))
    floor = float(basepositions[:, 1].min())
    source_sha = digest(source / "character.glb")
    summaries = []
    info["game_profile"] = ref.get("gait_profile", {})
    for name, clip in ref["clips"].items():
        frames = clip["frames"]
        times = np.linspace(0, clip["duration"], len(frames))
        values = {i: [] for i in order}
        direction_errors = []
        for frame in frames:
            props = copy.deepcopy(g.nodes)
            # The robot casing stays rigid; the cat also receives the source spine/chest motion.
            for i, key in sorted(bodymap.items(), key=lambda kv: depth(kv[0])):
                w = worlds(g, props)
                parent = g.parents.get(i)
                pr = rot(w[parent]) if parent is not None else np.eye(3)
                desired = (
                    np.array(frame["orientation"][key])
                    @ np.array(neutral[key]).T
                    @ rot(rest[i])
                )
                q = Rotation.from_matrix(pr.T @ desired).as_quat()
                if values[i] and np.dot(values[i][-1], q) < 0:
                    q = -q
                values[i].append(q)
                props[i]["rotation"] = q.tolist()
            for role, i in sorted(roles.items(), key=lambda kv: depth(kv[1])):
                w = worlds(g, props)
                endpoint = ends[i]
                current = w[endpoint][:3, 3] - w[i][:3, 3]
                target = np.array(frame[role])
                desired = aim(current, target) @ rot(w[i])
                parent = g.parents.get(i)
                parentrot = rot(w[parent]) if parent is not None else np.eye(3)
                q = Rotation.from_matrix(parentrot.T @ desired).as_quat()
                if values[i] and np.dot(values[i][-1], q) < 0:
                    q = -q
                props[i]["rotation"] = q.tolist()
                values[i].append(q)
            w = worlds(g, props)
            for role, i in roles.items():
                d = w[ends[i]][:3, 3] - w[i][:3, 3]
                d /= np.linalg.norm(d)
                direction_errors.append(
                    float(
                        np.degrees(np.arccos(np.clip(d @ np.array(frame[role]), -1, 1)))
                    )
                )
        anim = dict(name=name, samplers=[], channels=[])
        ta = g.add_acc(times[:, None], "SCALAR")
        for i in order:
            oa = g.add_acc(values[i], "VEC4")
            anim["samplers"].append(dict(input=ta, output=oa, interpolation="LINEAR"))
            anim["channels"].append(
                dict(
                    sampler=len(anim["samplers"]) - 1,
                    target=dict(node=i, path="rotation"),
                )
            )
        translations = []
        minimums = []
        for f, t in enumerate(times):
            pts = np.concatenate([p for _, p in g.pose(anim, float(t))[0]])
            bottom = float(pts[:, 1].min())
            minimums.append(bottom)
            # Contact lift is independent of the authored limb rotations.
            lift = max(0.0, floor - bottom)
            if name == "Jump_preview":
                u = f / (len(times) - 1)
                trajectory = clip["flight_samples"]
                lift += float(
                    np.interp(u, np.linspace(0, 1, len(trajectory)), trajectory)
                )
            body = clip["frames"][f]["body_translation"]
            # Keep horizontal locomotion in the player; retain only Taka's vertical body bob.
            body_y = body[1] - min(x["body_translation"][1] for x in clip["frames"])
            if name != "Jump_preview":
                lift += max(0.0, body_y)
            translations.append(
                rootbase + np.linalg.solve(rootparent, np.array([0, lift, 0]))
            )
        oa = g.add_acc(translations, "VEC3")
        anim["samplers"].append(dict(input=ta, output=oa, interpolation="LINEAR"))
        anim["channels"].append(
            dict(
                sampler=len(anim["samplers"]) - 1,
                target=dict(node=root, path="translation"),
            )
        )
        g.meta["animations"].append(anim)
        summaries.append(
            dict(
                name=name,
                maximum_direction_error_degrees=max(direction_errors),
                global_amplitude=1.0,
                local_angle_limits={},
                maximum_contact_correction=max(0.0, floor - min(minimums)),
            )
        )
        print(
            name,
            "full amplitude; max direction error",
            round(max(direction_errors), 5),
            flush=True,
        )
    g.meta["asset"].setdefault("extras", {}).update(
        motion="Actual Taka game clip direction transfer",
        motion_license="CC-BY-4.0",
        motion_attribution="Taka tuned game-motion reference by Takafumi Nakanishi",
        motion_license_url="https://creativecommons.org/licenses/by/4.0/",
        global_amplitude=1.0,
        jump="original game discrete physics, baked once",
    )
    g.write(out / "character.glb")
    info.update(
        output_sha256=digest(out / "character.glb"),
        locomotion="Taka actual game clips + game jump physics",
        motion_license="CC-BY-4.0",
        motion_attribution="Taka tuned game-motion reference by Takafumi Nakanishi",
        label=source.name,
        validation_passed=False,
        scope="Full source directions retained; validation-report.json gives geometry checks",
        motion_reference_sha256=digest(reference),
    )
    for name, clip in ref["clips"].items():
        mode = name.split("_")[0].lower()
        info["modes"].setdefault(mode, {}).update(
            method="taka-game-retarget10j",
            cycle_seconds=clip["duration"],
            suggested_speed=clip["game_speed"] / max(clip["game_rate"], 1e-8),
            vertical_motion=name == "Jump_preview",
            game_rate=clip["game_rate"],
            speed_method="Taka natural-gait reference speed; target foot-contact IK is not applied",
        )
    report["input_motion_amplitudes"] = report.get("per_clip_arm_amplitudes", {})
    report["per_clip_arm_amplitudes"] = {name: 1.0 for name in ref["clips"]}
    report["per_clip_leg_amplitudes"] = {name: 1.0 for name in ref["clips"]}
    info["mode_provenance"] = {
        name.split("_")[0].lower(): dict(
            method="taka-game-retarget10j",
            source_clip=clip.get("source_runtime", "authored clip"),
            global_amplitude=1.0,
        )
        for name, clip in ref["clips"].items()
    }
    info["rigging_status"] = "predicted_biped_with_taka_motion"
    report.update(
        source_glb_sha256=source_sha,
        source_motion_sha256=ref["source_model_sha256"],
        transfer_mapping={k: g.nodes[v]["name"] for k, v in roles.items()},
        full_amplitude=True,
        joint_weight_corrections=corrections,
        clips=summaries,
    )
    (out / "animation-report.json").write_text(json.dumps(report, indent=2))
    (out / "character.json").write_text(json.dumps(info, indent=2))
    (out / "arms-report.json").write_text(
        json.dumps(
            dict(
                both_arms_present=True,
                validation_passed=False,
                method="Taka direction transfer",
                clips=summaries,
            ),
            indent=2,
        )
    )
    return report


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--source", type=Path, required=True)
    p.add_argument("--reference", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--mechanical", action="store_true")
    p.add_argument("--no-repair", action="store_true")
    a = p.parse_args()
    transfer(a.source, a.reference, a.out, a.mechanical, not a.no_repair)
