"""Embedded glTF reader/writer and sampled pose inspection, independent of a character ID."""

from pathlib import Path
import hashlib, json, struct, math
from functools import lru_cache
import numpy as np

DT = {5120: "i1", 5121: "u1", 5122: "<i2", 5123: "<u2", 5125: "<u4", 5126: "<f4"}
SZ = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4, "MAT2": 4, "MAT3": 9, "MAT4": 16}


def digest(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def trs(t, r, s):
    x, y, z, w = r
    m = np.eye(4)
    m[:3, :3] = np.array(
        [
            [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
            [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
            [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)],
        ]
    ) @ np.diag(s)
    m[:3, 3] = t
    return m


def sample(times, values, t, method, rotation=False):
    if method == "STEP":
        return values[
            max(
                0, min(len(times) - 1, int(np.searchsorted(times, t, side="right") - 1))
            )
        ]
    i = max(0, min(len(times) - 2, int(np.searchsorted(times, t) - 1)))
    if len(times) == 1:
        return values[1] if method == "CUBICSPLINE" else values[0]
    dt = times[i + 1] - times[i]
    u = float(np.clip((t - times[i]) / max(dt, 1e-12), 0, 1))
    if method == "CUBICSPLINE":
        a = values[3 * i + 1]
        b = values[3 * (i + 1) + 1]
        v = (
            (2 * u**3 - 3 * u * u + 1) * a
            + (u**3 - 2 * u * u + u) * dt * values[3 * i + 2]
            + (-2 * u**3 + 3 * u * u) * b
            + (u**3 - u * u) * dt * values[3 * (i + 1)]
        )
    elif method == "LINEAR":
        a, b = values[i], values[i + 1]
        if rotation:
            d = float(np.dot(a, b))
            if d < 0:
                b = -b
                d = -d
            if d < 0.9995:
                angle = math.acos(np.clip(d, -1, 1))
                v = (
                    math.sin((1 - u) * angle) * a + math.sin(u * angle) * b
                ) / math.sin(angle)
            else:
                v = a * (1 - u) + b * u
        else:
            v = a * (1 - u) + b * u
    else:
        raise ValueError("未対応の補間: " + method)
    if rotation:
        v /= max(np.linalg.norm(v), 1e-12)
    return v


class GLB:
    def __init__(self, path):
        self.path = Path(path)
        raw = self.path.read_bytes()
        if len(raw) < 20 or struct.unpack_from("<4sII", raw) != (b"glTF", 2, len(raw)):
            raise ValueError("有効なGLB 2.0ではありません")
        self.meta = None
        self.binary = bytearray()
        o = 12
        while o < len(raw):
            n, k = struct.unpack_from("<II", raw, o)
            o += 8
            part = raw[o : o + n]
            o += n
            if k == 0x4E4F534A:
                self.meta = json.loads(
                    part,
                    parse_constant=lambda x: (_ for _ in ()).throw(
                        ValueError("GLB JSONに不正な数値があります")
                    ),
                )
            elif k == 0x004E4942:
                self.binary = bytearray(part)
        if self.meta and any(
            x in self.meta.get("extensionsUsed", [])
            for x in ["KHR_draco_mesh_compression", "EXT_meshopt_compression"]
        ):
            raise ValueError("圧縮を解除した通常のGLBを指定してください")
        if not self.meta or not self.meta.get("meshes"):
            raise ValueError("メッシュのあるGLBが必要です")
        if any(b.get("uri") for b in self.meta.get("buffers", [])) or any(
            im.get("uri") and not im["uri"].startswith("data:")
            for im in self.meta.get("images", [])
        ):
            raise ValueError("画像とbufferを内蔵したGLBを指定してください")
        self.cache = {}
        self.nodes = self.meta["nodes"]
        self.parents = {
            c: i for i, n in enumerate(self.nodes) for c in n.get("children", [])
        }
        self.primitives = []
        for ni, node in enumerate(self.nodes):
            if "mesh" not in node:
                continue
            for p in self.meta["meshes"][node["mesh"]]["primitives"]:
                if "POSITION" not in p["attributes"] or p.get("mode", 4) != 4:
                    raise ValueError("非圧縮の三角形メッシュを指定してください")
                pos = self.acc(p["attributes"]["POSITION"])
                faces = (
                    self.acc(p["indices"]).reshape(-1, 3).astype(int)
                    if "indices" in p
                    else np.arange(len(pos)).reshape(-1, 3)
                )
                self.primitives.append((ni, p, pos, faces))

    @lru_cache(maxsize=2048)
    def acc(self, index):
        a = self.meta["accessors"][index]
        dtype = np.dtype(DT[a["componentType"]])
        width = SZ[a["type"]]
        if "bufferView" in a:
            v = self.meta["bufferViews"][a["bufferView"]]
            array = np.ndarray(
                (a["count"], width),
                dtype=dtype,
                buffer=self.binary,
                offset=v.get("byteOffset", 0) + a.get("byteOffset", 0),
                strides=(v.get("byteStride", dtype.itemsize * width), dtype.itemsize),
            ).copy()
        else:
            array = np.zeros((a["count"], width), dtype=dtype)
        if a.get("sparse"):
            sp = a["sparse"]
            ind = sp["indices"]
            val = sp["values"]
            iv = self.meta["bufferViews"][ind["bufferView"]]
            vv = self.meta["bufferViews"][val["bufferView"]]
            ids = np.frombuffer(
                self.binary,
                dtype=DT[ind["componentType"]],
                count=sp["count"],
                offset=iv.get("byteOffset", 0) + ind.get("byteOffset", 0),
            )
            values = np.frombuffer(
                self.binary,
                dtype=dtype,
                count=sp["count"] * width,
                offset=vv.get("byteOffset", 0) + val.get("byteOffset", 0),
            ).reshape(-1, width)
            array[ids] = values
        if a.get("normalized"):
            array = np.maximum(array.astype(float) / np.iinfo(dtype).max, -1)
        if not np.isfinite(array).all():
            raise ValueError("GLBにNaNまたは無限大があります")
        return array

    def duration(self, clip):
        return max(float(self.acc(s["input"])[-1, 0]) for s in clip["samplers"])

    def pose(self, clip=None, t=0, vertex_limit=None):
        props = [
            dict(
                translation=n.get("translation", [0, 0, 0]),
                rotation=n.get("rotation", [0, 0, 0, 1]),
                scale=n.get("scale", [1, 1, 1]),
                weights=n.get(
                    "weights",
                    (
                        self.meta["meshes"][n["mesh"]].get("weights", [])
                        if "mesh" in n
                        else []
                    ),
                ),
            )
            for n in self.nodes
        ]
        animated = set()
        if clip:
            for ch in clip["channels"]:
                target = ch["target"]
                i = target.get("node")
                path = target["path"]
                if i is None:
                    continue
                sampler = clip["samplers"][ch["sampler"]]
                times = self.acc(sampler["input"]).ravel()
                val = self.acc(sampler["output"])
                method = sampler.get("interpolation", "LINEAR")
                if path == "weights":
                    val = val.reshape(
                        len(times) * (3 if method == "CUBICSPLINE" else 1), -1
                    )
                props[i][path] = sample(times, val, t, method, path == "rotation")
                animated.add(i)
        worlds = [None] * len(self.nodes)

        def world(i):
            if worlds[i] is None:
                n = self.nodes[i]
                p = props[i]
                local = (
                    np.array(n["matrix"]).reshape(4, 4).T
                    if "matrix" in n and i not in animated
                    else trs(p["translation"], p["rotation"], p["scale"])
                )
                worlds[i] = (
                    world(self.parents[i]) @ local if i in self.parents else local
                )
            return worlds[i]

        out = []
        for ni, p, source, faces in self.primitives:
            ids = (
                np.arange(len(source))
                if vertex_limit is None or len(source) <= vertex_limit
                else np.unique(
                    np.linspace(0, len(source) - 1, vertex_limit).astype(int)
                )
            )
            pos = source[ids].astype(float).copy()
            for w, target in zip(props[ni]["weights"], p.get("targets", [])):
                if w and "POSITION" in target:
                    pos += float(w) * self.acc(target["POSITION"])[ids]
            pos4 = np.c_[pos, np.ones(len(pos))]
            node = self.nodes[ni]
            if "skin" not in node:
                result = pos4 @ world(ni).T
            else:
                skin = self.meta["skins"][node["skin"]]
                joints = skin["joints"]
                ibm = (
                    self.acc(skin["inverseBindMatrices"])
                    .reshape(-1, 4, 4)
                    .transpose(0, 2, 1)
                    if "inverseBindMatrices" in skin
                    else np.tile(np.eye(4), (len(joints), 1, 1))
                )
                mats = np.stack([world(j) for j in joints]) @ ibm
                result = np.zeros((len(pos), 4))
                total = np.zeros(len(pos))
                for setno in [0, 1]:
                    an = p["attributes"]
                    if "JOINTS_" + str(setno) not in an:
                        continue
                    ji = self.acc(an["JOINTS_" + str(setno)])[ids].astype(int)
                    bw = self.acc(an["WEIGHTS_" + str(setno)])[ids]
                    if ji.min() < 0 or ji.max() >= len(joints) or bw.min() < 0:
                        raise ValueError("不正なスキン重みです")
                    for k in range(4):
                        result += (
                            np.einsum("nij,nj->ni", mats[ji[:, k]], pos4)
                            * bw[:, k, None]
                        )
                    total += bw.sum(axis=1)
                if np.max(np.abs(total - 1)) > 0.03:
                    raise ValueError("スキン重みの合計が不正です")
            if not np.isfinite(result).all():
                raise ValueError("姿勢の計算値が不正です")
            out.append((ids, result[:, :3]))
        return out, props

    def bounds(self, clip=None, t=0):
        points = np.concatenate(
            [v for ids, v in self.pose(clip, t, vertex_limit=20000)[0]]
        )
        return points.min(axis=0), points.max(axis=0)

    def add_acc(self, array, type, component_type=5126):
        a = np.asarray(
            array, dtype={5126: "<f4", 5123: "<u2", 5125: "<u4"}[component_type]
        )
        self.binary.extend(b"\0" * (-len(self.binary) % 4))
        offset = len(self.binary)
        self.binary.extend(a.tobytes())
        v = dict(buffer=0, byteOffset=offset, byteLength=a.nbytes)
        self.meta.setdefault("bufferViews", []).append(v)
        ac = dict(
            bufferView=len(self.meta["bufferViews"]) - 1,
            componentType=component_type,
            count=len(a),
            type=type,
            min=a.min(axis=0).tolist(),
            max=a.max(axis=0).tolist(),
        )
        self.meta.setdefault("accessors", []).append(ac)
        return len(self.meta["accessors"]) - 1

    def write(self, path):
        self.meta["buffers"] = [dict(byteLength=len(self.binary))]
        j = json.dumps(self.meta, separators=(",", ":"), ensure_ascii=False).encode()
        j += b" " * (-len(j) % 4)
        b = bytes(self.binary) + b"\0" * (-len(self.binary) % 4)
        Path(path).write_bytes(
            struct.pack("<4sII", b"glTF", 2, 28 + len(j) + len(b))
            + struct.pack("<II", len(j), 0x4E4F534A)
            + j
            + struct.pack("<II", len(b), 0x004E4942)
            + b
        )
