# 2026-11-15 真机探针证据

这是 2026-11-15 在 Windows 剪映专业版 **11.8.0.14778** 上实际生成一批草稿、导出 MP4 并抽帧的原始证据，
用来让 `limits.md` / `capabilities.md` 里的“真机抽帧/volumedetect”结论可以被复核，而不是只留在
`%TEMP%`。

技能包只保留最小证据（plan/completion/png），成片媒体归档在仓库 `_evidence/`，分发时不需要带走。

- 画布：320×180 / 30fps
- 导出：剪映 native bridge（`jy.py render`），不是外部 ffmpeg 拼接
- 源素材：`D:\data\123\jy-fullcap-smoke\bg.mp4`、`clip.mp4`
- 每个目录都保留 plan、抽帧与桥接回执 `*.completion.json`；失败项保留 `render-error.json`；成片 mp4 已移到技能包外（见下表与文末说明）

## 目录与结论

| 目录 | 结论 | 关键文件 |
|---|---|---|
| `mask/` | `resource_id=82432977`（circle）+ 完整 config 导出后，抽帧可见中央椭圆彩条；`config={}` 同机导出全黑（黑场约 1.967s） | `plan-mask-config.json`、`mask-config.mp4`（媒体已移至技能包外的 `_evidence/jianying/2026-11-15-real-probes/mask/`）、`mask-config.png`、`plan-mask-main.json`、`mask-main.mp4`（媒体已移至技能包外的 `_evidence/jianying/2026-11-15-real-probes/mask/`）、`mask-main.png` |
| `flip/` | `flip.vertical=true` 真实导出后，画面上下翻转成立 | `plan-flip-v.json`、`flip-v.mp4`（媒体已移至技能包外的 `_evidence/jianying/2026-11-15-real-probes/flip/`）、`flip-v.png` |
| `audio-channel/` | 双声道源 + `channel:1` 导出后，左右声道 `volumedetect` 均为 `-21.2dB`；11.8 native 声道映射未生效 | `plan-channel-left.json`、`channel-left.mp4`（媒体已移至技能包外的 `_evidence/jianying/2026-11-15-real-probes/audio-channel/`） |
| `wheel/` | `color_wheel gamma red=0.5` 导出抽帧与无调色帧一致；11.8 native 色轮未观察到像素变化 | `plan-wheel.json`、`wheel.mp4`（媒体已移至技能包外的 `_evidence/jianying/2026-11-15-real-probes/wheel/`）、`wheel.png` |
| `sticker/` | 包 `7675620818189077810`：render 返回 409 `film_export_entitlement_denied`（见 `render-error.json`）；包 `7202575978646737469`：render ok，但抽帧未见贴纸 | `plan-sticker.json`、`draft-sticker-info.json`、`render-error.json`、`plan-sticker-free.json`、`sticker-free.mp4`（媒体已移至技能包外的 `_evidence/jianying/2026-11-15-real-probes/sticker/`）、`sticker-free.png` |

## 复现命令

复现前置：
- 源素材（`bg.mp4` / `clip.mp4` / `stereo.m4a`）与 `Cache/effect/82432977` 资源包不在仓库；plan 里仍是本机绝对路径，换机要改 `path`。
- native render 需要剪映 11.8 已登录、bridge health 可用；回执里的 `accountScope` 已脱敏。
- 抽帧/黑场/声道验收需要本机 ffmpeg；本机 PATH 没有裸 `ffmpeg`，先按 `jy.py probe` 的路径调用。

在技能根目录执行：

```powershell
# 圆形蒙版（完整 config）
python scripts/jy.py build --plan references/evidence/2026-11-15-real-probes/mask/plan-mask-config.json `
  --out $env:TEMP\jy-evidence-mask --force --no-cover
python scripts/jy.py render $env:TEMP\jy-evidence-mask -o $env:TEMP\jy-evidence-mask.mp4 --force
python scripts/jy.py frame $env:TEMP\jy-evidence-mask.mp4 --at 1.0 -o $env:TEMP\jy-evidence-mask.png --force

# 空 config（预期全黑）
python scripts/jy.py build --plan references/evidence/2026-11-15-real-probes/mask/plan-mask-main.json `
  --out $env:TEMP\jy-evidence-mask-main --force --no-cover
python scripts/jy.py render $env:TEMP\jy-evidence-mask-main -o $env:TEMP\jy-evidence-mask-main.mp4 --force
python scripts/jy.py frame $env:TEMP\jy-evidence-mask-main.mp4 --at 1.0 -o $env:TEMP\jy-evidence-mask-main.png --force

# 垂直翻转
python scripts/jy.py build --plan references/evidence/2026-11-15-real-probes/flip/plan-flip-v.json `
  --out $env:TEMP\jy-evidence-flip --force --no-cover
python scripts/jy.py render $env:TEMP\jy-evidence-flip -o $env:TEMP\jy-evidence-flip.mp4 --force
python scripts/jy.py frame $env:TEMP\jy-evidence-flip.mp4 --at 1.0 -o $env:TEMP\jy-evidence-flip.png --force

