#!/usr/bin/env python3
"""驱动一个常驻的 `photocraft-cli serve` 会话（JSON-lines over stdio）。由场景脚本执行。

    python clients/serve_session.py <工作目录> <输入图，相对工作目录>

工作目录同时授权为读、写根目录，请求里的路径一律写相对路径（正斜杠）。
和逐条 `photocraft-cli run` 相比：一个进程里保持文档、历史、快照和预设，能根据上一步结果决定下一步。
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import pclib  # noqa: E402


def log(*parts):
    print(*parts, flush=True)


def mean_chroma(serve, doc):
    steps = []
    for i in range(1, 6):
        for k in range(1, 6):
            steps.append({"command": "document.sampleColor",
                          "params": {"x": round(doc["width"] * i / 6), "y": round(doc["height"] * k / 6), "size": 31}})
    results = serve.batch(steps)["results"]
    chroma = [max(r["result"][:3]) - min(r["result"][:3]) for r in results]
    return sum(chroma) / len(chroma)


def main(files):
    if len(files) != 2:
        raise SystemExit("usage: serve_session.py <workspace-dir> <input-relative-to-workspace>")
    root, input_name = files
    with pclib.Serve(read_root=root, write_root=root) as serve:
        doc = serve.call("doc.open", {"path": input_name})
        log(f"opened {doc['name']} {doc['width']}x{doc['height']}")
        serve.execute("history.newSnapshot", {"name": "Original"})
        base = mean_chroma(serve, doc)

        pass1 = serve.batch([
            {"command": "image.autoContrast"},
            {"command": "layer.newAdjustmentLayer.curves", "params": {"points": [[0, 0], [64, 36], [192, 232], [255, 255]]}},
            {"command": "layer.newAdjustmentLayer.vibrance", "params": {"vibrance": 90, "saturation": 35}},
        ])
        serve.call("doc.render", {"maxSide": 512, "path": "preview-pass1.png"})
        chroma = mean_chroma(serve, doc)
        log(f"pass 1: {pass1['completed']} steps, mean chroma {base:.3f} -> {chroma:.3f}")

        if chroma > base * 1.25:
            snapshots = serve.call("doc.inspect")["snapshots"]
            original = next(s for s in snapshots if s["name"] == "Original")
            serve.execute("history.selectSnapshot", {"snapshot": original["id"]})
            log(f"rolled back to snapshot \"{original['name']}\"")

        serve.batch([
            {"command": "layer.newAdjustmentLayer.curves", "params": {"points": [[0, 8], [64, 58], [192, 206], [255, 250]]}},
            {"command": "layer.newAdjustmentLayer.vibrance", "params": {"vibrance": 25}},
        ])

        # 长任务：wait:false 立即返回 job，轮询到结束再继续改同一文档
        serve.execute("layer.select", {"name": "Background"})
        serve.execute("layer.duplicate", {"name": "Soft glow"})
        job = serve.execute("filter.blur.gaussianBlur", {"radius": 30}, wait=False)["job"]
        state = "running"
        while state == "running":
            time.sleep(0.15)
            jobs = serve.call("jobs.list")["jobs"]
            state = next((j["state"] for j in jobs if j["id"] == job), "done")
        log(f"job {job} {state}")
        serve.execute("layer.setProps", {"blend": "Soft Light", "opacity": 0.35})
        serve.execute("edit.undo")
        serve.execute("edit.redo")
        serve.call("doc.render", {"maxSide": 512, "path": "preview-pass2.png"})

        # 会话内文档预设：存一次，之后按名字取参数新建文档
        serve.execute("document.presets.save", {"name": "Story 9:16", "settings": {"width": 1080, "height": 1920, "background": "white"}})
        params = serve.execute("document.presets.get", {"name": "Story 9:16"})["params"]
        story = serve.call("doc.new", {**params, "name": "story"})
        log(f"doc.new from preset \"Story 9:16\" -> document {story['document']}")
        serve.call("doc.select", {"index": 0})

        serve.call("doc.save", {"path": "graded.psd"})
        serve.call("doc.save", {"path": "graded.jpg", "quality": 85})
        log(f"exported {serve.call('doc.exportLayers', {'dir': 'layers'})['count']} layers")

        refusals = [
            ("path traversal", lambda: serve.call("doc.save", {"path": "../escape.png"})),
            ("ambient file command", lambda: serve.execute("file.saveACopy", {"path": "copy.png"})),
        ]
        for what, attempt in refusals:
            try:
                attempt()
            except pclib.RpcError as exc:
                log(f"refused ({what}): {str(exc)[:100]}")
            else:
                raise SystemExit(f"{what} was not refused")
        try:
            serve.execute("file.saveACopy", {"path": "copy.png"})
        except pclib.RpcError:
            pass

        log(f"ui language pref: {serve.execute('prefs.get', {'path': 'interface.language'})}")
        documents = serve.call("session.list")["documents"]
        log("documents: " + " ".join(f"{d['index']}:{d['name']}{'*' if d['dirty'] else ''}" for d in documents))
        if not serve.alive:
            raise SystemExit("the serve process exited early:\n" + serve.stderr_tail())


if __name__ == "__main__":
    try:
        main(sys.argv[1:])
    except pclib.PcError as exc:
        print(f"FAIL {exc}", file=sys.stderr)
        raise SystemExit(1)
