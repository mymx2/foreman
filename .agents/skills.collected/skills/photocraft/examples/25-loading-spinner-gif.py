#!/usr/bin/env python3
"""场景：前端要一个 8 帧循环的"加载中"动画：GIF 直接用，PNG 序列帧给做雪碧图或 Lottie 替代。
做法：时间轴 + 空白视频图层逐帧绘制。

要点：insertBlankFrame 插入空白帧后当前帧不会前进，画下一帧前必须 timeline.nextFrame；
      renderVideo 的参数是 {dir, format}，注册表参数文本没有列出（以实测为准）。

用法: python 25-loading-spinner-gif.py [帧数] [尺寸]
"""
from __future__ import annotations

import math
from pathlib import Path

from pcx import *


def main(args):
    frames = int(args[0]) if args else 8
    size = int(args[1]) if len(args) > 1 else 160
    pcx_init("25-loading-spinner-gif")

    def pt(k):
        a = 2 * math.pi * k / frames - math.pi / 2
        return [round(size / 2 + size * 0.34 * math.cos(a)), round(size / 2 + size * 0.34 * math.sin(a))]

    cmds = [("timeline.create", {"duration": 1, "fps": 12}), ("layer.videoLayers.newBlankVideoLayer",)]
    dot = round(size * 0.13)
    for f in range(frames):
        if f > 0:
            cmds += [("layer.videoLayers.insertBlankFrame",), ("timeline.nextFrame",)]
        for k in range(frames):
            lag = (f - k + frames) % frames
            color = {0: "#2563eb", 1: "#60a5fa", 2: "#bfdbfe"}.get(lag, "#e5e7eb")
            cmds.append(("paint.stroke", {"points": [pt(k) + [1]], "size": dot, "hardness": 1, "color": color}))

    step("逐帧绘制：%d 帧，%dpx，12 fps" % (frames, size))
    cmds += [("timeline.setFrame", {"frame": 0}), ("timeline.info",),
             ("file.export.renderVideo", {"dir": "gif", "format": "gif"}),
             ("file.export.renderVideo", {"dir": "frames", "format": "png"})]
    out = pc_run(cmds, new={"width": size, "height": size, "background": "white", "name": "spinner"},
                 out="spinner.psd", check=True)
    t = pc_result(out, "timeline.info")["timeline"]
    print("(timeline: %s frames at %s fps)" % (t["duration"], t["fps"]))

    step("核对：GIF 存在、PNG 序列帧数正确、第 k 帧高亮的是第 k 个点")
    gif = next(Path("gif").glob("*.gif"))
    expect_file(gif)
    expect_count("frames", "*.png", frames)
    for i, f in enumerate(sorted(Path("frames").glob("*.png"))):
        x, y = pt(i)
        r = pc_result(pc_run([("document.pixel", {"x": x, "y": y})], input=str(f)), "document.pixel")
        hexc = "".join("%02x" % round(v * 255) for v in r[:3])
        if hexc != "2563eb":
            fail(f"frame {i}: dot {i} is #{hexc}, expected the highlight #2563eb")
    note("ok  every frame highlights its own dot")

    data = gif.read_bytes()
    count = data.count(b"\x21\xf9\x04")
    note("gif: %d frames, %d bytes" % (count, len(data)))
    if count != frames:
        fail("GIF frame count differs")
    note("ok  GIF holds all %d frames" % frames)


run(main)
