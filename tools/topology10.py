"""Repair inconsistent biped roles using hierarchy, without changing skin or mesh."""

import copy
import numpy as np


def repair_roles(g, rest, report, height):
    result = copy.deepcopy(report)
    names = {n.get("name"): i for i, n in enumerate(g.nodes)}
    joints = {i for skin in g.meta["skins"] for i in skin["joints"]}

    def descendants(node):
        return {node} | {
            j for c in g.nodes[node].get("children", []) for j in descendants(c)
        }

    subtree = {i: descendants(i) & joints for i in joints}
    roles = report["mapping"]
    thighs = [names.get(roles[s].get("thigh")) for s in ["left", "right"]]
    invalid = any(i is None for i in thighs)
    if not invalid:
        invalid = thighs[0] in subtree[thighs[1]] or thighs[1] in subtree[thighs[0]]
    # Independent branches alone do not establish that they are legs.
    if not invalid:
        points0 = np.concatenate([p for _, p in g.pose()[0]])
        bottom0 = float(points0[:, 1].min())
        for side, thigh in zip(["left", "right"], thighs):
            chain = roles[side].get("leg_chain", [])
            branch = subtree[thigh]
            origin = rest[thigh][:3, 3]
            invalid |= len(chain) > 12
            invalid |= max(rest[j][1, 3] for j in branch) > origin[1] + 0.08 * height
            invalid |= min(rest[j][1, 3] for j in branch) > bottom0 + 0.20 * height
    if not invalid:
        return result, {
            "changed": False,
            "reason": "左右の脚が独立した枝にあるため既存の対応を保持",
        }
    points = np.concatenate([p for _, p in g.pose()[0]])
    bottom = float(points[:, 1].min())

    def head(i):
        return rest[i][:3, 3]

    leaves = {i for i in joints if not (set(g.nodes[i].get("children", [])) & joints)}
    candidates = []
    for pelvis in joints:
        if not bottom + 0.25 * height < head(pelvis)[1] < bottom + 0.66 * height:
            continue
        branches = []
        for child in g.nodes[pelvis].get("children", []):
            if child not in joints:
                continue
            low = [
                i
                for i in subtree[child] & leaves
                if head(i)[1] < bottom + 0.20 * height
            ]
            if (
                not low
                or max(head(i)[1] for i in subtree[child])
                > head(pelvis)[1] + 0.08 * height
            ):
                continue
            tip = min(low, key=lambda i: head(i)[1])
            chain, node = [], tip
            while node != pelvis:
                chain.append(node)
                node = g.parents.get(node)
                if node is None:
                    raise ValueError("脚の階層を確認できません")
            chain.reverse()
            if 3 <= len(chain) <= 12:
                branches.append(chain)
        for a in range(len(branches)):
            for b in range(a + 1, len(branches)):
                ca, cb = branches[a], branches[b]
                separation = abs(head(ca[0])[0] - head(cb[0])[0]) / height
                if separation > 0.04:
                    candidates.append((separation, pelvis, ca, cb))
    if not candidates:
        raise ValueError(
            "左右の脚の対応が不整合で、独立した接地枝を確認できません。誤った骨を動かさず停止します。"
        )
    _, pelvis, ca, cb = max(candidates, key=lambda v: v[0])
    ordered = sorted([ca, cb], key=lambda chain: head(chain[0])[0], reverse=True)
    # The path to the protected head defines the central trunk. At each fork,
    # lateral branches are arms; the neck/head branch cannot become a forearm.
    head_node = names.get(report.get("head_bone"))
    if head_node not in subtree[pelvis]:
        raise ValueError("頭部と骨盤のつながりを確認できません")
    trunk, node = [], head_node
    while node != pelvis:
        trunk.append(node)
        node = g.parents.get(node)
        if node is None:
            raise ValueError("頭部の階層が不整合です")
    trunk.append(pelvis)
    trunk.reverse()
    arm_candidates = {"left": [], "right": []}
    leg_nodes = set(ca + cb)
    for index, node in enumerate(trunk[:-1]):
        next_node = trunk[index + 1]
        for child in g.nodes[node].get("children", []):
            if child == next_node or child in leg_nodes or child not in joints:
                continue
            lateral = max(subtree[child], key=lambda i: abs(head(i)[0] - head(node)[0]))
            dx = head(lateral)[0] - head(node)[0]
            if abs(dx) > 0.12 * height and head(child)[1] > bottom + 0.40 * height:
                arm_candidates["left" if dx > 0 else "right"].append((abs(dx), child))
    mapped = {}
    for side, chain in zip(["left", "right"], ordered):
        mapped[side] = dict(
            thigh=g.nodes[chain[0]]["name"],
            knee=g.nodes[chain[1]]["name"],
            foot=g.nodes[chain[2]]["name"] if len(chain) > 2 else None,
            leg_chain=[g.nodes[i]["name"] for i in chain],
        )
        arms = arm_candidates[side]
        if arms:
            mapped[side]["arm"] = g.nodes[max(arms)[1]]["name"]
    result["mapping"] = mapped
    return result, {
        "changed": True,
        "reason": "脚の位置または階層に矛盾があるため接地枝と頭部への幹から再分類",
        "pelvis": g.nodes[pelvis]["name"],
        "before": roles,
        "after": mapped,
    }