# 声道（双声道源需按 plan 中的绝对路径存在）
python scripts/jy.py build --plan references/evidence/2026-11-15-real-probes/audio-channel/plan-channel-left.json `
  --out $env:TEMP\jy-evidence-channel --force --no-cover
python scripts/jy.py render $env:TEMP\jy-evidence-channel -o $env:TEMP\jy-evidence-channel.mp4 --force

# 色轮
python scripts/jy.py build --plan references/evidence/2026-11-15-real-probes/wheel/plan-wheel.json `
  --out $env:TEMP\jy-evidence-wheel --force --no-cover
python scripts/jy.py render $env:TEMP\jy-evidence-wheel -o $env:TEMP\jy-evidence-wheel.mp4 --force
python scripts/jy.py frame $env:TEMP\jy-evidence-wheel.mp4 --at 1.0 -o $env:TEMP\jy-evidence-wheel.png --force

# 贴纸失败包（预期 exit 1，409 film_export_entitlement_denied）
python scripts/jy.py build --plan references/evidence/2026-11-15-real-probes/sticker/plan-sticker.json `
  --out $env:TEMP\jy-evidence-sticker --force --no-cover
python scripts/jy.py render $env:TEMP\jy-evidence-sticker -o $env:TEMP\jy-evidence-sticker-real.mp4 --force

# 贴纸成功包（预期 render ok，但抽帧不应看到贴纸）
python scripts/jy.py build --plan references/evidence/2026-11-15-real-probes/sticker/plan-sticker-free.json `
  --out $env:TEMP\jy-evidence-sticker-free --force --no-cover
python scripts/jy.py render $env:TEMP\jy-evidence-sticker-free -o $env:TEMP\jy-evidence-sticker-free.mp4 --force
python scripts/jy.py frame $env:TEMP\jy-evidence-sticker-free.mp4 --at 1.0 -o $env:TEMP\jy-evidence-sticker-free.png --force
```

## 验收命令

```powershell
# 蒙版空 config：整段应接近黑场
ffmpeg -hide_banner -i .agents/skills.collected/_evidence/jianying/2026-11-15-real-probes/mask/mask-main.mp4 `
  -vf "blackdetect=d=0.1:pix_th=0.10" -f null -

# 声道：左右应各自 -21.2dB，证明 channel 未生效
ffmpeg -hide_banner -i .agents/skills.collected/_evidence/jianying/2026-11-15-real-probes/audio-channel/channel-left.mp4 `
  -af "pan=mono|c0=c0,volumedetect" -f null -
ffmpeg -hide_banner -i .agents/skills.collected/_evidence/jianying/2026-11-15-real-probes/audio-channel/channel-left.mp4 `
  -af "pan=mono|c0=c1,volumedetect" -f null -

# 贴纸失败：stdout 里应出现 status=409 + native_error=film_export_entitlement_denied
Get-Content references/evidence/2026-11-15-real-probes/sticker/render-error.json -Raw
```

> 归档 mp4 的路径相对仓库根（`rbz-one`）；技能包内没有这些成片，只保留 plan/completion/png。
> `ffmpeg` 不在本机 PATH：先用 `python scripts/jy.py probe` 看 `ffmpeg.ffmpeg`，或把该路径临时加进 PATH。
> 裸 `-af volumedetect` 只给一个整体均值；要证明“左右相同”，必须像上面那样分声道各测一次。

`plan-*.json` 里的素材路径是 2026-11-15 本机绝对路径；换机复现前要先把 `path` 改成自己的素材。
`sticker/render-error.json` 是失败命令的真实 stdout + exit code，不含 bridge token。
归档回执已删除 `accountScope`（`uid:<id>` 属于账号标识），保留 requestId/draftSha256/outputSha256 作为回执证据。
这是**整键移除**而不是置 `null`：按 JSON schema 消费这些回执时，请把 `accountScope` 当作可缺省字段。
协议文档/代码示例里的 `uid:<userId>`、`uid:123456` 是占位符，不是账号值；`resource_id`/`sticker_id`/草稿包 id 是资源标识，按非账号数据处理。

## 边界

- 这些证据只证明 **本机 11.8.0.14778 + 当次素材** 的结果；换版本、换画布、换资源包都可能不同。
- `sticker` 两个包都没有完成“可见且可用”的像素验收；`sticker` 仍按 `conditional` 说明，不承诺。
- 色轮、声道、HSL、绿幕、倒放、曲线变速的真实效果仍不可承诺，见 `limits.md`。
- 证据文件是二进制；`check_docs`/`check_skill` 只校验文本，不解析视频内容。
- 成片媒体（6 个 mp4）不在技能包内，归档在仓库 `.agents/skills.collected/_evidence/jianying/2026-11-15-real-probes/`；上面验收命令按仓库根路径引用。
