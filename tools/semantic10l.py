"""Checks role consistency; no character names or fixed bone indices."""
def check_roles(report):
    roles = report.get("transfer_mapping")
    if roles is None:
        roles = {}
        for side, m in report["mapping"].items():
            chain = report["arm_anatomy"]["arms"][side]["chain"]
            i = chain.index(m["arm"])
            if len(chain) < i + 3:
                raise ValueError(side + ": upper arm / forearm / hand endpoints missing")
            roles.update({side+"_arm":m["arm"], side+"_forearm":chain[i+1],
                          side+"_hand":chain[i+2], side+"_thigh":m["thigh"],
                          side+"_knee":m["knee"], side+"_foot":m["foot"]})
    used = {}
    for role, bone in roles.items():
        if bone is None:
            raise ValueError("Missing semantic bone: " + role)
        if bone in used:
            raise ValueError(f"Semantic collision: {used[bone]} and {role} share {bone}")
        used[bone] = role
    arms = report.get("arm_anatomy", {}).get("arms", {})
    legs = set()
    for m in report.get("mapping", {}).values():
        legs.update(m.get("leg_chain", []))
    for side, arm in arms.items():
        if set(arm["branch"]) & legs:
            raise ValueError(side + ": arm subtree overlaps leg chain")
    return dict(passed=True, roles=roles)
