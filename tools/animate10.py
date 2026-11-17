"""Normalize the bind pose and infer semantic roles. Does not create motion clips."""

from pathlib import Path
import argparse, json
import bpy, numpy as np
from mathutils import Vector


def main(
    source,
    out,
    profile="humanoid",
    amplitude=1.0,
    amplitudes=None,
    arm_amplitude=1.0,
    arm_amplitudes=None,
):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=str(source))
    arms = [o for o in bpy.context.scene.objects if o.type == "ARMATURE"]
    meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]
    if len(arms) != 1 or not meshes:
        raise ValueError("1つのスキン骨格が必要です")
    arm = arms[0]
    arm.animation_data_clear()
    bpy.context.view_layer.update()
    # Blender's glTF importer creates an unskinned Icosphere for bone display. It
    # must never participate in character bounds, floor tests, or output geometry.
    meshes = [
        o
        for o in meshes
        if any(m.type == "ARMATURE" and m.object == arm for m in o.modifiers)
        and len(o.vertex_groups) > 0
    ]
    for o in list(bpy.context.scene.objects):
        if o.type == "MESH" and o not in meshes:
            bpy.data.objects.remove(o, do_unlink=True)
    if not meshes:
        raise ValueError("スキンに接続された本体メッシュがありません")
    pts = [o.matrix_world @ Vector(c) for o in meshes for c in o.bound_box]
    lo = Vector([min(v[i] for v in pts) for i in range(3)])
    hi = Vector([max(v[i] for v in pts) for i in range(3)])
    h = hi.z - lo.z
    center = (lo + hi) / 2
    info = {}
    for pb in arm.pose.bones:
        q = arm.matrix_world @ pb.bone.head_local
        t = arm.matrix_world @ pb.bone.tail_local
        info[pb.name] = dict(
            head=list(q), tail=list(t), parent=pb.parent.name if pb.parent else None
        )

    def head(pb):
        return arm.matrix_world @ pb.bone.head_local

    # Each leg is traced from a low joint back toward the central trunk.
    mapped = {}
    for side, sign in [("left", 1), ("right", -1)]:
        eligible = [
            p
            for p in arm.pose.bones
            if sign * (head(p).x - center.x) > 0.025 * h and head(p).z < lo.z + 0.55 * h
        ]
        if not eligible:
            mapped[side] = dict(thigh=None, knee=None, foot=None, leg_chain=[])
            continue
        foot = min(eligible, key=lambda p: head(p).z)
        chain = []
        p = foot
        while (
            p
            and sign * (head(p).x - center.x) > 0.02 * h
            and head(p).z < lo.z + 0.64 * h
        ):
            chain.append(p)
            p = p.parent
        chain = chain[::-1]
        # Drop toe-level terminal segments while retaining hip -> knee -> ankle.
        if len(chain) < 2:
            mapped[side] = dict(thigh=None, knee=None, foot=None, leg_chain=[])
            continue
        thigh = chain[0]
        knee = chain[1]
        ankle = chain[2] if len(chain) > 2 else None
        mapped[side] = dict(
            thigh=thigh.name,
            knee=knee.name,
            foot=ankle.name if ankle else None,
            leg_chain=[p.name for p in chain],
        )
        candidates = [
            p
            for p in arm.pose.bones
            if 0.12 * h < sign * (head(p).x - center.x) < 0.36 * h
            and lo.z + 0.42 * h < head(p).z < lo.z + 0.83 * h
            and p.children
        ]
        if candidates:
            upper = min(candidates, key=lambda p: abs(head(p).x - center.x))
            mapped[side]["arm"] = upper.name
    # Regularize spatially isolated weight jumps on the welded surface graph.
    # This operates on the inferred mesh, independent of motion name or character ID.
    from scipy.sparse import coo_matrix, diags

    weight_changes = []
    for o in meshes:
        names = [p.name for p in arm.pose.bones]
        lookup = {n: i for i, n in enumerate(names)}
        w = np.zeros((len(o.data.vertices), len(names)))
        for v in o.data.vertices:
            for g in v.groups:
                n = o.vertex_groups[g.group].name
                if n in lookup:
                    w[v.index, lookup[n]] = g.weight
        original = w.copy()
        edge = np.array([e.vertices[:] for e in o.data.edges], dtype=int)
        if len(edge):
            rows = np.r_[edge[:, 0], edge[:, 1], np.arange(len(w))]
            cols = np.r_[edge[:, 1], edge[:, 0], np.arange(len(w))]
            a = coo_matrix(
                (np.ones(len(rows)), (rows, cols)), shape=(len(w), len(w))
            ).tocsr()
            a = diags(1 / np.asarray(a.sum(1)).ravel()) @ a
            for iteration in range(3):
                w = 0.65 * w + 0.35 * (a @ w)
        keep = np.argsort(w, axis=1)[:, -4:]
        mask = np.zeros_like(w, dtype=bool)
        np.put_along_axis(mask, keep, True, axis=1)
        w[~mask] = 0
        w[w < 0.015] = 0
        total = w.sum(1)
        if (total < 1e-8).any():
            raise ValueError("重みを保持できない頂点があります")
        w /= total[:, None]
        weight_changes.append(float(np.abs(w - original).sum(1).mean()))
        ids = list(range(len(w)))
        for group in o.vertex_groups:
            group.remove(ids)
        groups = [o.vertex_groups.get(n) or o.vertex_groups.new(name=n) for n in names]
        for vi, bi in zip(*np.nonzero(w)):
            groups[bi].add([int(vi)], float(w[vi, bi]), "REPLACE")
    # Preserve the face as one rigid region; the inferred head is selected by upper-region weights.
    cutoff = lo.z + h * (0.76 if profile == "humanoid" else 0.68)
    scores = {}
    for o in meshes:
        for v in o.data.vertices:
            if (o.matrix_world @ v.co).z >= cutoff:
                for g in v.groups:
                    n = o.vertex_groups[g.group].name
                    if n in arm.pose.bones:
                        scores[n] = scores.get(n, 0) + g.weight
    if not scores:
        raise ValueError("頭部の重みを確認できません")
    headname = max(scores, key=scores.get)
    # Validate the semantic roles before creating any clips. A raised arm or an
    # asymmetric silhouette must not turn a shared pelvis into a thigh.
    from topology10 import repair_roles
    from types import SimpleNamespace

    bone_names = list(info)
    bone_index = {name: i for i, name in enumerate(bone_names)}
    adapter_nodes = [
        dict(
            name=name,
            children=[bone_index[c.name] for c in arm.pose.bones[name].children],
        )
        for name in bone_names
    ]
    adapter_parents = {
        bone_index[name]: bone_index[data["parent"]]
        for name, data in info.items()
        if data["parent"] is not None
    }
    adapter_points = np.array([[v.x, v.z, -v.y] for v in pts])
    adapter_rest = {}
    for name, data in info.items():
        matrix = np.eye(4)
        x, y, z = data["head"]
        matrix[:3, 3] = [x, z, -y]
        adapter_rest[bone_index[name]] = matrix
    adapter = SimpleNamespace(
        nodes=adapter_nodes,
        parents=adapter_parents,
        meta={"skins": [{"joints": list(range(len(bone_names)))}]},
        pose=lambda: ([(None, adapter_points)], None),
    )
    role_report, role_repair = repair_roles(
        adapter, adapter_rest, dict(mapping=mapped, head_bone=headname), h
    )
    mapped = role_report["mapping"]
    from arms10d import identify_arms

    arm_anatomy = identify_arms(info, mapped, headname, h)
    arm_names = {
        name for side in arm_anatomy["arms"].values() for name in side["branch"]
    }
    for side, data in arm_anatomy["arms"].items():
        mapped[side]["arm"] = data["upper"]
    from semantic10l import check_roles
    check_roles(dict(mapping=mapped, arm_anatomy=arm_anatomy))
    changed = 0
    for o in meshes:
        group = o.vertex_groups.get(headname) or o.vertex_groups.new(name=headname)
        for v in o.data.vertices:
            influences = {o.vertex_groups[g.group].name: g.weight for g in v.groups}
            arm_weight = sum(w for n, w in influences.items() if n in arm_names)
            # Do not freeze raised or short arms merely because they are high in the image.
            if (
                (o.matrix_world @ v.co).z >= cutoff
                and arm_weight < 0.15
                and influences.get(headname, 0) > 0.15
            ):
                for g in list(v.groups):
                    o.vertex_groups[g.group].remove([v.index])
                group.add([v.index], 1.0, "REPLACE")
                changed += 1
    # Normalize under a non-animated parent, preserving object and skin bind matrices.
    root = bpy.data.objects.new("AvatarRoot", None)
    bpy.context.collection.objects.link(root)
    for o in list(bpy.context.scene.objects):
        if o != root and o.parent is None:
            m = o.matrix_world.copy()
            o.parent = root
            o.matrix_world = m
    height = 2.2 if profile == "humanoid" else 1.25
    scale = height / h
    root.scale = (scale, scale, scale)
    root.location = (-center.x * scale, -center.y * scale, -lo.z * scale)
    bpy.context.view_layer.update()
    # Export the normalized bind pose only. Taka motion is added in the next stage.
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.export_scene.gltf(filepath=str(out / "character.glb"), export_format="GLB",
        export_animations=False, export_cameras=False, export_lights=False)
    report = dict(arm_anatomy=arm_anatomy,role_repair=role_repair,
        weight_regularization=dict(iterations=3,neighbor_blend=.35,mean_l1_change=weight_changes),
        profile=profile,height=height,mapping=mapped,bones=info,head_bone=headname,
        head_vertices_rigidified=changed,head_cutoff_normalized=(cutoff-lo.z)/h)
    (out / "animation-report.json").write_text(json.dumps(report,indent=2))
    (out / "character.json").write_text(json.dumps(dict(modes={name:{} for name in
        ["idle","walk","jog","run","jump"]},height=height,validation_passed=False),indent=2))
    print("Normalized bind pose and semantic mapping exported",flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True);p.add_argument('--profile',choices=['humanoid','compact'],default='humanoid')
    a=p.parse_args();main(a.source,a.out,a.profile)
