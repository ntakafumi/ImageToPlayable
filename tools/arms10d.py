"""Hierarchy-based bilateral arm detection; missing arms are failures, not silent fallbacks."""

import numpy as np


def identify_arms(bones, mapping, head_name, height):
    parents = {name: data["parent"] for name, data in bones.items()}
    children = {name: [] for name in bones}
    for name, parent in parents.items():
        if parent in children:
            children[parent].append(name)

    def path_to_root(name):
        path = []
        while name is not None:
            path.append(name)
            name = parents[name]
        return path

    left_path = set(path_to_root(mapping["left"]["thigh"]))
    right_path = set(path_to_root(mapping["right"]["thigh"]))
    trunk = path_to_root(head_name)
    # A coincident helper shared only by the legs is not the torso junction.
    pelvis = next((name for name in trunk if name in left_path and name in right_path), None)
    if pelvis is None:
        raise ValueError("頭と左右の脚に共通する骨盤がありません")
    trunk = trunk[: trunk.index(pelvis) + 1][::-1]

    def descendants(name):
        return [name] + [n for c in children[name] for n in descendants(c)]

    leg_nodes = set()
    for side in ["left", "right"]:
        leg_nodes.update(descendants(mapping[side]["thigh"]))

    # Stored coordinates are Blender Z-up.
    pos = {n: np.asarray(d["head"]) for n, d in bones.items()}
    candidates = {"left": [], "right": []}
    for parent, central in zip(trunk[:-1], trunk[1:]):
        for child in children[parent]:
            if child == central:
                continue
            branch = descendants(child)
            if len(branch) < 3 or set(branch) & leg_nodes:
                continue
            tip = max(branch, key=lambda n: abs(pos[n][0] - pos[parent][0]))
            dx = float(pos[tip][0] - pos[parent][0])
            if (
                abs(dx) < 0.08 * height
                or pos[child][2] < pos[pelvis][2] + 0.06 * height
            ):
                continue
            chain = path_to_root(tip)
            chain = chain[: chain.index(parent)][::-1]
            # Retain all helper bones in the rig, but remove near-coincident
            # endpoints from the anatomical shoulder/elbow/wrist chain.
            filtered = [chain[0]]
            for name in chain[1:]:
                if np.linalg.norm(pos[name] - pos[filtered[-1]]) >= height * 0.015:
                    filtered.append(name)
            chain = filtered
            if len(chain) < 3:
                continue
            length = sum(
                float(np.linalg.norm(pos[b] - pos[a]))
                for a, b in zip([parent] + chain, chain)
            )
            side = "left" if dx > 0 else "right"
            candidates[side].append((abs(dx), child, branch, chain, length))
    result = {}
    for side in ["left", "right"]:
        if not candidates[side]:
            raise ValueError(
                side
                + "側の独立した腕の骨格がありません。両腕のある別の推定候補が必要です"
            )
        _, root, branch, chain, length = max(candidates[side], key=lambda item: item[0])
        # A collarbone can be long in a stylized character. Identify its central
        # origin and outward path to the shoulder, not just its absolute length.
        first_length = (
            np.linalg.norm(pos[chain[1]] - pos[root]) if len(chain) > 1 else 0
        )
        chest = pos[parents[root]]
        root_lateral = abs(pos[root][0] - chest[0])
        child_lateral = (
            abs(pos[chain[1]][0] - chest[0]) if len(chain) > 1 else root_lateral
        )
        outward = child_lateral - root_lateral
        vertical = abs(pos[chain[1]][2] - pos[root][2]) if len(chain) > 1 else 0
        short_collar = len(chain) > 2 and first_length < 0.045 * height
        spatial_collar = (
            len(chain) > 2
            and root_lateral < 0.12 * height
            and outward > 0.05 * height
            and outward > vertical
        )
        upper = chain[1] if short_collar or spatial_collar else root
        start = chain.index(upper)
        moving_chain = chain[start:]
        moving_length = sum(
            float(np.linalg.norm(pos[b] - pos[a]))
            for a, b in zip(moving_chain, moving_chain[1:])
        )
        if moving_length < 0.03 * height:
            raise ValueError(side + "側の腕の長さを確認できません")
        result[side] = dict(
            root=root,
            upper=upper,
            branch=branch,
            chain=chain,
            moving_branch=descendants(upper),
            length=moving_length,
            upper_selection=(
                "spatial_collarbone"
                if spatial_collar
                else "short_collarbone" if short_collar else "branch_root"
            ),
        )
    if set(result["left"]["branch"]) & set(result["right"]["branch"]):
        raise ValueError("左右の腕の枝が重なっています")
    return dict(pelvis=pelvis, trunk=trunk, arms=result)
