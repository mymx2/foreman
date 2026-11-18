# 注册表快照（自动生成）

> 由 `photocraft-cli commands --json` 直接导出。**本文件自动生成，不要手改**；参数以本文件为准，行为描述以实跑为准。
> 导出时间：2026-11-18；CLI：photocraft-cli 0.23.1 (45066c482, 2026-11-12)；共 1009 条，按家族分组。
> 人工整理的说明与案例编号见 [commands.md](commands.md)。

## 家族索引

| 家族 | 条数 |
|---|---|
| actions | 27 |
| brush | 21 |
| channel | 22 |
| cloneSource | 5 |
| color | 1 |
| command | 1 |
| count | 7 |
| document | 11 |
| edit | 79 |
| file | 60 |
| filter | 124 |
| gradient | 12 |
| help | 1 |
| history | 14 |
| image | 66 |
| jobs | 2 |
| layer | 233 |
| layerComp | 14 |
| measurementLog | 3 |
| notes | 4 |
| paint | 28 |
| path | 27 |
| pattern | 10 |
| plugin | 5 |
| prefs | 3 |
| select | 35 |
| session | 1 |
| shape | 10 |
| slice | 7 |
| style | 7 |
| swatches | 12 |
| timeline | 7 |
| tool | 5 |
| tools | 13 |
| type | 99 |
| updates | 1 |
| variables | 1 |
| view | 31 |

## actions（27）

```text
actions.allowToolRecording	Allow Tool Recording	{"enabled":bool?=toggle} → {enabled:bool}. Opt in to recording painting-tool strokes (off initially). Existing pending steps are committed under the previous mode. Painting, history and the journal are unchanged. actions.list reports toolRecording.
actions.assignSet	Move to Set	{"action":name|index, "set":name|null} → {action, set}. The set folder the Actions panel shows the action under (what Load Actions fills and Save Actions writes); null takes it out of any set.
actions.conditional	Conditional	{"if":condition, "then":action name|null, "else":action name|null} → {if, holds, played, ran?, failed?}. Photoshop's Insert Conditional: conditions always|never|isOpen|landscape|square|portrait|modeIsRGB|modeIsCMYK|modeIsGrayscale|modeIsLab|modeIsBitmap|modeIsIndexed|modeIsDuotone|modeIsMultichannel|depth8|depth16|depth32|unsaved|hasSelection|hasLayers|hasAlphaChannels|isBackground|isPixelLayer|isAdjustmentLayer|isShapeLayer|isTypeLayer|isSmartObject|isLayerGroup|isLocked|isVisible|hasPixelMask|hasVectorMask|hasEffects (layer conditions test the active layer). The branch plays as actions.play does; its failure stops the calling action.
actions.delete	Delete Action	{"action":name|index, "step":index?} → {deleted:name} or {action, deletedStep, steps:count}. step is 0-based, including pending recorded steps. Whole-action deletion is refused while recording.
actions.dialog	Toggle Step Dialog	{"action":name|index, "step":index?, "enabled":bool?} → {action, dialogs:[step…]}. The Actions panel's dialog toggle: the desktop shell shows the step's dialog, seeded with its recorded params, and resumes playback when it is confirmed; headless playback runs the recorded params. Omitted enabled flips it; without step, every step: on unless all already are, or as enabled says.
actions.duplicate	Duplicate Action	{"action":name|index,"step":index?} or {"set":name} → {action?,index?,step?,steps?,set?,actions?}. Copy an action, step or named set below the source. Copies retain settings and flags, and leave shortcuts with the originals.
actions.get	Get Action	{"action":name|index} → {name, steps:[[id, params]…], disabled:[step…], dialogs:[step…], set:name|null, color:str} (steps is the shape file.automate.batch and droplets take; disabled lists the 0-based steps playback skips; dialogs the steps whose dialog Photoshop would show; set the action set from Load Actions; color is the Button Mode swatch, or empty)
actions.insert	Insert Step	{"action":name|index, "id":command id, "params":{}?, "at":index?=end} → {action, step, id, steps}. Inserts a step at the 0-based position (the reference application's Insert Stop… with id actions.stopMessage, its dialog toggle on; Insert Menu Item… with any command). Pending recorded steps count; flags of the steps after it follow them.
actions.insertMenuItem	Insert Menu Item…	{"action":name|index,"id":menu command,"at":index?,"eventKind":"name"|"code"="name"} → {action,step,id,steps}. Records an unambiguous supported menu event without settings. Image Size and mapped filter menu events are supported. Desktop playback opens the existing editor when settings are needed; no-settings items run immediately.
actions.insertPath	Insert Path	{"action":name|index,"name":"work"|"layer"|saved path name,"at":index?} → {action,step,id,steps}. Snapshot exactly the selected path as a path.set work-path step, preserving cubic handles and path options. No fallback from a missing Work Path to a layer path. The measured Work Path ATN descriptor supports absolute coordinates, cubic handles, even-odd subpaths and Add/Subtract/XOR. Paths outside that measured form still play natively and are reported as unsupported by ATN export.
actions.list	List Actions	{} → {actions:[{name, steps:count, set:name|null}], sets:[name…] (every set in panel order, empty ones too), recording:name|null, toolRecording:bool}
actions.load	Load Actions…	{"path":".atn file"?,"data":base64 bytes?,"set":name? (override the file's set name),"replace":bool=true (replace the actions of a set of the same name),"encoding":"auto"|label="auto" (the encoding of 8-bit step names: shift_jis, gbk, big5, euc-kr, windows-1252, macintosh…; auto works it out)} → {set, actions:[names], steps, unsupported:[{action, step, event, name}], functionKeys:[{action, key}], warnings, encoding}. Photoshop steps PhotoCraft cannot play become actions.photoshopStep steps (kept for Save Actions; they fail at playback with the step's name); tool selections and other steps with no document effect are imported switched off. Layer references by name replay in any document.
actions.menuItem	Menu Item	{"id":menu command,"eventKind":"name"|"code"="name"} (a descriptor-free Image Size or unambiguous mapped filter menu event; desktop playback asks for settings when needed, headless playback only runs stateless menu items)
actions.move	Move Action or Step	{"action":name|index, "step":index?, "to":index}. Move a step within its action, or the action itself. to is the final zero-based index. Pending recorded steps can be moved.
actions.newSet	New Set	{"name":str? (default "Set N")} → {set}. An empty set folder in the Actions panel, as Photoshop's New Set… makes; New Action records into the selected set (actions.record's `set`). Save Actions… (actions.save's `set`) writes it even while empty; it is remembered between sessions once it holds an action.
actions.photoshopStep	Photoshop Step	{"event":id,"name":str,"descriptor":base64?} (a step from a .atn file PhotoCraft has no command for: fails at playback, written back by actions.save)
actions.play	Play Action	{"action":name|index, "from":step?} → {action, ran, failed?:{step, id, error}}. step and from are 0-based; steps switched off with actions.toggle are skipped. Stops at the first error (the command still returns ok, with failed set) and groups document edits in one Action: <name> history entry by default; actions.setHistory can retain per-step history. Nested calls are supported up to 16 levels; cycles are rejected. Recording stores a named call rather than its expanded commands. Each step is checked with Session::authorize when one is installed.
actions.record	Record Action	{"name":str? (new action, default "Action N"),"set":name? (the set it goes in, as New Action records into the selected set)} or {"action":name|index} (append) → {action, index}
actions.recordAgain	Record Again	{"action":name|index,"step":index,"params":{new settings},"revision":u64?} → {action,step,id,result}. Replays the selected command and stores its new settings only after success, preserving its enabled/dialog flags. The panel opens the command's editor at the recorded settings. Stop recording or playback first; revision optionally rejects stale library state.
actions.rename	Rename Action	{"action":name|index, "name":str} → {action, index}. The name must not be empty or whitespace-only and must be unique. Nested Play Action steps and the action's function key follow the rename.
actions.save	Save Actions…	{"path":".atn file"? (else the bytes come back as base64 `data`),"set":name? (that set's actions, none for an empty New Set set; default: every action, as the set "PhotoCraft Actions"),"action":name|index? (one action),"skipUnsupported":bool=false (leave out steps with no Photoshop equivalent instead of failing)} → {set, actions:[names], steps, bytes, skipped:[{action, step, id}], path|data}
actions.setColor	Set Action Color	{"action":name|index, "color":""|"red"|"orange"|"yellow"|"green"|"blue"|"violet"|"gray"} → {action, color}. The Button Mode colour. Empty clears it.
actions.setHistory	Set Actions History	{"singleState":bool} → {singleState}. Persist Create a single history state (default true). Playback Options can use this setting without changing its performance mode.
actions.setPlayback	Playback Options	{"performance":"accelerated"|"step"|"pause"?, "seconds":1..60?, "singleState":bool?} → {performance, seconds, singleState}. The Actions panel menu's Playback Options, saved in preferences (`actions.performance`, `actions.pauseSeconds`, `actions.createSingleHistoryState`). Step by Step and Pause For pace a person's Play in the app, about one second between steps plus Pause For's whole seconds; actions.play from agents, the CLI and Batch always runs at once. Omitted keys keep their value; {} reads them. Every value is checked before any is stored.
actions.stop	Stop Recording	{} → {action, steps:count} (steps recorded since actions.record, queries and action-editing commands omitted)
actions.stopMessage	Stop	{"message":str,"allowContinue":bool=false} (Photoshop's Insert Stop: a step that shows the message; headless playback continues when allowContinue is set and otherwise stops the action with the message)
actions.toggle	Toggle Action Steps	{"action":name|index, "step":index?, "enabled":bool?} → {action, disabled:[step…]}. Switch one 0-based step (including pending recorded steps) on or off for playback, Batch and droplets; omitted enabled flips it. Without step, switch every step: on unless all already are, or as enabled says.
```

## brush（21）

```text
brush.defineFromSelection	Define Brush Preset…	{"name":string}
brush.get	Get Brush	{}
brush.mixer.autoClean	Mixer Brush Auto-Clean	{"on":bool? (none: toggle)} → {"on":bool} (the Mixer Brush's Clean the brush after each stroke)
brush.mixer.autoLoad	Mixer Brush Auto-Load	{"on":bool? (none: toggle)} → {"on":bool} (the Mixer Brush's Load the brush after each stroke)
brush.mixer.clean	Clean Mixer Brush	{}
brush.mixer.load	Load Mixer Brush	{"color":"#rrggbb"|[r,g,b,a?] 0..1?=foreground}
brush.mixer.sample	Sample Mixer Brush	{"points":[[x,y,pressure?,tiltX?,tiltY?,rotation?]],"sampleAllLayers":bool=brush setting,"size":px?,"target":"pixels"|"mask"|"quickMask"|{"channel":i}}
brush.mixer.sampleAllLayers	Mixer Brush Sample All Layers	{"on":bool? (none: toggle)} → {"on":bool} (the Mixer Brush's Sample All Layers)
brush.presets.delete	Delete Brush Preset	{"name":string}
brush.presets.deleteGroup	Delete Brush Group	{"group":string,"folder":[name]? (delete this nested folder instead)} → {deleted, count}
brush.presets.importAbr	Import Brushes…	{"path":".abr file"?,"data":base64 bytes?,"group":string?=file name,"replace":bool=false (first delete the non-built-in presets of a group of the same name; false imports beside it as <group> (2)),"select":bool=false (make the first imported preset current)} → {group, imported, count, folders (nested folders kept from the file), version, warnings}
brush.presets.importImage	Import Brush from Image…	{"path":"image file (PNG, JPEG, TIFF, PSD…)"?,"data":base64 bytes?,"fileName":string? (with data: the file's name, for its format and the default preset name),"name":string?=file name,"select":bool=true (make it the current brush)} → {name, width, height}
brush.presets.list	List Brush Presets	{"full":bool=false}
brush.presets.move	Move Brush	{"name":string,"group":string?=its group ("" = ungrouped),"folder":[name]? (nested folder names in the group, outermost first; [] = the group itself)=before's folder, else its own if it stays in its group, else [],"before":name? (preset to land before, in that folder) | "index":n? (position in the group)=end of the folder} → {name, group, folder, index}
brush.presets.moveGroup	Move Brush Group	{"group":string,"folder":[name]? (move this nested folder instead),"into":{"group":string?,"folder":[name]?}? (move it inside that folder of that group, [] = directly in the group; no group = out to the top level as a group of its own; the folder keeps its content),"before":group? (or sibling folder name, in its new place with `into`) | "index":n? (group or sibling folder position, without `into`)=end} → {group, folder?, index}
brush.presets.rename	Rename Brush	{"name":string,"newName":string} → {name}
brush.presets.renameGroup	Rename Brush Group	{"group":string,"folder":[name]? (rename this nested folder instead),"newName":string} → {group, folder?}
brush.presets.save	Save Brush Preset	{"name":string,"brush":{…BrushSettings}?=current brush,"captureSize":bool=true (false: picking it keeps the tool's size),"toolSettings":bool=true (false: picking it keeps the tool's mode, opacity, flow and pressure buttons),"color":bool=false (picking it sets the foreground to the current foreground)}
brush.presets.setCurrent	Set Current Brush Preset	{"name":string}
brush.presets.update	Update Brush Preset	{"name":string?=the preset the current brush was picked from,"brush":{…BrushSettings}?=current brush}
brush.texturePattern	Brush Texture Pattern	{"pattern":id|name,"scale":1..1000?,"enabled":bool=true} (sets the session brush's Texture to that pattern)
```

## channel（22）

```text
channel.delete	Delete Channel	{"channel":index|name?=targeted}
channel.duplicate	Duplicate Channel…	{"channel":index|name|"red|…"|"composite"|"quickMask","name":str?,"document":index|"new"?=active,"invert":bool=false}
channel.list	Channels	{}
channel.merge	Merge Channels…	{"mode":"rgb|cmyk|lab"="rgb","documents":[index,…]?=open grayscale docs of the active size,"name":str?}
channel.mergeSpot	Merge Spot Channel	{"channel":index|name?=targeted or first spot}
channel.move	Reorder Channel	{"channel":index|name,"to":index}
channel.new	New Channel…	{"name":str?,"fill":"black|white|selection"="black","color":"#rrggbb"="#ff0000","opacity":0..100=50,"indicates":"masked|selected"="masked"}
channel.newSpot	New Spot Channel…	{"name":str?,"color":"#rrggbb"="#ff0000","solidity":0..100=0,"fromSelection":bool=true}
channel.options	Channel Options…	{"channel":index|name|"quickMask"|"mask","name":str?,"indicates":"masked|selected|spot"?,"color":"#rrggbb"?,"opacity":0..100?,"solidity":0..100?} ("mask": Layer Mask Display Options, the rubylith's color and opacity for every layer mask, kept in the preferences as layerMaskOverlay; not an undo step; returns them as layerMaskOverlay)
channel.rename	Rename Channel	{"channel":index|name,"name":str}
channel.setVisible	Channel Visibility	{"channel":"composite"|"red|…"|index|name|"quickMask","visible":bool?=toggle}
channel.split	Split Channels	{"closeOriginal":bool=true}
channel.target	Target Channel	{"channel":"composite"|"mask"|"vectorMask"|"red|green|blue|…"|index|name|{"color":index|name}|{"alpha":index}="composite","colors":[index,…]?,"extend":bool=false} (a color object selects only a native component, never a named alpha channel; colors selects native colour components only; extend toggles one colour channel, as Shift-click; all components select the composite)
channel.target.composite	Target Composite Channel	{}
channel.target.layerMask	Target Layer Mask	{}
channel.target.slot3	Target Channel 3	{}
channel.target.slot4	Target Channel 4	{}
channel.target.slot5	Target Channel 5	{}
channel.target.slot6	Target Channel 6	{}
channel.target.slot7	Target Channel 7	{}
channel.target.slot8	Target Channel 8	{}
channel.target.slot9	Target Channel 9	{}
```

## cloneSource（5）

```text
cloneSource.list	Clone Sources	{} → {active,sources:[{index,source,anchor,offset,layer,width,height,linked,rotation,flipH,flipV}],overlay}
cloneSource.overlay	Clone Source Overlay	{"show":bool?,"opacity":0..100?,"clipped":bool?,"autoHide":bool?,"invert":bool?,"blend":"normal|darken|lighten|difference"?}
cloneSource.resetTransform	Reset Transform	{"index":0..4?=active}
cloneSource.select	Select Clone Source	{"index":0..4}
cloneSource.set	Set Clone Source	{"index":0..4?=active,"source":[x,y]? (⌥-click; re-pairs with the next stroke),"offset":[dx,dy]?,"width":%?,"height":%?|"scale":[w%,h%]?,"linked":bool? (W/H link: a lone width or height scales the other by the same factor),"rotation":deg?,"flipH":bool?,"flipV":bool?,"layer":id?,"clear":bool?,"select":bool=true}
```

## color（1）

```text
color.profileMismatch	Embedded Profile Mismatch	{"action":"preserve|convert|discard|assignWorking"}
```

## command（1）

```text
command.list	List Commands	{}
```

## count（7）

```text
count.add	Add Count	{"x":px,"y":px,"group":index?}
count.clear	Clear Count	{"group":index|"all"=active}
count.deleteGroup	Delete Count Group	{"group":index=active}
count.move	Move Count	{"index":n,"group":index?,"to":[x,y]} | {"x":px,"y":px,"to":[x,y]}
count.newGroup	New Count Group	{"name":str?,"color":"#rrggbb"|[r,g,b]?}
count.remove	Remove Count	{"index":n,"group":index?} | {"x":px,"y":px,"radius":px=6}
count.setGroup	Count Group Options	{"group":index=active,"name":str?,"color":"#rrggbb"|[r,g,b]?,"markerSize":1..10?,"labelSize":8..72?,"visible":bool?,"active":bool?}
```

## document（11）

```text
document.activate	Activate Document	{"document":index|{"index":uint}} or {"offset":int} (numeric document: zero-based tab index; typed index: one-based opening order; offset: places after the active document in opening order, before it when negative) → {document}
document.inspect	Inspect Document	{"document":index?}
document.move	Move Document	{"document":index?,"to":index}
document.pixel	Read Composite Pixel	{"x":i32,"y":i32}
document.presets.delete	Delete Document Preset	{"name":str}
document.presets.get	Get Document Preset	{"name":str} -> {preset,params} (params for file.new; no document is created)
document.presets.list	List Document Presets	{}
document.presets.save	Save Document Preset	{"name":str (trimmed, ASCII case-insensitive unique, 1..255 characters),"settings":{"width":px,"height":px,"resolution":ppi=72,"mode":"rgb|gray|cmyk|lab"="rgb","depth":8|16|32=8,"background":"white|black|transparent|backgroundColor|#rrggbb"="white","backgroundColor":[r,g,b]?,"unit":"px|in|cm|mm|pt|pica"="px","resolutionUnit":"in|cm"="in"}}
document.recent.add	Add Recent Document Settings	{"settings":{same fields as document.presets.save}} (File › New records each document it creates; newest first, max 20, duplicates collapsed)
document.recent.list	List Recent Document Settings	{} -> {recent:[settings]} (newest first; each settings.command params minus unit/resolutionUnit go to file.new)
document.sampleColor	Sample Color	{"x":f64,"y":f64,"size":"point"|1|3|5|11|31|51|101=1,"sampleLayer":"current"|"currentAndBelow"|"all"|"allNoAdjustments"|"currentAndBelowNoAdjustments"="all","zoom":f64? (the view zoom, 1 = 100 %: at 100 % and below an N by N Average covers (N+1)×(N+1) screen pixels, as in Photoshop; missing: the centred square)} → [r,g,b,a] (the Eyedropper's Sample Size and Sample: the composite pixel, or the average of the size×size square centred on it (without `zoom`; with it, the zoom-dependent box above), clipped to the canvas; transparent off the canvas)
```

## edit（79）

```text
edit.assignProfile	Assign Profile…	{"profile":"working|srgb|display-p3|adobe-rgb-compat|prophoto-compat|linear-srgb|rec2020|gray-gamma-2.2|sgray|dot-gain-20-compat|lab-d50|coated-cmyk|none" (or a path to an .icc file)}
edit.autoAlignLayers	Auto-Align Layers…	{"projection":"auto|perspective|cylindrical|spherical|collage|reposition","reference":layer id?=the locked selected layer, else the bottom selected layer,"geometricCorrection":bool=false,"interpolation":"bicubic|bilinear|nearest","registration":"auto|features|intensity"}
edit.autoBlendLayers	Auto-Blend Layers…	{"method":"panorama|stack","seamlessTones":bool=true,"haloControl":0..8=2,"depthMap":bool=false}
edit.checkSpelling	Check Spelling…	{"action":"list|change|changeAll|addToDictionary|removeFromDictionary|suggest"="list","allLayers":bool=true,"layer":id|name? (check one layer),"ignore":[word]? (Ignore All for this check),"suggestions":n=5; change: "layer"? (default: the active layer),"start","end" (chars),"word"? (verified),"replace"; changeAll: "word","replace"; addToDictionary/removeFromDictionary/suggest: "word"} → list: {"misspellings":[{"layer","start","end","word","suggestions"}],"count"} (an action records only a call without "action", as {"allLayers"} with its dialog on)
edit.clear	Clear	{"target":"mask"|{"color":i}|{"colors":[i,…]}?=Channels panel target,"layer":id|name?=active} (a targeted mask, channel or Quick Mask is cleared alone)
edit.colorSettings	Color Settings…	{"workingRgb":"srgb|display-p3|adobe-rgb-compat|prophoto-compat|linear-srgb|rec2020","workingCmyk":"coated-cmyk","workingGray":"dot-gain-20-compat|sgray|gray-gamma-2.2","policyRgb":"preserve|convert|off","policyCmyk":"preserve|convert|off","policyGray":"preserve|convert|off","askOnMismatch":bool=true,"askOnPaste":bool=true,"askOnMissing":bool=false,"intent":"relative|perceptual|saturation|absolute","blendTextGamma":1.0..2.2|bool=1.45,"spotDotGain":0..49=20,"bpc":bool=true,"dither":bool=true,"monitorProfile":"auto|srgb|display-p3|adobe-rgb-compat|prophoto-compat|rec2020","reset":bool=false} (spotDotGain = the Spot working space: the dot gain, in % at a 50 % dot, that spot channel previews add, as Photoshop's Spot menu (Dot Gain 10–30 %, or a custom value); working spaces and the monitor profile also accept .icc paths; monitor `auto` = the main display's profile when the platform provides it, else sRGB; the reply's `monitorStatus` says which profile is in use and why: source auto|manual|fallback, reason)
edit.contentAwareFill	Content-Aware Fill…	{"sampling":"auto|rectangular|custom","margin":px?,"area":[x,y,w,h]?,"channel":index|name?,"samplingStrokes":[{"mode":"add|subtract","size":px,"points":[[x,y],…]}]? (the workspace's Sampling Brush, after the sampling option's area; added strokes may lie outside the window),"fillEdits":[{"op":"new|add|subtract|intersect","points":[[x,y],…]}|{"op":"expand|contract","by":px}]? (the workspace's lasso edits of the fill area, in order),"sampleAllLayers":bool=false,"colorAdaptation":"default|none|high|veryHigh","rotationAdaptation":"none|low|medium|high|full","scale":bool=false,"mirror":bool=false,"output":"current|new|duplicate","layer":id|name?=active (the layer filled and sampled),"seed":u64=1}
edit.contentAwareScale	Content-Aware Scale	{"width":px?,"height":px?,"scaleX":1..400=100,"scaleY":1..400=100,"x":px?,"y":px?,"amount":0..100=100,"protect":"none"|channel index|name,"protectSkinTones":bool=false}
edit.convertToProfile	Convert to Profile…	{"profile":"srgb|display-p3|adobe-rgb-compat|prophoto-compat|linear-srgb|rec2020|gray-gamma-2.2|sgray|lab-d50|coated-cmyk|working" (or a path to an .icc file),"intent":"perceptual|relative|saturation|absolute"="relative","bpc":bool=true,"dither":bool=false (deterministic color quantization for 8-bit profile changes),"flatten":bool=false (flatten in the source profile before conversion),"rasterizePlaced":bool=false (freeze displayed Smart Object pixels; flatten takes precedence)}
edit.copy	Copy	{"target":"mask|filterMask"|{"color":i}|{"colors":[i,…]}?=Channels panel target,"layer":id|name?=active (colour targets only)} (a targeted mask, colour or alpha channel copies that channel as grayscale; a colour set copies its selected components)
edit.copyMerged	Copy Merged	{}
edit.cut	Cut	{"target":"mask|filterMask"|{"color":i}|{"colors":[i,…]}?=Channels panel target,"layer":id|name?=active (colour targets only)} (a targeted mask or colour channel cuts that channel only; a colour set cuts its selected components)
edit.defineBrushPreset	Define Brush Preset…	{"name":text}
edit.defineCustomShape	Define Custom Shape…	{"name":text,"path":"work|<saved path name>"?}
edit.definePattern	Define Pattern…	{"name":text,"rect":[x0,y0,x1,y1]?} → {"pattern":id} (name: default the document's name numbered past the library's names; rect: default the selection bounds or else the canvas; added to the library from the visible composite)
edit.deleteAndFillSelection	Delete and Fill Selection	{}
edit.fade	Fade…	{"opacity":0..100=100,"mode":"normal|multiply|screen|overlay|softLight|hardLight|darken|lighten|difference|color|luminosity"}
edit.fill	Fill…	{"contents":"foreground|background|color|contentAware|pattern|history|black|gray|white"="color","color":"#rrggbb|[r,g,b,a]"=foreground (contents=color),"pattern":id|name (contents=pattern),"scale":%=100,"angle":deg,"state":row?,"snapshot":id? (contents=history: a History panel row as history.setSource, redo rows last, or a snapshot; default the History Brush source),"colorAdaptation":bool=true,"scaleAdaptation":bool=false,"mirror":bool=false,"rotationAdaptation":bool=false (contents=contentAware: enable quarter-turn source candidates within the sampling budget),"mode":"normal|multiply|…"="normal","opacity":0..100=100,"preserveTransparency":bool=false,"target":"pixels"|"mask"|"filterMask"|"quickMask"|{"channel":i}?}
edit.fillBackground	Fill with Background Color	{"layer":id|name?,"target":"pixels"|"mask"|"filterMask"|"quickMask"|{"channel":i}?}
edit.fillBackgroundPreserve	Fill with Background Color, Preserve Transparency	{"layer":id|name?,"target":"pixels"|"mask"|"filterMask"|"quickMask"|{"channel":i}?}
edit.fillForeground	Fill with Foreground Color	{"layer":id|name?,"target":"pixels"|"mask"|"filterMask"|"quickMask"|{"channel":i}?}
edit.fillForegroundPreserve	Fill with Foreground Color, Preserve Transparency	{"layer":id|name?,"target":"pixels"|"mask"|"filterMask"|"quickMask"|{"channel":i}?}
edit.fillHistory	Fill from History	{"state":n? (default: the History Brush's source, the oldest state still held),"layer":id?,"target":"pixels"|"mask"|"quickMask"|{"channel":i}?,"preserveTransparency":bool?}
edit.findAndReplaceText	Find and Replace Text…	{"find":text,"replace":text,"action":"changeAll|find|change|changeFind","caseSensitive":bool=false,"wholeWord":bool=false,"forward":bool=true,"allLayers":bool=true}
edit.installedProfiles	Installed Profiles	{"class":"any|input|display|output|deviceLink|colorSpace|abstract|namedColor"="any","colorSpace":"any|rgb|cmyk|gray"="any"} → {profiles: [{path, description, class, colorSpace}], dirs} (the OS profile folders; pass a path as any command's "profile")
edit.keyboardShortcuts	Keyboard Shortcuts…	{"set":{"<command id>|tools.temporary.hand|zoomIn|zoomOut":"Cmd+Shift+X"|""(remove)|null(default)}?,"alternates":{"<command id>":["F3",…]|[](none)|null(default)}?,"reset":true|["<id>",…]?,"removeConflicts":bool=true,"filter":str?,"list":bool=false,"importKys":"<.kys XML>"|{"path":".kys"}?,"useSet":"<name>"|""(defaults)?,"saveSet":"<name>"?,"deleteSet":"<name>"?,"sets":{"<name>":{"shortcuts":{…},"alternateShortcuts":{…}}}?,"activeSet":"<name>"|""?,"exportKys":true|{"path":".kys"}?,"summarize":true|{"mac":bool,"path":".html"}?} (with a path the file is written and the reply has kysPath/htmlPath instead of kys/html)
edit.menus	Menus…	{"hide":["<id>",…]?,"show":["<id>",…]?,"color":{"<id>":"red|orange|yellow|green|blue|violet|gray|none"}?,"reset":bool=false}
edit.paste	Paste	{"as":"pixels|path|shape"? (explicit mode: active layered document/composite only; SVG canvas is centred, Path/Shape require retained vector source),"center":[x,y]? (finite explicit coordinates within ±10 million; default keeps raster position when it overlaps the canvas),"clampToCanvas":bool=true (legacy mode only; keep the paste on the canvas, or at its top-left when larger),"target":"pixels"|"mask"|"quickMask"|{"channel":i}=Channels panel target (not pixels: the luminosity pasted into that mask or channel)} (with no document open: a new document from the clipboard)
edit.pasteSpecial.pasteInPlace	Paste in Place	{"target":"pixels"|"mask"|"quickMask"|{"channel":i}=Channels panel target (not pixels: the luminosity pasted into that mask or channel)}
edit.pasteSpecial.pasteInto	Paste Into	{"center":[x,y]?,"target":"pixels"|"mask"|"quickMask"|{"channel":i}=Channels panel target (not pixels: the luminosity pasted into that mask or channel)}
edit.pasteSpecial.pasteOutside	Paste Outside	{"center":[x,y]?,"target":"pixels"|"mask"|"quickMask"|{"channel":i}=Channels panel target (not pixels: the luminosity pasted into that mask or channel)}
edit.perspectiveWarp	Perspective Warp	{"planes":[{"src":[[x,y]×4],"dst":[[x,y]×4]}…] (corners clockwise from top-left; corners that coincide in src are linked),"straighten":"horizontal|vertical|auto"?,"interpolation":"bicubic|bilinear|nearest","layer":id?}
edit.preferences.cursors	Cursors…	{}
edit.preferences.enhancedControls	Enhanced Controls…	{}
edit.preferences.export	Export…	{}
edit.preferences.fileHandling	File Handling…	{}
edit.preferences.general	General…	{}
edit.preferences.guidesGridAndSlices	Guides, Grid & Slices…	{}
edit.preferences.historyLog	History Log…	{}
edit.preferences.integrations	Integrations…	{}
edit.preferences.interface	Interface…	{}
edit.preferences.performance	Performance…	{}
edit.preferences.plugIns	Plugins…	{}
edit.preferences.rawDefaults	RAW Defaults…	{}
edit.preferences.scratchDisks	Scratch Disks…	{}
edit.preferences.tools	Tools…	{}
edit.preferences.transparencyAndGamut	Transparency & Gamut…	{}
edit.preferences.type	Type…	{}
edit.preferences.unitsAndRulers	Units & Rulers…	{}
edit.preferences.workspace	Workspace…	{}
edit.presets.exportImportPresets	Export/Import Presets…	{"action":"export|import","kinds":["brushes","customShapes","tools"]?,"data":json (import),"includeBuiltins":bool=false}
edit.presets.migratePresets	Migrate Presets	{path} → {migrated, added:{gradients,styles,shapes,patternGroups,toolPresets}}: merge a presets/preferences file into the library (appends groups by name)
edit.presets.presetManager	Preset Manager…	{"action":"list|rename|delete|move","kind":"brushes|customShapes|patterns","index":n?,"name":str?,"newName":str?,"to":n?}
edit.profileInfo	Profile Info	{"profile":"<builtin id>|document|/path/to/profile.icc"=document}
edit.puppetWarp	Puppet Warp	{"pins":[{"src":[x,y],"dst":[x,y],"rotate":deg?,"depth":n?}…],"mode":"rigid|normal|distort"="normal","density":"fewer|normal|more"="normal","expansion":px=2,"interpolation":"bicubic|bilinear|nearest","layer":id?} — mesh over the opaque region, as-rigid-as-possible; on a smart object it becomes a smart filter
edit.purge.all	All	{}
edit.purge.clipboard	Clipboard	{}
edit.purge.histories	Histories	{}
edit.purge.undo	Undo	{}
edit.purge.videoCache	Video Cache	{}
edit.redo	Redo	{}
edit.stroke	Stroke…	{"width":1..250=1,"color":"#rrggbb|[r,g,b,a]"=foreground,"location":"inside|center|outside"="center","mode":"any layer blend mode"="normal","opacity":0..100=100,"preserveTransparency":bool=false}
edit.toggleLastState	Toggle Last State	{}
edit.toolbar	Toolbar…	{"hidden":["<tool>",…]?,"order":["<tool>",…]?,"reset":bool=false}
edit.transform	Free Transform	{"layer":id?,"layers":[id,…]? (several layers moved by one box, one step; default with neither = the selected layers, as Photoshop's Free Transform with several selected; refused as locked when the Background is among several),"rect":[x0,y0,x1,y1]? (source frame; default = the layers' content ∩ selection),"quad":[[x,y]×4]? (where the frame's corners go, clockwise from top-left),"matrix":[a,b,c,d,e,f]? (affine alternative),"scaleX":%?,"scaleY":%?,"rotate":deg?,"dx":px?,"dy":px?,"reference":"center|topLeft|top|topRight|left|right|bottomLeft|bottom|bottomRight"|[x,y]="center" (relative alternative: scale and rotate about this point, then move),"interpolation":"bicubic|bilinear|nearest|bicubicSharper|bicubicSmoother|bicubicAutomatic"="bicubic" (Photoshop's bicubic variants render as Bicubic),"stepName":"Transform Path"? (History step name; the shape tools' bounding box sends it; default "Free Transform"; any other value is refused),"target":"pixels"|"mask"|"quickMask"|{"channel":i}=Channels panel target (an unlinked mask, an alpha channel or the Quick Mask transforms alone; a linked mask moves with its layer)}
edit.transform.again	Again	{}
edit.transform.againCopy	Transform Again on a Copy	{} (duplicates the active layer and repeats the last transform on the copy: step and repeat)
edit.transform.flipHorizontal	Flip Horizontal	{"target":"pixels"|"mask"|"vectorMask"|"quickMask"|{"channel":i}=Channels panel target (an unlinked mask, a vector mask, an alpha channel or the Quick Mask turns alone)}
edit.transform.flipVertical	Flip Vertical	{"target":"pixels"|"mask"|"vectorMask"|"quickMask"|{"channel":i}=Channels panel target (an unlinked mask, a vector mask, an alpha channel or the Quick Mask turns alone)}
edit.transform.removeWarpSplit	Remove Warp Split	{"warp":{…}? (the warp being edited; returned split),"rect":[x0,y0,x1,y1]?,"at":[x,y]? (document point; default = middle of the patch)} — without `warp`, edits the active smart object's warp. A 1×1 custom mesh is divided at the thirds first (the guides drawn on the default grid), so splitWarpCrosswise on an identity custom warp returns a 4×4 mesh (knots at 0, 1/3, 1/2, 2/3 and 1), not a 2×2. A preset is fitted as one patch and split without that step.
edit.transform.rotate180	Rotate 180°	{"target":"pixels"|"mask"|"vectorMask"|"quickMask"|{"channel":i}=Channels panel target (an unlinked mask, a vector mask, an alpha channel or the Quick Mask turns alone)}
edit.transform.rotate90Ccw	Rotate 90° Counter Clockwise	{"target":"pixels"|"mask"|"vectorMask"|"quickMask"|{"channel":i}=Channels panel target (an unlinked mask, a vector mask, an alpha channel or the Quick Mask turns alone)}
edit.transform.rotate90Cw	Rotate 90° Clockwise	{"target":"pixels"|"mask"|"vectorMask"|"quickMask"|{"channel":i}=Channels panel target (an unlinked mask, a vector mask, an alpha channel or the Quick Mask turns alone)}
edit.transform.splitWarpCrosswise	Split Warp Crosswise	{"warp":{…}? (the warp being edited; returned split),"rect":[x0,y0,x1,y1]?,"at":[x,y]? (document point; default = middle of the patch)} — without `warp`, edits the active smart object's warp. A 1×1 custom mesh is divided at the thirds first (the guides drawn on the default grid), so splitWarpCrosswise on an identity custom warp returns a 4×4 mesh (knots at 0, 1/3, 1/2, 2/3 and 1), not a 2×2. A preset is fitted as one patch and split without that step.
edit.transform.splitWarpHorizontally	Split Warp Horizontally	{"warp":{…}? (the warp being edited; returned split),"rect":[x0,y0,x1,y1]?,"at":[x,y]? (document point; default = middle of the patch)} — without `warp`, edits the active smart object's warp. A 1×1 custom mesh is divided at the thirds first (the guides drawn on the default grid), so splitWarpCrosswise on an identity custom warp returns a 4×4 mesh (knots at 0, 1/3, 1/2, 2/3 and 1), not a 2×2. A preset is fitted as one patch and split without that step.
edit.transform.splitWarpVertically	Split Warp Vertically	{"warp":{…}? (the warp being edited; returned split),"rect":[x0,y0,x1,y1]?,"at":[x,y]? (document point; default = middle of the patch)} — without `warp`, edits the active smart object's warp. A 1×1 custom mesh is divided at the thirds first (the guides drawn on the default grid), so splitWarpCrosswise on an identity custom warp returns a 4×4 mesh (knots at 0, 1/3, 1/2, 2/3 and 1), not a 2×2. A preset is fitted as one patch and split without that step.
edit.transform.warp	Warp	{"layer":id?,"rect":[x0,y0,x1,y1]? (warp box; default = layer content ∩ selection),"style":"custom|none|arc|arcLower|arcUpper|arch|bulge|shellLower|shellUpper|flag|wave|fish|rise|fisheye|inflate|squeeze|twist|cylinder","bend":%=50,"hDistort":%,"vDistort":%,"vertical":bool,"values":[left,bottom,right,top,topDepth,bottomDepth,wrap]? (cylinder: silhouettes and edges in document px, the ellipses' depths in half-axis units, wrap 0..1; horizontal only),"mesh":{"us":[0,…,1],"vs":[0,…,1],"points":[[x,y]…]} ((3c+1)×(3r+1) control points, row-major, document px; on a smart object `us`/`vs` span the source contents, so points equal to the placement are an identity warp even when it is skewed),"grid":[cols,rows]?,"warp":{full warp object}?,"interpolation":"bicubic|bilinear|nearest"} — on a type layer a style (or none) sets its Warp Text and the type stays editable
edit.transform.warpGrid	Warp Grid	{"warp":{…}? (the warp being edited; returned with the new mesh),"rect":[x0,y0,x1,y1]?,"size":n|"default"|"3"|"4"|"5" (square patches, 1..=64; 1 and "default" are the single-patch grid)} — without `warp`/`style`/`mesh`, edits the active smart object's warp. The surface is kept and the new lines are real splits at i/n.
edit.undo	Undo	{}
```

## file（60）

```text
file.approveMemory	Approve High Memory PSD Import	{"id":u64,"approve":bool=true,"background":bool=true}
file.automate.batch	Batch…	{"action":name|index|[steps]? (used only when steps is absent; named actions exclude disabled steps),"set":str? (for a named action),"steps":[[commandId,params]|{"command":id,"params":{}}…] (a recorded action; a Save, Save As or Save a Copy step marks the document written to output, in this command's format and options: as the save found it if it was closed or another document is active at the end, else as the action leaves it; with no such step, the active document at the end),"source":"folder|open"="folder" (open runs on live documents),"input":folder|[paths] (folder source),"errorLog":path? (blank disables it),"suppressOpenOptions":bool=false (use caller RAW defaults and fully supported prior XMP without a dialog; unsupported prior settings or unanswerable profile questions fail the input),"suppressWarnings":bool=false (apply caller opening policy without profile questions; import diagnostics remain in notices),"overrideOpen":bool=false (execute action Open steps with the current input path, retaining other Open options; without an executed Open the input fails),"includeNonImages":bool=false (folder inputs report unsupported files as per-file errors instead of skipping them; arrays are unchanged),"includeSubfolders":bool=false (a folder input also takes the images in its subfolders, up to 32 levels and 100000 files; ordinary outputs are flat; namingComponents can retain subfolders when flatOutput is false),"destination":"folder|saveAndClose"="folder" (Save and Close writes the same source path/format; rejects already-open sources and changed result document identity),"output":folder? (required only for folder; omit for Save and Close),"format":"same|png|jpg|psd|tiff|…"="same" (Save and Close requires same),"quality":0..12?,"jpegFormat":"baseline|optimized|progressive"?,"namingComponents":[{"component":choice}|{"text":str}]? (up to six; the exact filename, with no automatic extension),"compatibility":{"macintosh":bool,"windows":bool,"unix":bool}?,"flatOutput":bool=false (structured naming only; put every result directly under output, dropping its subfolder path; duplicate output names make later results error entries),"overrideSaveAs":bool? (recorded routing; requires a directly represented Save configuration),"stopOnError":bool=false (report the first failed input and stop; earlier outputs remain saved),"naming":string? (blank keeps source names; {name}/{NAME}/{Name}, {serial}/{serial:1..4}, {letter}/{LETTER}, {date} and date formats, {ext}/{EXT}; template determines the whole filename),"startingSerial":1..4294967295=1 (input position, including failed inputs),"tiffLayers":bool? (Folder default false; Save and Close default true, with false refused when TIFF layer data would be lost),"tiffCompression":"none|lzw|zip"?,"tiffTransparency":bool?,"tiffPyramid":bool=false,"tgaBits":24|32?,"dpxBits":8|10|12|16? (DPX: bits per sample; unset, 8 for an 8-bit document, else 16),"ddsCompression":"none|bc1|bc2|bc3"="none" (DDS: uncompressed, or block compression; BC1 keeps alpha on or off),"ddsMipmaps":bool=false (DDS: also write the full mip chain),"maximizeCompatibility":bool? (PSD/PSB: write the real merged image; unset, Preferences > File Handling > Maximize PSD and PSB File Compatibility),"pdfSpotPlates":bool=true (PDF: spot channels as overprinting Separation plates after the image; a Multichannel document as plates alone, so false refuses it),"calledActions":[{"name","steps"}…]? (internal action references; default: the session's; a named source is selected from the caller)} → {files, errors, stopped?, skipped?, errorLog?, documents?} (structured naming, includeNonImages and Save and Close refuse duplicate results; ordinary native templates keep the later result)
file.automate.conditionalModeChange	Conditional Mode Change…	{"from":["rgb","grayscale","cmyk","lab","indexed","bitmap",…]|"any"="any","to":"rgb|grayscale|cmyk|lab"}
file.automate.contactSheetII	Contact Sheet II…	{"input":folder|[paths],"units":"inches|cm|mm|pixels"="inches","width":8,"height":10,"resolution":ppi=300,"mode":"rgb|gray|cmyk|lab"="rgb","depth":8|16=8,"columns":5,"rows":6,"placeAcrossFirst":bool=true,"autoSpacing":bool=true,"horizontal":units?,"vertical":units?,"rotateForBestFit":bool=false,"caption":bool=true (file name as caption),"font":family?,"fontSize":pt=12,"flatten":bool=false} → {documents, pages, images}
file.automate.createDroplet	Create Droplet…	{"path":str (.pcdroplet),"steps":[[id,params]…]?,"action":name|index|[steps]? (used only when steps is absent; named actions exclude disabled steps),"set":str? (with a named action: that set's action of the name),"name":str?,"output":folder?,"format":"same|png|jpg|…"?,"quality":0..12?,"shim":bool=true on Unix (writes <name>.command calling `photocraft-cli droplet`)} → {path, shim} (the actions its Play Action and Conditional steps call are saved in the droplet)
file.automate.cropAndStraightenPhotos	Crop and Straighten Photos	{} → one new document per photo found on the scan (inside the selection when there is one)
file.automate.fitImage	Fit Image…	{"width":px,"height":px,"dontEnlarge":bool=false,"resample":"automatic|preserveDetails|bicubicSmoother|bicubicSharper|bicubicAutomatic|bicubic|nearest|bilinear|lanczos"="bicubic"}
file.automate.lensCorrection	Lens Correction…	{"input":folder|[files],"output":folder,"format":"same|jpg|png|tif|psd","quality":0..12?, …Filter › Lens Correction params ("profile" defaults to "auto")}
file.automate.mergeToHdrPro	Merge to HDR Pro…	{"paths":[str]|folder,"useOpenDocuments":bool=false,"exposures":[ev]? (default EXIF, else estimated),"align":bool=true,"removeGhosts":bool=false,"ghostBase":int?,"mode":"32|16|8","method":"localAdaptation|exposureGamma|highlightCompression|equalizeHistogram","radius":1..500=7,"strength":0.1..4=0.52,"gamma":0.1..2=1,"exposure":-5..5=0,"detail":-100..300=30,"shadow":-100..100=0,"highlight":-100..100=0,"vibrance":-100..100=0,"saturation":-100..100=20} → new document (32-bit linear, or tone-mapped 16/8-bit)
file.automate.photomerge	Photomerge…	{"paths":[str]|folder,"useOpenDocuments":bool=false,"layout":"auto|perspective|cylindrical|spherical|collage|reposition","blend":bool=true,"vignetteRemoval":bool=false,"geometricCorrection":bool=false,"contentAwareFill":bool=false,"focalLength":mm=0 (35 mm equivalent; 0 = EXIF or estimated),"memoryBudget":bytes?=half of RAM} → new document, one masked layer per image
file.automate.runDroplet	Run Droplet	{"droplet":path,"input":[files or folders],"output":folder? (default: droplet's, else <input folder>/droplet-output)} → {files, errors} (an input whose output name was already written in the run goes to errors)
file.close	Close	{"document":index?,"save":"discard|ask"|false="discard"} (false means discard; ask refuses to close a changed document in headless playback)
file.closeAll	Close All	{}
file.closeOthers	Close Others	{"document":index? (the one to keep; default active)}
file.export.artboardsToFiles	Artboards to Files…	{"dir":folder,"format":"png|jpg|psd|tiff|…"="png","prefix":str=document name ("" = none),"artboards":[id]? (default all),"quality":0..12?} → {files}
file.export.artboardsToPdf	Artboards to PDF…	{"path":str (.pdf),"artboards":[id]?,"quality":0..12=10} → {path, pages} (one raster page per board)
file.export.colorLookupTables	Color Lookup Tables…	{"path":str? (.cube; omit to return the text),"size":2..129=33,"title":str?,"scope":"all|selected"="all","layers":[id,…]?} (selected layer IDs use original document stacking; masks are spatial and omitted)
file.export.dataSetsAsFiles	Data Sets as Files…	{dir, format?:png, dataSets?[names], naming?:"{name}|{index}|{document}"} → {files,count}: apply each data set and export the flattened document; colliding filenames are rejected before writing (include {index} to disambiguate)
file.export.exportPreferences	Export Preferences…	{"quickExportFormat":"png|jpg|gif|webp|exr"?,"quickExportLocation":"ask|sameFolder"?,"jpegQuality":1..100?,"webpLossless":bool?,"webpQuality":1..100?,"metadata":"none|copyright|all"?,"convertToSrgb":bool?} → {values}
file.export.layerCompsToFiles	Layer Comps to Files…	{"dir":folder,"format":"png|jpg|psd|tiff|…"="png","prefix":str=document name,"selectedOnly":bool=false (only the last applied comp),"comps":[id]?,"quality":0..12?} → {files}
file.export.layersToFiles	Layers to Files…	{"dir":folder,"format":"png|jpg|psd|tiff|…"="png","prefix":str=document name,"visibleOnly":bool=true,"trim":bool=false,"quality":0..12?,"jpegFormat":"baseline|optimized|progressive"?,"tiffLayers":bool=false,"tiffCompression":"none|lzw|zip"?,"tiffTransparency":bool?,"tiffPyramid":bool=false,"tgaBits":24|32?,"dpxBits":8|10|12|16? (DPX: bits per sample; unset, 8 for an 8-bit document, else 16),"ddsCompression":"none|bc1|bc2|bc3"="none" (DDS: uncompressed, or block compression; BC1 keeps alpha on or off),"ddsMipmaps":bool=false (DDS: also write the full mip chain),"maximizeCompatibility":bool? (PSD/PSB: write the real merged image; unset, Preferences > File Handling > Maximize PSD and PSB File Compatibility),"pdfSpotPlates":bool=true (PDF: spot channels as overprinting Separation plates after the image; a Multichannel document as plates alone, so false refuses it)} → {files}
file.export.pathsToIllustrator	Paths to Illustrator…	{"path":str? (.ai; omit to return the text),"paths":"all|work|<path name>"="all"} → {path, paths}
file.export.presets.delete	Delete Export Preset	{"name":str}
file.export.presets.get	Get Export Preset	{"name":str} -> {preset} (settings for Export As; nothing is exported)
file.export.presets.list	List Export Presets	{}
file.export.presets.save	Save Export Preset	{"name":str,"settings":{"format":"png|jpg|webp|tif|tga|ico","quality":1..100,"lossless":bool,"transparency":bool,"scale":1..1000,"width":px,"height":px,"lockAspect":bool,"sizing":"scale|pixels","metadata":"none|exif|all","profile":"document|srgb","embedProfile":bool,"tgaBits":"auto|24|32","resample":"bicubicAutomatic|bicubic|bicubicSmoother|bicubicSharper|bilinear|nearest"="bicubicAutomatic"}} (a saved name is replaced)
file.export.quickExport	Quick Export	{"path":str? (required unless Export Preferences › Location is "sameFolder" and the document is saved)} → {path, format, bytes, warnings}
file.export.renderVideo	Render Video…	{} → {}
file.export.saveForWebLegacy	Save for Web (Legacy)…	{"preset":"GIF 128 Dithered|JPEG High|PNG-24|…"?,"format":"gif|png8|png24|jpeg|wbmp|webp"="png24","palette":"perceptual|selective|adaptive|restrictive|exact|systemMac|systemWindows|uniform"="selective","colors":2..256=256,"colorTable":["#rrggbb",…]? (fixed opaque source palette, 1–256 entries; 255 with transparency),"colorTableEdits":{"0":"#rrggbb",…}? (replace entries after indexing; requires colorTable),"dither":"none|diffusion|pattern|noise"="diffusion","ditherAmount":0..100=88,"transparency":bool=true,"matte":"#rrggbb|none"="none" (a preset's own: white; formats without transparency go over white),"interlaced":bool=false,"webSnap":0..100=0,"quality":0..100=60 (JPEG, lossy WebP),"lossless":bool=false (WebP),"progressive":bool=false,"optimized":bool=true,"embedIcc":bool=false,"metadata":"none|copyright|copyrightAndContact|allExceptCameraInfo|all"="copyright" (EXIF only with all),"convertToSrgb":bool=true,"width"|"height"|"percent"? (image size),"resample":"bicubic|bilinear|nearest"?,"path":file? (whole image),"folder":folder? (whole image, named after the document; ignored with "path" or "dir"),"dir":folder? (one file per slice in images/),"imagesFolder":relative-folder?="images","html":bool=false,"trustedSliceHtml":bool=false (only for trusted documents; emit raw no-image cell HTML),"slices":"all|user|selected"="all" (selected requires numbers when the document has slices),"numbers":[n]? (slice numbers, each an existing slice; chooses the slices whatever the mode; with `path` or `folder` alone on a document with slices, refused: use `dir`)} → no path/dir: {bytes,width,height,colors,colorTable,transparentIndex} estimate; else {files, html, bytes, warnings}
file.exrParts	EXR Parts Info	{"path":str (the EXR file)}
file.fileInfo	File Info…	{"title":str?,"author":str?,"authorTitle":str?,"description":str?,"keywords":[str]|"a; b"?,"copyright":str?,"copyrightStatus":"unknown|copyrighted|publicDomain"?,"copyrightUrl":str?} (no keys: read; the result also has read-only "camera":{"make","model","dateTaken","exposure","fNumber","iso","focalLength","focalLength35mm","lens"}, present keys only)
file.generate.imageAssets	Image Assets	{"on":bool? (default: toggle),"dir":folder? (default <document>-assets next to the file)} → {enabled, files, errors}; layers named like "foo.png", "200% foo@2x.png", "48x48 icons/a.png8", "photo.jpg80%" are exported, now and after each save
file.import.notes	Notes…	{"path":".psd|.psb|.pcraft with notes"}
file.import.variableDataSets	Variable Data Sets…	{path, delimiter?} → {imported}: CSV header = variable names, each row a data set (first column may be the data-set name)
file.import.videoFramesToLayers	Video Frames to Layers…	{} → {}
file.import.wiaSupport	WIA Support…	{} → {available, devices, note}: acquire from a scanner/camera (Windows only)
file.new	New…	{"width":1..300000=1920,"height":1..300000=1080 (pixel counts are rounded),"mode":"rgb|gray|grayscale|cmyk|lab"="rgb","depth":8|16|32=8,"background":"white|black|backgroundColor|transparent|#rrggbb"="white","backgroundColor":[r,g,b]? (0..1; defaults to toolbox colour),"resolution":1..30000=72 (ppi),"name":str,"artboard":bool=false (one artboard over the canvas, its background the chosen one, holding an empty Layer 1; no Background layer),"profile":"working"|built-in id|path to an .icc file="working" (the colour profile it is tagged with; it must suit the mode)}
file.newFromClipboard	New from Clipboard	{} (a new document the size of the clipboard image, holding it as one layer)
file.openAs	Open As…	{"path":str,"as":"psd|png|jpg|tiff|…"? (decode as this format),"approveHighMemory":bool=false (explicitly approve high memory usage)}
file.openAsSmartObject	Open as Smart Object…	{"path":str,"confirmDamage":bool=false (a damaged PSD waits for an answer, as File > Open's does)} (opens the file as a new untitled document named "<file name without its last extension>-N" with the file's size, resolution, colour mode, bit depth and profile, holding one embedded smart object layer named after the file) → {document, docId, name, layer, warnings, color, smartObject} (or {held, name, warnings, color, damaged, smartObject} while a prompt waits)
file.openExrParts	Open EXR Parts…	{"path":str (the EXR file),"view":"both|left|right"="both","part/<name>":bool (import this part as a layer),"group/<name>":bool (import this channel group as a layer),"precomp":bool=false (add the additive beauty precomp from the AOVs)}
file.package	Package…	{"dir":folder,"format":"pcraft|psd|psb"="pcraft"} → {folder, document, links, missing} (copies the document and its linked files into <dir>/<name>/, relinked to Links/)
file.placeEmbedded	Place Embedded…	{"path":str,"scale":%? (default: fit when larger than the canvas),"fit":bool? (default: Preferences > General > Resize Image During Place),"smartObject":bool? (default: Preferences > General > Always Create Smart Objects When Placing),"center":[x,y]?,"approveHighMemory":bool=false (explicitly approve high memory usage),"frame":id|false? (default: selected frame)}
file.placeLinked	Place Linked…	{"path":str,"scale":%?,"fit":bool? (default: Preferences > General > Resize Image During Place),"center":[x,y]?,"approveHighMemory":bool=false (explicitly approve high memory usage),"frame":id|false? (default: selected frame)}
file.print	Print…	{"printerSettings":hex? (Windows driver settings),"printer":name? (default printer),"copies":1..999=1,"paper":"letter|legal|tabloid|a3|a4|a5|4x6|5x7"|[w,h] pt="letter","orientation":"portrait|landscape"="portrait","center":bool=true,"top":in?,"left":in?,"scale":%=100,"scaleToFit":bool=false,"printable":[x,y,w,h] pt? (the driver's printable area from the paper's top-left, as file.print.page reports it; Scale to Fit Media fits it, else the paper minus 18 pt; a native Windows print reads the driver's own instead),"colorHandling":"printerManages|photocraftManages|noColorManagement"="printerManages","printerProfile":profile? (photocraftManages),"intent":"perceptual|relative|saturation|absolute"="relative","bpc":bool=true,"cornerCropMarks":bool,"centerCropMarks":bool,"registrationMarks":bool,"bleed":in=0 (Functions › Bleed: corner crop marks this far inside the image edge, on the trim line),"description":bool,"labels":bool,"emulsionDown":bool=false (mirror the page left to right, for sublimation and other transfer printing),"output":pdf path? (print to PDF; then "send" defaults to false),"send":bool?,"printServer":"host[:port]|socket path"? (default: the system's CUPS; a named server is always printed to over IPP),"dryRun":bool=false (render the PDF, report the backend command, don't spool; write a PDF only at an explicit output path)} → {pdf:path|null (null without explicit output), imageRect, command:diagnostic array|null, sent, spooler:where the job went|null, backend:"lp|windows|ipp|portal"|null}
file.print.page	Printer Page	{"printer":name? (default printer),"printerSettings":hex?,"orientation":"portrait|landscape"? (turn the settings, or the printer's own, that way)} → {printer, paper: [w,h] pt, printable: [x,y,w,h] pt from the top-left, dpi: [x,y], printerSettings: hex (only with orientation: the turned settings)} (Windows)
file.print.printers	Printers	{} → {supported, printers: [{name, default}]} (supported: Windows; elsewhere Print spools with lp)
file.printers	Printers	{} → {printers:[{name, default}], default:name|null} (the system spooler's printers; a name is Print's "printer")
file.printOneCopy	Print One Copy	{} (the last Print settings, one copy; any Print key overrides)
file.revealInFinder	Reveal in Finder	{"document":index? (default active),"dryRun":bool=false}
file.revert	Revert	{} (reloads the saved file as one undoable step)
file.saveACopy	Save a Copy…	{"path":str (format from the extension),"quality":0..12? (JPEG),"jpegFormat":"baseline|optimized|progressive"? (JPEG; default baseline),"layers":bool=true,"overwrite":bool=false (replace the document's own file),"tiffLayers":bool=false (TIFF: keep the layers; flat by default),"tiffCompression":"none|lzw|zip"? (TIFF: image compression; unset, none),"tiffTransparency":bool? (TIFF: Save Transparency; off composites over white; unset, kept unless the document has alpha or spot channels),"tiffPyramid":bool=false (TIFF: Save Image Pyramid, half-size copies after the image),"tgaBits":24|32? (TGA: 32 writes the alpha channel, or else the transparency, as the alpha; unset, 32 with an alpha channel or transparency, else 24),"dpxBits":8|10|12|16? (DPX: bits per sample; unset, 8 for an 8-bit document, else 16),"ddsCompression":"none|bc1|bc2|bc3"="none" (DDS: uncompressed, or block compression; BC1 keeps alpha on or off),"ddsMipmaps":bool=false (DDS: also write the full mip chain),"maximizeCompatibility":bool? (PSD/PSB: write the real merged image; unset, Preferences > File Handling > Maximize PSD and PSB File Compatibility),"pdfSpotPlates":bool=true (PDF: spot channels as overprinting Separation plates after the image; a Multichannel document as plates alone, so false refuses it),"pcraftFullComposite":bool? (.pcraft: request the flattened document at its canvas size as composite/full.png; it may be omitted; check the manifest's full_composite member; unset, Preferences › File Handling)}
file.scripts.browse	Browse…	{"path":script file | "script":text | "steps":[[id,params]…]} (JSON action, or one `command.id {json}` per line) → {steps, ok, results}
file.scripts.deleteAllEmptyLayers	Delete All Empty Layers	{}
file.scripts.flattenAllLayerEffects	Flatten All Layer Effects	{}
file.scripts.flattenAllMasks	Flatten All Masks	{} (pixel layers; masks on other layer kinds are left)
file.scripts.imageProcessor	Image Processor…	{"source":"folder|current|open"="folder" (current processes a copy of the active document; open processes copies of all open documents, including unsaved edits; originals and history stay unchanged),"input":folder|[paths]? (required for folder source),"includeSubfolders":bool=false (a folder input also takes the images in its subfolders, up to 32 levels and 100000 files; each result keeps its subfolder under output),"output":folder,"format":"jpg|png|psd|tiff|…"="jpg","quality":0..12=8,"jpegFormat":"baseline|optimized|progressive"?,"tiffLayers":bool=false,"tiffCompression":"none|lzw|zip"?,"tiffTransparency":bool?,"tiffPyramid":bool=false,"tgaBits":24|32?,"dpxBits":8|10|12|16? (DPX: bits per sample; unset, 8 for an 8-bit document, else 16),"ddsCompression":"none|bc1|bc2|bc3"="none" (DDS: uncompressed, or block compression; BC1 keeps alpha on or off),"ddsMipmaps":bool=false (DDS: also write the full mip chain),"maximizeCompatibility":bool? (PSD/PSB: write the real merged image; unset, Preferences > File Handling > Maximize PSD and PSB File Compatibility),"pdfSpotPlates":bool=true (PDF: spot channels as overprinting Separation plates after the image; a Multichannel document as plates alone, so false refuses it),"width":px?,"height":px? (fit, never enlarge),"convertToSrgb":bool=false} → {files, errors} (an input whose output name was already written in the run goes to errors)
file.scripts.loadFilesIntoStack	Load Files into Stack…	{"paths":[str]|folder,"align":bool=false (Auto-Align Layers on them first),"createSmartObject":bool=false} → new document with one layer per file (inside one smart object with createSmartObject)
file.scripts.scriptEventsManager	Script Events Manager…	{"enabled":bool?,"add":{"event":"startApplication|newDocument|openDocument|saveDocument|closeDocument|print|export|everything","script":path?|"steps":[…]?,"name":str?}?,"remove":index?,"removeAll":bool?} → {enabled, bindings, events}
file.scripts.statistics	Statistics…	{"mode":"mean|median|maximum|minimum|range|summation|variance|standardDeviation|skewness|kurtosis|entropy"="median","input":folder|[paths],"align":bool=false (Auto-Align first)} → new document with one stack-mode smart object
```

## filter（124）

```text
filter.adaptiveWideAngle	Adaptive Wide Angle…	{"model":"auto|fisheye|perspective|fullSpherical","focalLength":0..200=0,"cropFactor":0.1..10=1,"scale":50..150=100,"constraints":[{"a":[x,y],"b":[x,y],"orientation":"free|horizontal|vertical"}]}
filter.blur.average	Average	{}
filter.blur.blur	Blur	{}
filter.blur.blurMore	Blur More	{}
filter.blur.boxBlur	Box Blur…	{"radius":1..2000=1}
filter.blur.gaussianBlur	Gaussian Blur…	{"radius":0.1..1000=1}
filter.blur.lensBlur	Lens Blur…	{"radius":0..100=15,"shape":"hexagon|triangle|square|pentagon|heptagon|octagon","bladeCurvature":0..100=0,"rotation":0..360=0,"depthMap":"none|transparency|layerMask|channel","depthChannel":index|name?,"focalDistance":0..255=0,"invert":bool,"brightness":0..100=0,"threshold":0..255=255,"noise":0..100=0,"distribution":"uniform|gaussian","monochromatic":bool,"seed":u32=0}
filter.blur.motionBlur	Motion Blur…	{"angle":-360..360=0,"distance":1..2000=10}
filter.blur.radialBlur	Radial Blur…	{"amount":1..100=10,"method":"spin|zoom","quality":"draft|good|best"="good","centerX":0..1=0.5,"centerY":0..1=0.5}
filter.blur.shapeBlur	Shape Blur…	{"radius":5..1000=10,"shape":"circle|ring|square|diamond|triangle|hexagon|star|heart|cross","shapeId":str?,"shapeName":str?,"shapePath":json?,"shapeOriginType":9? (recorded ATN metadata)} (custom shape: exact installed id, name, or portable path; ids never fall back to names)
filter.blur.smartBlur	Smart Blur…	{"radius":0.1..100=3,"threshold":0.1..100=25,"quality":"high|medium|low","mode":"normal|edgeOnly|overlayEdge"}
filter.blur.surfaceBlur	Surface Blur…	{"radius":1..100=5,"threshold":2..255=15}
filter.blurGallery.fieldBlur	Field Blur…	{"blur":0..500=15,"centerX":0..1=0.5,"centerY":0..1=0.5,"pins":json}
filter.blurGallery.irisBlur	Iris Blur…	{"blur":0..500=15,"centerX":0..1=0.5,"centerY":0..1=0.5,"radiusX":0.01..1=0.35,"radiusY":0.01..1=0.25,"angle":-180..180=0,"roundness":0..100=0,"feather":0..0.99=0.5,"pins":json}
filter.blurGallery.pathBlur	Path Blur…	{"speed":0..500=50,"taper":0..100=0,"startX":0..1=0.2,"startY":0..1=0.5,"endX":0..1=0.8,"endY":0..1=0.5,"paths":json}
filter.blurGallery.spinBlur	Spin Blur…	{"blurAngle":0..360=15,"centerX":0..1=0.5,"centerY":0..1=0.5,"radiusX":0.01..1=0.3,"radiusY":0.01..1=0.3,"angle":-180..180=0,"pins":json}
filter.blurGallery.tiltShift	Tilt-Shift…	{"blur":0..500=15,"centerX":0..1=0.5,"centerY":0..1=0.5,"angle":-90..90=0,"focus":0..1=0.1,"transition":0.01..1=0.15}
filter.cameraRaw	RAW Develop Filter…	{"temperature":-100..100=0,"tint":-100..100=0,"exposure":-5..5=0,"contrast":-100..100=0,"highlights":-100..100=0,"shadows":-100..100=0,"whites":-100..100=0,"blacks":-100..100=0,"texture":-100..100=0,"clarity":-100..100=0,"dehaze":-100..100=0,"vibrance":-100..100=0,"saturation":-100..100=0,"curveHighlights":-100..100=0,"curveLights":-100..100=0,"curveDarks":-100..100=0,"curveShadows":-100..100=0,"curveSplits":[25,50,75],"pointCurve":[[in,out]],"pointCurveRed":[[in,out]],"pointCurveGreen":[[in,out]],"pointCurveBlue":[[in,out]],"hslHue":[8],"hslSat":[8],"hslLum":[8],"gradeShadows":{"hue":deg,"sat":0..100,"lum":-100..100},"gradeMidtones":{},"gradeHighlights":{},"gradeGlobal":{},"gradeBlending":0..100=50,"gradeBalance":-100..100=0,"shadowTint":-100..100=0,"calibrationHue":[red,green,blue] -100..100,"calibrationSat":[red,green,blue] -100..100 (the Calibration panel: Shadows tint and the primaries' hue and saturation),"sharpenAmount":0..150=0,"sharpenRadius":0.5..3=1,"sharpenDetail":0..100=25,"sharpenMasking":0..100=0,"noiseLuminance":0..100=0,"noiseLuminanceDetail":0..100=50,"noiseColor":0..100=0,"noiseColorDetail":0..100=50,"grainAmount":0..100=0,"grainSize":0..100=25,"grainRoughness":0..100=50,"vignetteAmount":-100..100=0,"vignetteMidpoint":0..100=50,"vignetteRoundness":-100..100=0,"vignetteFeather":0..100=50,"vignetteHighlights":0..100=0,"vignetteStyle":"highlightPriority|colorPriority|paintOverlay","seed":u32=0}
filter.convertForSmartFilters	Convert for Smart Filters	{"layer":id?} (default: combine selected layers)
filter.distort.displace	Displace…	{"horizontal":-999..999=10,"vertical":-999..999=10,"fit":"stretch|tile","undefinedAreas":"repeat|wrap","mapDocument":doc,"mapPath":text,"mapLayer":json}
filter.distort.pinch	Pinch…	{"amount":-100..100=50}
filter.distort.polarCoordinates	Polar Coordinates…	{"mode":"rectangularToPolar|polarToRectangular"}
filter.distort.ripple	Ripple…	{"amount":-999..999=100,"size":"small|medium|large"}
filter.distort.shear	Shear…	{"amount":-100..100=0,"undefinedAreas":"wrap|repeat","points":json}
filter.distort.spherize	Spherize…	{"amount":-100..100=100,"mode":"normal|horizontalOnly|verticalOnly"}
filter.distort.twirl	Twirl…	{"angle":-999..999=50}
filter.distort.wave	Wave…	{"generators":1..999=5,"wavelengthMin":1..998=10,"wavelengthMax":2..999=120,"amplitudeMin":1..998=5,"amplitudeMax":1..999=35,"type":"sine|triangle|square","undefinedAreas":"wrap|repeat","seed":u32=0}
filter.distort.zigZag	ZigZag…	{"amount":-100..100=10,"ridges":0..20=5,"style":"pondRipples|outFromCenter|aroundCenter"}
filter.filterGallery	Filter Gallery…	{"effects":json,"foreground":json,"background":json,"list":bool}
filter.gallery.accentedEdges	Accented Edges	{"edgeWidth":1..14=2,"edgeBrightness":0..50=38,"smoothness":1..15=5}
filter.gallery.angledStrokes	Angled Strokes	{"directionBalance":0..100=50,"strokeLength":3..50=15,"sharpness":0..10=3}
filter.gallery.basRelief	Bas Relief	{"detail":1..15=13,"smoothness":1..15=3,"light":"bottom|bottomLeft|left|topLeft|top|topRight|right|bottomRight","foreground":json,"background":json}
filter.gallery.chalkCharcoal	Chalk & Charcoal	{"charcoalArea":0..20=6,"chalkArea":0..20=6,"strokePressure":0..5=1,"foreground":json,"background":json}
filter.gallery.charcoal	Charcoal	{"charcoalThickness":1..7=1,"detail":0..5=5,"lightDarkBalance":0..100=50,"foreground":json,"background":json}
filter.gallery.chrome	Chrome	{"detail":0..10=4,"smoothness":0..10=7}
filter.gallery.coloredPencil	Colored Pencil	{"pencilWidth":1..24=4,"strokePressure":0..15=8,"paperBrightness":0..50=25}
filter.gallery.conteCrayon	Conté Crayon	{"foregroundLevel":1..15=11,"backgroundLevel":1..15=7,"texture":"canvas|brick|burlap|sandstone","scaling":50..200=100,"relief":0..50=4,"light":"top|topRight|right|bottomRight|bottom|bottomLeft|left|topLeft","invert":bool,"foreground":json,"background":json}
filter.gallery.craquelure	Craquelure	{"crackSpacing":2..100=15,"crackDepth":0..10=6,"crackBrightness":0..10=9}
filter.gallery.crosshatch	Crosshatch	{"strokeLength":3..50=9,"sharpness":0..20=6,"strength":1..3=1}
filter.gallery.cutout	Cutout	{"numberOfLevels":2..8=4,"edgeSimplicity":0..10=4,"edgeFidelity":1..3=2}
filter.gallery.darkStrokes	Dark Strokes	{"balance":0..10=5,"blackIntensity":0..10=6,"whiteIntensity":0..10=2}
filter.gallery.diffuseGlow	Diffuse Glow	{"graininess":0..10=6,"glowAmount":0..20=10,"clearAmount":0..20=15,"background":json}
filter.gallery.dryBrush	Dry Brush	{"brushSize":0..10=2,"brushDetail":0..10=8,"texture":1..3=1}
filter.gallery.filmGrain	Film Grain	{"grain":0..20=4,"highlightArea":0..20=0,"intensity":0..10=10}
filter.gallery.fresco	Fresco	{"brushSize":0..10=2,"brushDetail":0..10=8,"texture":1..3=1}
filter.gallery.glass	Glass	{"distortion":0..20=5,"smoothness":1..15=3,"texture":"frosted|blocks|canvas|tinyLens","scaling":50..200=100,"invert":bool}
filter.gallery.glowingEdges	Glowing Edges	{"edgeWidth":1..14=2,"edgeBrightness":0..20=6,"smoothness":1..15=5}
filter.gallery.grain	Grain	{"intensity":0..100=40,"contrast":0..100=50,"grainType":"regular|soft|sprinkles|clumped|contrasty|enlarged|stippled|horizontal|vertical|speckle","foreground":json,"background":json}
filter.gallery.graphicPen	Graphic Pen	{"strokeLength":1..15=15,"lightDarkBalance":0..100=50,"strokeDirection":"rightDiagonal|horizontal|leftDiagonal|vertical","foreground":json,"background":json}
filter.gallery.halftonePattern	Halftone Pattern	{"size":1..12=1,"contrast":0..50=5,"patternType":"dot|circle|line","foreground":json,"background":json}
filter.gallery.inkOutlines	Ink Outlines	{"strokeLength":1..50=4,"darkIntensity":0..50=20,"lightIntensity":0..50=10}
filter.gallery.mosaicTiles	Mosaic Tiles	{"tileSize":2..100=12,"groutWidth":1..15=3,"lightenGrout":0..10=9}
filter.gallery.neonGlow	Neon Glow	{"glowSize":-24..24=5,"glowBrightness":0..50=15,"glowColor":json}
filter.gallery.notePaper	Note Paper	{"imageBalance":0..50=25,"graininess":0..20=10,"relief":0..25=11,"foreground":json,"background":json}
filter.gallery.oceanRipple	Ocean Ripple	{"rippleSize":1..15=9,"rippleMagnitude":0..20=9}
filter.gallery.paintDaubs	Paint Daubs	{"brushSize":1..50=8,"sharpness":0..40=7,"brushType":"simple|lightRough|darkRough|wideSharp|wideBlurry|sparkle"}
filter.gallery.paletteKnife	Palette Knife	{"strokeSize":1..50=25,"strokeDetail":1..3=3,"softness":0..10=0}
filter.gallery.patchwork	Patchwork	{"squareSize":0..10=4,"relief":0..25=8}
filter.gallery.photocopy	Photocopy	{"detail":1..24=7,"darkness":1..50=8,"foreground":json,"background":json}
filter.gallery.plaster	Plaster	{"imageBalance":0..50=20,"smoothness":1..15=2,"light":"top|topRight|right|bottomRight|bottom|bottomLeft|left|topLeft","foreground":json,"background":json}
filter.gallery.plasticWrap	Plastic Wrap	{"highlightStrength":0..20=15,"detail":1..15=9,"smoothness":1..15=7}
filter.gallery.posterEdges	Poster Edges	{"edgeThickness":0..10=2,"edgeIntensity":0..10=1,"posterization":0..6=2}
filter.gallery.reticulation	Reticulation	{"density":0..50=12,"foregroundLevel":0..50=40,"backgroundLevel":0..50=5,"foreground":json,"background":json}
filter.gallery.roughPastels	Rough Pastels	{"strokeLength":0..40=6,"strokeDetail":1..20=4,"texture":"canvas|brick|burlap|sandstone","scaling":50..200=100,"relief":0..50=20,"light":"bottom|bottomLeft|left|topLeft|top|topRight|right|bottomRight","invert":bool}
filter.gallery.smudgeStick	Smudge Stick	{"strokeLength":0..10=2,"highlightArea":0..20=0,"intensity":0..10=10}
filter.gallery.spatter	Spatter	{"sprayRadius":0..25=10,"smoothness":1..15=5}
filter.gallery.sponge	Sponge	{"brushSize":0..10=2,"definition":0..25=12,"smoothness":1..15=5}
filter.gallery.sprayedStrokes	Sprayed Strokes	{"strokeLength":0..20=12,"sprayRadius":0..25=7,"strokeDirection":"rightDiagonal|horizontal|leftDiagonal|vertical"}
filter.gallery.stainedGlass	Stained Glass	{"cellSize":2..50=10,"borderThickness":1..20=4,"lightIntensity":0..10=3,"foreground":json}
filter.gallery.stamp	Stamp	{"lightDarkBalance":0..50=25,"smoothness":1..50=5,"foreground":json,"background":json}
filter.gallery.sumiE	Sumi-e	{"strokeWidth":3..15=10,"strokePressure":0..15=2,"contrast":0..40=16}
filter.gallery.texturizer	Texturizer	{"texture":"canvas|brick|burlap|sandstone","scaling":50..200=100,"relief":0..50=4,"light":"top|topRight|right|bottomRight|bottom|bottomLeft|left|topLeft","invert":bool}
filter.gallery.tornEdges	Torn Edges	{"imageBalance":0..50=25,"smoothness":1..15=11,"contrast":1..25=17,"foreground":json,"background":json}
filter.gallery.underpainting	Underpainting	{"brushSize":0..40=6,"textureCoverage":0..40=16,"texture":"canvas|brick|burlap|sandstone","scaling":50..200=100,"relief":0..50=4,"light":"top|topRight|right|bottomRight|bottom|bottomLeft|left|topLeft","invert":bool}
filter.gallery.watercolor	Watercolor	{"brushDetail":1..14=9,"shadowIntensity":0..10=1,"texture":1..3=1}
filter.gallery.waterPaper	Water Paper	{"fiberLength":3..50=15,"brightness":0..100=60,"contrast":0..100=80}
filter.lastFilter	Last Filter	{}
filter.lensCorrection	Lens Correction…	{"profile":"none|auto|generic","focalLength":mm=0,"correctDistortion":bool=true,"correctVignette":bool=true,"correctCA":bool=true,"autoScale":bool=false,"distortion":-100..100=0,"redCyan":-100..100=0,"blueYellow":-100..100=0,"vignetteAmount":-100..100=0,"vignetteMidpoint":0..100=50,"vertical":-100..100=0,"horizontal":-100..100=0,"angle":-180..180=0,"scale":50..150=100,"edge":"transparency|edgeExtension|black|white","straighten":[[x,y],[x,y]]?}
filter.liquify	Liquify…	{"strokes":[{"tool":"forwardWarp|reconstruct|smooth|twirlCw|twirlCcw|pucker|bloat|pushLeft|freeze|thaw|lassoMask|reconstructAll","size":px=100,"density":0-100=50,"pressure":0-100=100,"rate":0-100=80,"points":[[x,y,pressure?,ms?]…] (ms: milliseconds since the previous point; a point with it follows the pointer exactly and times the stationary tools in real time, as the dialog records them),"amount":%? (twirlCcw: twirlCw reversed, what an Alt-drag with Twirl Clockwise records; reconstructAll; lassoMask: 1 freezes the polygon in points, 0 thaws it)}…],"meshSize":px? (field resolution, px per node; default 2, or 4 above 4 MP),"layer":id?} — strokes replay in order on a fresh field; a selection limits the effect; on a smart object it becomes a smart filter
filter.noise.addNoise	Add Noise…	{"amount":0.1..400=12.5,"distribution":"uniform|gaussian","monochromatic":bool,"seed":u32=0}
filter.noise.despeckle	Despeckle	{}
filter.noise.dustAndScratches	Dust & Scratches…	{"radius":1..500=1,"threshold":0..255=0}
filter.noise.median	Median…	{"radius":1..500=1}
filter.noise.reduceNoise	Reduce Noise…	{"strength":0..10=6,"preserveDetails":0..100=60,"reduceColorNoise":0..100=45,"sharpenDetails":0..100=25,"removeJpegArtifact":bool}
filter.other.colorToAlpha	Color to Alpha…	{"color":color=#ffffff,"transparencyThreshold":0..1=0,"opacityThreshold":0..1=1}
filter.other.custom	Custom…	{"kernel":int[25],"scale":1..9999=1,"offset":-9999..9999=0}
filter.other.highPass	High Pass…	{"radius":0.1..1000=10}
filter.other.hsbHsl	HSB/HSL	{"inputMode":"rgb|hsb|hsl","rowOrder":"hsb|hsl|rgb"}
filter.other.maximum	Maximum…	{"radius":0.2..500=1,"preserve":"squareness|roundness"}
filter.other.minimum	Minimum…	{"radius":0.2..500=1,"preserve":"squareness|roundness"}
filter.other.offset	Offset…	{"horizontal":px=0,"vertical":px=0,"undefinedAreas":"wrap|repeat|transparent"}
filter.pixelate.colorHalftone	Color Halftone…	{"maxRadius":4..127=8,"channel1":-360..360=108,"channel2":-360..360=162,"channel3":-360..360=90,"channel4":-360..360=45}
filter.pixelate.crystallize	Crystallize…	{"cellSize":3..300=10,"seed":u32=0}
filter.pixelate.facet	Facet	{}
filter.pixelate.fragment	Fragment	{}
filter.pixelate.mezzotint	Mezzotint…	{"type":"fineDots|mediumDots|grainyDots|coarseDots|shortLines|mediumLines|longLines|shortStrokes|mediumStrokes|longStrokes","seed":u32=0}
filter.pixelate.mosaic	Mosaic…	{"cellSize":2..200=10}
filter.pixelate.pointillize	Pointillize…	{"cellSize":3..300=5,"seed":u32=0,"background":json}
filter.render.clouds	Clouds	{"seed":u32=0,"foreground":json,"background":json}
filter.render.differenceClouds	Difference Clouds	{"seed":u32=0,"foreground":json,"background":json}
filter.render.fibers	Fibers…	{"variance":1..64=16,"strength":1..64=4,"seed":u32=0,"foreground":json,"background":json}
filter.render.flame	Flame…	{"flameType":"oneFlameAlongPath|multipleFlamesAlongPath|multipleFlamesPathDirections|multipleFlamesVariousLength|candleLight|multipleFlamesOneDirection","length":1..1000=150,"randomizeLength":bool,"width":1..1000=40,"angle":-180..180=0,"interval":1..1000=60,"adjustIntervalForLoops":bool=true,"useCustomColor":bool,"color":color,"turbulent":0..100=25,"jag":0..100=25,"opacity":0..100=75,"flameLines":1..100=20,"flameBottomAlignment":0..100=20,"flameStyle":"normal|violent|flat","flameShape":"parallel|toCenter|spread|oval|pointed","randomizeShapes":bool,"seed":u32=0,"quality":"draft|low|medium|high|fine","path":text,"newLayer":bool} → {layer,newLayer,bounds,primitives,usedPath}
filter.render.lensFlare	Lens Flare…	{"brightness":10..300=100,"centerX":0..1=0.5,"centerY":0..1=0.5,"lens":"zoom|prime35|prime105|moviePrime"} (normalized centre: 0..1 is the canvas; agents and actions may pass values outside it, which place the flare off the canvas unclamped)
filter.render.lightingEffects	Lighting Effects…	{"lightType":"spot|point|infinite","intensity":-100..100=75,"lightX":0..1=0.25,"lightY":0..1=0.2,"lightZ":0..2=0.6,"targetX":0..1=0.5,"targetY":0..1=0.55,"cone":1..89=45,"hotspot":0..100=50,"angle":-180..180=135,"elevation":0..90=45,"gloss":-100..100=0,"metallic":-100..100=0,"exposure":-100..100=0,"ambience":-100..100=8,"texture":"none|red|green|blue|alpha|luminance","height":0..100=50,"whiteIsHigh":bool=true,"lights":json}
filter.render.pictureFrame	Picture Frame…	{"frame":"vineWithFlowers|vineWithLeaves|ivy|roses|daisies|berries|bamboo|waves|zigzag|dots|rope|scallops|doubleLine|snowflakes|stars|hearts","margin":0..30=4,"size":1..100=50,"arrangement":1..100=50,"lines":1..5=1,"thickness":1..100=30,"fade":0..100=0,"vineColor":color,"flowerColor":color,"leafColor":color,"seed":u32=0,"newLayer":bool} → {layer,newLayer,bounds,primitives,frame}
filter.render.relight	Relight…	{"angle":-180..180=45,"elevation":0..90=40,"intensity":0..100=40,"ambient":0..100=55,"warmth":-100..100=0,"softness":1..100=25}
filter.render.tree	Tree…	{"baseTreeType":1..34=1,"lightDirection":1..5=3,"leavesAmount":0..100=50,"leavesSize":0..200=100,"branchesHeight":50..300=100,"branchesThickness":50..200=100,"defaultLeaves":bool=true,"leavesColor":color,"customBranchColor":bool,"branchesColor":color,"flatShading":bool,"seed":u32=0,"x":0..1=0.5,"y":0..1=0.95,"size":0.05..2=0.8,"newLayer":bool} → {layer,newLayer,bounds,primitives,treeType}
filter.sharpen.sharpen	Sharpen	{}
filter.sharpen.sharpenEdges	Sharpen Edges	{}
filter.sharpen.sharpenMore	Sharpen More	{}
filter.sharpen.smartSharpen	Smart Sharpen…	{"amount":1..500=100,"radius":0.1..64=1,"reduceNoise":0..100=10}
filter.sharpen.unsharpMask	Unsharp Mask…	{"amount":1..500=50,"radius":0.1..1000=1,"threshold":0..255=0}
filter.stylize.diffuse	Diffuse…	{"mode":"normal|darkenOnly|lightenOnly|anisotropic","seed":u32=0}
filter.stylize.emboss	Emboss…	{"angle":-180..180=135,"height":1..100=3,"amount":1..500=100}
filter.stylize.extrude	Extrude…	{"type":"blocks|pyramids","size":2..255=30,"depth":1..255=30,"depthMode":"random|levelBased","solidFrontFaces":bool,"maskIncompleteBlocks":bool,"seed":u32=0}
filter.stylize.findEdges	Find Edges	{}
filter.stylize.oilPaint	Oil Paint…	{"stylization":0.1..10=4,"cleanliness":0..10=5,"scale":0.1..10=1,"bristleDetail":0..10=5,"lighting":bool=true,"angle":-180..180=-60,"shine":0..10=1}
filter.stylize.solarize	Solarize	{}
filter.stylize.tiles	Tiles…	{"count":1..99=10,"maxOffset":1..99=10,"fill":"background|foreground|inverse|unaltered","seed":u32=0,"foreground":json,"background":json}
filter.stylize.traceContour	Trace Contour…	{"level":0..255=128,"edge":"lower|upper"}
filter.stylize.wind	Wind…	{"method":"wind|blast|stagger","direction":"fromRight|fromLeft","seed":u32=0}
filter.vanishingPoint	Vanishing Point…	{"planes":[{"corners":[[x,y]×4]} | {"from":plane,"edge":"top|right|bottom|left","angle":deg=90,"depth":1}],"focalLength":px=0,"paste":[{"plane":0,"layer":id? (else the clipboard),"at":[u,v]=[0.25,0.25],"width":0..1=0.5}],"clone":[{"source":[x,y],"points":[[x,y]],"size":px=40,"hardness":0..100=50,"opacity":0..100=100}],"newLayer":bool=false,"layer":id|name? (else the active layer)}
filter.video.deInterlace	De-Interlace…	{"eliminate":"oddFields|evenFields","createBy":"interpolation|duplication"}
filter.video.ntscColors	NTSC Colors	{}
```

## gradient（12）

```text
gradient.fill.create	Gradient (Live)	{"from":[x,y],"to":[x,y],"style":"linear|radial|angle|reflected|diamond"="linear","gradient":preset name?,"stops":[[t,"#rrggbb"|"foreground"|"background"],…]?,"transparency":[[t,0..100],…]? (default: the current gradient),"reverse":bool=false,"dither":bool=true,"opacity":0..100=100,"mode":"normal|multiply|…"="normal"} → {"layer":id}; a Gradient Fill layer above the active layer, masked by the selection
gradient.fill.get	Gradient Fill Settings	{"layer":id?} → {"style","angle","scale":%,"offset":[%,%],"reverse","dither","align","from":[x,y],"to":[x,y],"stops":[[t,"#hex"]],"transparency":[[t,%]],"midpoints":[…]}
gradient.fill.set	Edit Gradient Fill	{"layer":id?,"from":[x,y]?,"to":[x,y]?,"style":"linear|radial|angle|reflected|diamond"?,"angle":deg?,"scale":%?,"offset":[x%,y%]?,"reverse":bool?,"dither":bool?,"align":bool?,"stops":[[t,"#rrggbb"|"#rrggbbaa"|[r,g,b,a]|"foreground"|"background"],…]?,"transparency":[[t,0..100],…]?,"midpoints":[0.05..0.95 per segment]?} → the gradient (see gradient.fill.get)
gradient.fill.stop	Edit Gradient Stop	{"layer":id?,"action":"add|move|delete|color|opacity|midpoint","kind":"color|opacity"="color","index":stop (midpoint: segment) number,"location":0..1 (midpoint: of the segment),"color":"#rrggbb"|[r,g,b,a]|"foreground"|"background" (add: default the colour there),"opacity":0..100} → the gradient
gradient.presets.apply	New Gradient Fill Layer from Preset	{"preset":name?=current|"stops":[[t 0..1,"#rrggbb"|"foreground"|"background"],…],"transparency":[[t,opacity 0..100],…]?,"angle":deg=90,"style":"linear|radial|angle|reflected|diamond"="linear","scale":1..1000=100,"reverse":bool} → {layer}
gradient.presets.edit	Edit Gradient Presets	{"action":"rename|delete|move|newGroup|renameGroup|deleteGroup","preset":name|[names] (rename/delete/move),"group":name? (narrows the lookup; the group for renameGroup/deleteGroup),"name":str (rename: new name; newGroup/renameGroup: group name),"to":group (move),"index":n? (move)}
gradient.presets.importGrd	Import Gradients…	{"path":".grd file"?,"data":base64 bytes?,"group":string?=file name,"replace":bool=false (first delete a group of the same name; false imports beside it as <group> (2))} → {group, imported, count, warnings}
gradient.presets.list	Gradient Presets	{} → {groups:[{name,presets:[{name,stops,transparency}]}],current}
gradient.presets.new	New Gradient Preset	{"name":str="Custom","group":name?=first,"stops":[[t 0..1,"#rrggbb"|"foreground"|"background"],…],"transparency":[[t,opacity 0..100],…]? (default: the current gradient)}
gradient.presets.reset	Restore Default Gradients	{"append":bool=false}
gradient.presets.select	Select Gradient	{"preset":name|"stops":[[t 0..1,"#rrggbb"|"foreground"|"background"],…],"transparency":[[t,opacity 0..100],…]?,"group":name?,"applyToLayer":bool=true (also recolours a selected Gradient Fill layer, or fills a selected shape layer with it)} → {current,layer?}. The Gradient tool paints with it.
gradient.presets.stop	Edit Gradient Stop	{"action":"add|move|delete|color|opacity","kind":"color|opacity"="color","index":stop number,"location":0..1,"color":"#rrggbb"|"foreground"|"background" (add: default the colour there),"opacity":0..100} → {"current"}. Edits the Gradient tool's current gradient (no layer, midpoints stay centred).
```

## help（1）

```text
help.checkForUpdates	Check for Updates…	{}
```

## history（14）

```text
history.clear	Clear History	{} → {states,current,label}: removes every History state but the current one without changing the image; Edit › Undo restores them
history.deleteSnapshot	Delete Snapshot	{"snapshot":id} → {snapshot,snapshots}: the document and its history are unchanged
history.deleteState	Delete State	{"state":index?} (History entry, 0 = oldest; default the current state) → {states,current}: removes the state and every later one (with Allow Non-Linear History only that state, a later dimmed one too)
history.newDocument	New Document from State	{"state":index?,"name":str?} (History entry, 0 = oldest; default the current state) → {document,name}
history.newSnapshot	New Snapshot	{"name":str?="Snapshot N","from":"fullDocument"|"mergedLayers"|"currentLayer"="fullDocument","replaceExisting":bool=false (drop snapshots of the same name first)} → {snapshot,name}: a named copy of the document for the session (not a history state)
history.options	History Options…	{"automaticallyCreateFirstSnapshot":bool?,"automaticallyCreateNewSnapshotWhenSaving":bool?,"allowNonLinearHistory":bool?,"showNewSnapshotDialogByDefault":bool?,"makeLayerVisibilityChangesUndoable":bool?} → all five values (no params: report them). Automatically Create First Snapshot: a new or opened document starts with a snapshot of itself, named after it (default on). Automatically Create New Snapshot When Saving: each save of the document (not a copy) adds a snapshot named with the time of the save (default off). Allow Non-Linear History: an edit after stepping back keeps the later states and is appended at the end; deleting a state deletes only it (default off). Show New Snapshot Dialog by Default: a click on the History panel's camera button opens New Snapshot, not only ⌥-click (default off). Make Layer Visibility Changes Undoable: showing or hiding a layer is a history state (default on). Also `prefs.set historyOptions.*`
history.redo	Redo	{} (the same action as `edit.redo`)
history.renameSnapshot	Rename Snapshot	{"snapshot":id,"name":str} → {snapshot,name}
history.selectSnapshot	Select Snapshot	{"snapshot":id} → {snapshot,name}: the document returns to the snapshot as a new history state named after it
history.selectState	Select History State	{"state":index} (History entry as the panel lists them: 0 = oldest, then the current state, then the redo states) → {state,changed,current?}: returns the document to that state in one step; the states after it stay redoable
history.setSource	Set History Brush Source	{"state":row} | {"snapshot":id} (state: a History panel row, 0 = oldest state, then the current one, then the greyed redo states; snapshot: a history.newSnapshot id) → {state,label} | {snapshot,name}: paint.historyBrush and Fill › History use this source when neither `state` nor `snapshot` is passed
history.stepBackward	Step Backward	{} → {states,current,label}: makes the previous History state current (Err when there is none)
history.stepForward	Step Forward	{} → {states,current,label}: makes the next History state current (Err when there is none)
history.undo	Undo	{} (the same action as `edit.undo`)
```

## image（66）

```text
image.adjustments.blackWhite	Black & White…	{"reds":-200..300=40,"yellows":-200..300=60,"greens":-200..300=40,"cyans":-200..300=60,"blues":-200..300=20,"magentas":-200..300=80,"tint":bool=false,"tintColor":"#rrggbb"}
image.adjustments.brightnessContrast	Brightness/Contrast…	{"brightness":-150..150=0,"contrast":-50..100=0,"legacy":bool=false}
image.adjustments.channelMixer	Channel Mixer…	{"red":json,"green":json,"blue":json,"gray":json,"monochrome":bool=false} (per output channel [red %, green %, blue %, constant %] in -200..200; gray = the monochrome mix)
image.adjustments.colorBalance	Color Balance…	{"shadows":json,"midtones":json,"highlights":json,"preserveLuminosity":bool=true} (each tone [cyan-red, magenta-green, yellow-blue] in -100..100)
image.adjustments.colorLookup	Color Lookup…	{"lut":"none|warm|cool|tealOrange|bleachBypass|fadedFilm|dayForNight|monoContrast|crossProcess"="none","file":text,"interpolation":"trilinear|tetrahedral"="trilinear","dither":bool=false,"data":text,"dataEncoding":"text|base64"="text","fileName":text,"lutFormat":"auto|cube|3dl|look"="auto"} (file: LUT path; data: file text or encoded bytes; lutFormat overrides format detection, auto detects it)
image.adjustments.colorLookup.list	List Color Lookup Looks	{}
image.adjustments.curves	Curves…	{"points":json,"red":json,"green":json,"blue":json,"pencil":bool=false,"smooth":0..10=0,"eyedropper":json} (curves as [[in,out],…] in 0..255, 2..19 points: points = composite; red/green/blue, gray, cyan/magenta/yellow/black or lightness/a/b per channel; pencil = drawn curves (Draw to modify the curve): each curve is 256 output levels in 0..255 (point curves given are drawn in, and turning pencil off fits points to the drawing); smooth = Smooth passes over the drawn curves; eyedropper = the dialog's Set Black/Neutral Gray/White Point picker {"point":"black|gray|white","at":[x,y],"size":1..101=1} or {"point",…,"color":[r,g,b] 0..1}, colour composites: RGB and Grayscale (no gray); Image adjustments targeting a mask, alpha or Quick Mask sample that gray plane in any document mode, applied over the given curves)
image.adjustments.desaturate	Desaturate	{"target":"pixels"|"mask"|{"color":i}|{"colors":[i,…]}?=Channels panel target,"layer":id|name?=active}
image.adjustments.equalize	Equalize	{"selectedAreaOnly":bool=true (with a selection, false equalizes the layer within the canvas by the selection's histogram)}
image.adjustments.exposure	Exposure…	{"exposure":-20..20=0,"offset":-0.5..0.5=0,"gamma":0.01..9.99=1}
image.adjustments.gradientMap	Gradient Map…	{"stops":json,"reverse":bool=false,"dither":bool=false} (stops [[location 0..1, "#rrggbb"], …], 2..64)
image.adjustments.hdrToning	HDR Toning…	{"radius":1..500=30,"strength":0.1..4=0.5,"gamma":0.1..2=1,"exposure":-5..5=0,"detail":-100..300=30,"shadow":-100..100=0,"highlight":-100..100=0,"vibrance":-100..100=0,"saturation":-100..100=20,"curve":[[in,out],…] 0..255} (flattens the image)
image.adjustments.hueSaturation	Hue/Saturation…	{"hue":-180..180=0,"saturation":-100..100=0,"lightness":-100..100=0,"colorize":bool=false,"reds":json,"yellows":json,"greens":json,"cyans":json,"blues":json,"magentas":json} (per range {"hue","saturation","lightness","range":[4 hue degrees]}; colorize: hue 0..360, saturation 0..100)
image.adjustments.invert	Invert	{}
image.adjustments.levels	Levels…	{"inBlack":0..253=0,"gamma":0.01..9.99=1,"inWhite":2..255=255,"outBlack":0..255=0,"outWhite":0..255=255,"red":json,"green":json,"blue":json,"eyedropper":json} (top level = composite; per channel {"inBlack","gamma","inWhite","outBlack","outWhite"} under red/green/blue, gray, cyan/magenta/yellow/black or lightness/a/b; eyedropper = the dialog's Set Black/Neutral Gray/White Point picker {"point":"black|gray|white","at":[x,y],"size":1..101=1} or {"point",…,"color":[r,g,b] 0..1}: black/white set each channel's input black/white to the sample, gray each channel's gamma so the sample turns neutral at its luma; colour composites: RGB and Grayscale (no gray); Image adjustments targeting a mask, alpha or Quick Mask sample that gray plane in any document mode, applied over the given levels)
image.adjustments.matchColor	Match Color…	{"source":doc,"sourceLayer":json,"luminance":1..200=100,"intensity":1..200=100,"fade":0..100=0,"neutralize":bool=false,"useSelectionInSource":bool=false,"useSelectionInTarget":bool=false} (source: document index; sourceLayer: layer id, default the merged image)
image.adjustments.photoFilter	Photo Filter…	{"filter":"warming85|warmingLBA|warming81|cooling80|coolingLBB|cooling82|red|orange|yellow|green|cyan|blue|violet|magenta|sepia|deepRed|deepBlue|deepEmerald|deepYellow|underwater","color":"#rrggbb","density":0..100=25,"preserveLuminosity":bool=true}
image.adjustments.posterize	Posterize…	{"levels":2..255=4}
image.adjustments.replaceColor	Replace Color…	{"localized":bool=false,"color":color,"fuzziness":0..200=40,"range":0..100=100,"hue":-180..180=0,"saturation":-100..100=0,"lightness":-100..100=0,"points":[[x,y],…]?,"subtractPoints":[[x,y],…]?,"order":["+"|"-",…]?,"labMinimum":[L,a,b]?,"labMaximum":[L,a,b]?} (Lab bounds: a finite ordered D50 box, mutually exclusive with color/points/subtractPoints/order/localized/range; composite pixel-layer target only. Otherwise color ("#rrggbb") defaults to the foreground; localized points use range % of the longer side; several "points" (Add to Sample) or any "subtractPoints" (Subtract from Sample) match as select.colorRange does for the same samples, "order" the click order.)
image.adjustments.selectiveColor	Selective Color…	{"method":"relative|absolute"="relative","colors":"reds|yellows|greens|cyans|blues|magentas|whites|neutrals|blacks"="reds","cyan":-100..100=0,"magenta":-100..100=0,"yellow":-100..100=0,"black":-100..100=0,"reds":json} (per-range [c,m,y,k] arrays: reds yellows greens cyans blues magentas whites neutrals blacks)
image.adjustments.shadowsHighlights	Shadows/Highlights…	{"shadowAmount":0..100=35,"shadowTone":0..100=50,"shadowRadius":0..2500=30,"highlightAmount":0..100=0,"highlightTone":0..100=50,"highlightRadius":0..2500=30,"color":-100..100=20,"midtone":-100..100=0,"blackClip":0..50=0.01,"whiteClip":0..50=0.01}
image.adjustments.threshold	Threshold…	{"level":1..255=128}
image.adjustments.vibrance	Vibrance…	{"vibrance":-100..100=0,"saturation":-100..100=0}
image.analysis.countTool	Count Tool	{} → count groups and markers (edit with count.*)
image.analysis.info	Analysis Info	{} → scale, ruler readout, count groups, note and log counts
image.analysis.placeScaleMarker	Place Scale Marker…	{"length":logical units=nice ≈ width/5,"font":str?,"fontSize":pt=12,"displayText":bool=true,"textPosition":"top|bottom"="bottom","color":"black|white"="black"}
image.analysis.recordMeasurements	Record Measurements	{"source":"auto|selection|ruler|count"="auto"} → appended Measurement Log rows (selection: summary + one row per feature)
image.analysis.rulerTool	Ruler Tool	{"start":[x,y],"end":[x,y],"protractor":[x,y]|null?,"clear":bool=false} (no params: read) → X/Y/W/H/angle/L1/L2
image.analysis.selectDataPoints	Select Data Points…	{"selection":[keys]|{key:bool}?,"ruler":[keys]|{key:bool}?,"count":[keys]|{key:bool}?,"reset":bool=false} (keys: label,dateTime,document,source,scale,scaleUnits,scaleFactor,count,area,perimeter,circularity,height,width,grayMin,grayMax,grayMean,grayMedian,integratedDensity,histogram,length,angle)
image.analysis.setMeasurementScale	Set Measurement Scale…	{"preset":"default|custom"="custom","pixelLength":px,"logicalLength":number,"units":str (e.g. "mm")} (no params: read the scale)
image.analysis.straightenLayer	Straighten Layer	{"crop":bool=(active layer is the Background)} (rotates so the ruler line is level; crop = rotate the canvas and crop to the image; off for the Background, two or more selected layers, a group, Lock All and Lock Position, and a hidden target layer answers "Could not straighten the layer because the target layer is hidden." with nothing changed (#12033))
image.applyDataSet	Apply Data Set…	{name|index} → {applied, index}: sets layer visibility/text/pixels from the data set (one history step)
image.applyImage	Apply Image…	{"source":{"document":index?,"layer":id|name|{"name":str}|{"background":true}|"merged"="merged","channel":"composite"|"red|…"|index|"selection"|"transparency"|"mask"="composite","invert":bool=false},"blending":"normal|multiply|screen|overlay|softLight|hardLight|colorDodge|colorBurn|darken|lighten|difference|exclusion|linearBurn|linearDodge|add|subtract|…"="multiply","opacity":0..100=100,"scale":1..2=1,"offset":-255..255=0,"preserveTransparency":bool=false,"mask":{"document","layer","channel","invert"}?,"sourceChannel|sourceDocument|sourceLayer|sourceInvert|maskChannel|…":flat form of source/mask?}
image.autoColor	Auto Color	{}
image.autoContrast	Auto Contrast	{}
image.autoTone	Auto Tone	{}
image.calculations	Calculations…	{"source1":{"document","layer","channel","invert"},"source2":{…},"blending":"multiply|…"="multiply","opacity":0..100=100,"scale":1..2=1,"offset":-255..255=0,"mask":{…}?,"result":"newChannel|newDocument|selection"="newChannel","name":str?} (source channel: {"targeted":true} for one targeted colour/alpha, {"name":text} for a literal alpha name, {"color":text} for a colour component; source layer: {"name":text} for a literal layer name)
image.canvasSize	Canvas Size…	{"width":number,"height":number,"units":"px|percent"="px" (percent uses each current side; absolute sizes only),"relative":bool=false,"anchor":"topLeft|top|topRight|left|center|right|bottomLeft|bottom|bottomRight"="center","extensionColor":"background|foreground|white|black|transparent|#rrggbb"="background"}
image.crop	Crop	{"x":px,"y":px,"width":px,"height":px,"angle":-3600..3600=0,"deleteCroppedPixels":bool=true,"contentAware":bool=false,"targetWidth":px,"targetHeight":px,"resolution":ppi,"resample":"bicubic|bilinear|nearest|lanczos|preserveDetails"="bicubic"} → {x,y,width,height,documentWidth,documentHeight,resolution} (x/y/width/height, all four or none: without them the selection's bounds are cropped to; targetWidth/targetHeight, both or neither: the cropped area is resampled to exactly that size, as Image Size, in the same undo step; resolution: the document's new ppi; deleteCroppedPixels false: the pixels past the frame are kept and, unless contentAware, the Background becomes a normal layer, "Layer 0", so an extension is transparent on every layer (with contentAware the Background stays); contentAware: the Crop tool's Fill › Content-Aware Fill uses surrounding pixels to fill areas uncovered by a rotated or extending crop. The fill targets the Background, or the active pixel layer if there is no Background. With Delete Cropped Pixels on, it also targets a separate active pixel layer if it is visible and unlocked.)
image.detectFaces	Detect Faces	{"minScore":0..1=0.5,"sampleAllLayers":bool=true} → {"faces":[{"score","rect":[x,y,w,h],"landmarks":{"rightEye","leftEye","nose","mouthRight","mouthLeft"}: [x,y] each},…]} (best first; "rightEye" is the one on the image's left)
image.duplicate	Duplicate…	{"name":str,"mergedOnly":bool=false}
image.imageRotation.180	180°	{}
image.imageRotation.90ccw	90° Counter Clockwise	{}
image.imageRotation.90cw	90° Clockwise	{}
image.imageRotation.flipCanvasHorizontal	Flip Canvas Horizontal	{}
image.imageRotation.flipCanvasVertical	Flip Canvas Vertical	{}
image.imageSize	Image Size…	{"width":number,"height":number,"units":"px|pt"="px" (points use the document's current resolution),"percent":%? (both sides; an explicit side wins),"resolution":ppi,"keepPrintSize":bool=false (with only a resolution: resample the pixels to keep the print size),"scaleStyles":bool=true (scale layer effects with the pixels),"resample":"automatic|preserveDetails|bicubicSmoother|bicubicSharper|bicubicAutomatic|bicubic|nearest|bilinear|lanczos|none"="bicubic"} → {width,height} (the document's size after the command; "none" changes the resolution only)
image.mode.bitmap	Bitmap…	{"resolution":1..30000=document,"method":"diffusion|threshold|pattern|halftone|customPattern"="diffusion","frequency":1..999=53,"angle":-180..180=45,"shape":"round|ellipse|line|square|diamond|cross"="round","pattern":id|name=Patterns panel selection} (resolution: Output in pixels/inch, resamples first; frequency/angle/shape: Halftone Screen, frequency in lines/inch; pattern: Custom Pattern; flattens)
image.mode.bits16	16 Bits/Channel	{}
image.mode.bits32	32 Bits/Channel	{}
image.mode.bits8	8 Bits/Channel	{}
image.mode.cmyk	CMYK Color	{"profile":"<builtin id>|working|/path/to/profile.icc"=working,"intent":"perceptual|relative|saturation|absolute"="relative","bpc":bool=true}
image.mode.colorTable	Color Table…	{"table":"custom|blackBody|grayscale|spectrum|systemMac|systemWindows|web"="custom","colors":json,"entries":json,"transparent":json} (colors: ["#rrggbb", …]; entries: {"index": "#rrggbb"}; transparent: index|null)
image.mode.duotone	Duotone…	{"type":"duotone|monotone|tritone|quadtone"="duotone","inks":json} (inks: [{"name","color":"#rrggbb","curve":[[in,out],…] in 0..100}, …])
image.mode.grayscale	Grayscale	{"profile":"<builtin id>|working|/path/to/profile.icc"=working,"intent":"perceptual|relative|saturation|absolute"="relative","bpc":bool=true}
image.mode.indexedColor	Indexed Color…	{"palette":"selective|perceptual|adaptive|exact|systemMac|systemWindows|web|uniform"="selective","colors":2..256=256,"forced":"blackWhite|none|primaries|web"="blackWhite","transparency":bool=true,"matte":color,"dither":"diffusion|none|pattern|noise"="diffusion","amount":0..100=75} (flattens; matte: none|foreground|background|white|black|gray|netscapeGray|#rrggbb; gray=50% Gray (#808080), netscapeGray=Netscape Gray (#c0c0c0))
image.mode.lab	Lab Color	{"profile":"<builtin id>|working|/path/to/profile.icc"=working,"intent":"perceptual|relative|saturation|absolute"="relative","bpc":bool=true}
image.mode.multichannel	Multichannel	{} (flattens; RGB → Cyan/Magenta/Yellow, CMYK → Cyan/Magenta/Yellow/Black, Lab → Alpha 1–3, Grayscale → Black, Duotone → its inks)
image.mode.rgb	RGB Color	{"profile":"<builtin id>|working|/path/to/profile.icc"=working (Indexed→RGB preserves the document profile unless explicit),"intent":"perceptual|relative|saturation|absolute"="relative","bpc":bool=true}
image.perspectiveCrop	Perspective Crop	{"corners":[[x,y],[x,y],[x,y],[x,y]] (top-left, top-right, bottom-right, bottom-left; a convex quad, document px),"width":px,"height":px,"resolution":ppi,"interpolation":"bicubic|bilinear|nearest"="bicubic"} → {width,height,resolution,corners} (the quad is mapped onto an upright width x height canvas, all layers, one undo step; no width/height: the rectangle the quad shows in perspective, one alone keeps its proportions; type, shape, fill and smart object layers are rasterized)
image.revealAll	Reveal All	{}
image.rotation.arbitrary	Arbitrary…	{"angle":-359.99..359.99=0,"direction":"cw|ccw"="cw","interpolation":"bicubic|bilinear|nearest"="bicubic"}
image.trap	Trap…	{width:px>=1=1} → {trapped,width}: spread inks at colour edges (CMYK only)
image.trim	Trim…	{"basedOn":"transparent|topLeft|bottomRight"="transparent","top":bool=true,"bottom":bool=true,"left":bool=true,"right":bool=true}
image.variables.dataSets	Data Sets…	{dataSets:[{name, values:[{variable, kind:visibility|text|pixels, value}]}], append?} → {defs,dataSets,active}
image.variables.define	Define…	{defs:[{name, layer:id, type:visibility|textReplacement|pixelReplacement, method?:fit|fill|asIs|conform, align?, clip?}]} → {defs,dataSets,active}
```

## jobs（2）

```text
jobs.cancel	Cancel Background Job	{"job":u64? (default: every running job)}
jobs.list	List Background Jobs	{}
```

## layer（233）

```text
layer.addAboveToSelection	Add Layer Above to Selection	{} (follows the Layers panel's rows; collapsed groups are one row)
layer.addBelowToSelection	Add Layer Below to Selection	{} (follows the Layers panel's rows; collapsed groups are one row)
layer.align.bottomEdges	Bottom Edges	{"to":"auto|layers|selection|canvas"="auto"} (auto: the active selection's bounds when there is one, however many layers are selected; else one layer aligns to the canvas and several to their combined bounds)
layer.align.horizontalCenters	Horizontal Centers	{"to":"auto|layers|selection|canvas"="auto"} (auto: the active selection's bounds when there is one, however many layers are selected; else one layer aligns to the canvas and several to their combined bounds)
layer.align.leftEdges	Left Edges	{"to":"auto|layers|selection|canvas"="auto"} (auto: the active selection's bounds when there is one, however many layers are selected; else one layer aligns to the canvas and several to their combined bounds)
layer.align.rightEdges	Right Edges	{"to":"auto|layers|selection|canvas"="auto"} (auto: the active selection's bounds when there is one, however many layers are selected; else one layer aligns to the canvas and several to their combined bounds)
layer.align.topEdges	Top Edges	{"to":"auto|layers|selection|canvas"="auto"} (auto: the active selection's bounds when there is one, however many layers are selected; else one layer aligns to the canvas and several to their combined bounds)
layer.align.verticalCenters	Vertical Centers	{"to":"auto|layers|selection|canvas"="auto"} (auto: the active selection's bounds when there is one, however many layers are selected; else one layer aligns to the canvas and several to their combined bounds)
layer.arrange.bringForward	Bring Forward	{"layer":id?}
layer.arrange.bringToFront	Bring to Front	{"layer":id?}
layer.arrange.reverse	Reverse	{}
layer.arrange.sendBackward	Send Backward	{"layer":id?}
layer.arrange.sendToBack	Send to Back	{"layer":id?}
layer.artboard.addBeside	Add Artboard Beside	{"layer":id? (default: the active artboard),"side":"left|right|top|bottom"="right","duplicate":bool=false (copy the board with its contents instead of an empty one)} → {layer, rect} (the Artboard tool's "+" buttons: same size, a 100 px gap away, past any board in the way)
layer.artboard.set	Edit Artboard	{"layer":id? (default: the active artboard),"x","y","width","height"?|"rect":[x,y,w,h]?,"preset":str?,"background":"white|black|transparent|custom"?,"color":…?,"name":str?,"moveContents":bool=true} → {layer, rect}
layer.combineShapes.excludeOverlappingShapes	Subtract Shapes at Overlap	{"layer":id?,"subpath":index? (default all but the first)} (no layer/subpath and two or more shape layers selected: merges them into the top-most, whose components above the bottom layer's take the operation)
layer.combineShapes.intersectShapeAreas	Unite Shapes at Overlap	{"layer":id?,"subpath":index? (default all but the first)} (no layer/subpath and two or more shape layers selected: merges them into the top-most, whose components above the bottom layer's take the operation)
layer.combineShapes.mergeShapeComponents	Merge Shape Components	{"layer":id?,"tolerance":px=0.1} (bakes the path operations into plain combined outlines, traced from the exact coverage; no layer and several shape layers selected: merges them into the top-most first)
layer.combineShapes.subtractFrontShape	Subtract Front Shape	{"layer":id?,"subpath":index? (default all but the first)} (no layer/subpath and two or more shape layers selected: merges them into the top-most, whose components above the bottom layer's take the operation)
layer.combineShapes.unite	Unite Shapes	{"layer":id?,"subpath":index? (default all but the first)} (no layer/subpath and two or more shape layers selected: merges them into the top-most, whose components above the bottom layer's take the operation)
layer.copyCSS	Copy CSS	{"layer":id?} (no layer: the selected layers) → {"css": text, "layers": [id…]}; the app puts the text on the clipboard
layer.copyToDocument	Copy Layers to Document	{"document":index (destination),"layers":[id,…]?=the source's selected layers,"source":index?=active,"selectionOnly":bool=false (copy selected pixels from one raster layer),"center":bool=false (centre on the destination's canvas),"at":[x,y]? (centre the copies on this point),"offset":[dx,dy]?=[0,0] (from their place in the source),"name":str? (one layer: the copy's name)}
layer.createClippingMask	Create Clipping Mask	{"layer":id?} (no layer: every selected layer but the lowest clips to the layer below it)
layer.delete	Delete Layer	{"layer":id?} (no layer: every selected layer)
layer.delete.hiddenLayers	Hidden Layers	{}
layer.distribute.bottomEdges	Bottom Edges	{}
layer.distribute.horizontalCenters	Horizontal Centers	{}
layer.distribute.horizontally	Horizontally	{} (equal horizontal gaps)
layer.distribute.leftEdges	Left Edges	{}
layer.distribute.rightEdges	Right Edges	{}
layer.distribute.topEdges	Top Edges	{}
layer.distribute.verticalCenters	Vertical Centers	{}
layer.distribute.vertically	Vertically	{} (equal vertical gaps)
layer.duplicate	Duplicate Layer…	{"layer":id?,"inPlace":bool=false (artboards: keep the copy on the original instead of beside it),"name":str? (one layer: the copy's name),"document":index|"new"=same document (Photoshop's Destination: "new" makes a new document the size of this canvas holding just the copies),"documentName":str? (the new document's name)} (no layer: every selected layer)
layer.exportAs	Export As…	{"layer":id?,"path":text,"scale":1..1000=100,"resample":"bicubicAutomatic|bicubic|bicubicSmoother|bicubicSharper|bilinear|nearest"="bicubicAutomatic"} (format from the path's extension; the document is not resampled)
layer.fill.pattern.set	Pattern Fill…	{"layer":id|name? (default active; a Pattern Fill layer),"document":id? (reject a stale dialog),"pattern":id|name?,"patternName":name? (then `pattern` is an id; the name is used when no pattern has that id),"scale":1..1000?,"angle":-180..180?,"link":bool?,"phase":[x,y]? (Snap to Origin: [0,0])}; omitted values keep the layer's
layer.fill.solidColor.set	Solid Color…	{"layer":id|name? (default active),"document":id? (reject a stale dialog),"color":"#rrggbb"|"#rrggbbaa"|[r,g,b,a?]|{mode,c:[f32;4],alpha:f32},"cmyk":[c,m,y,k]? (inks 0..1 the colour was picked as: a CMYK document keeps exactly these)}; RGB values without alpha preserve it; stored Color preserves its model and precision
layer.flattenImage	Flatten Image	{}
layer.frame.convert	Convert to Frame	{"layer":id?,"name":str?,"width":px?,"height":px?}
layer.frame.fit	Fit Frame / Content	{"layer":id?,"mode":"contentToFrame|frameToContent"="contentToFrame"}
layer.frame.info	Frame Info	{"layer":id?}
layer.frame.set	Frame Properties	{"layer":id?,"transform":[a,b,c,d,x,y]?,"stroke":object|null?,"name":str?}
layer.frame.setContent	Replace Frame Content	{"layer":id?,"content":id,"copy":bool=false}: a layer dragged into a frame keeps its original size
layer.groupLayers	Group Layers	{"layer":id?,"name":text?,"color":"none|red|orange|yellow|green|seafoam|blue|indigo|magenta|fuchsia|violet|gray"="none","mode":str="passThrough" (blend mode),"opacity":0..100=100 (percent)} (no layer: every selected layer; the new group starts collapsed)
layer.hideLayers	Hide Layers	{"layer":id?} (shows them instead when every targeted layer is already hidden, so ⌘, toggles)
layer.layerContentOptions	Layer Content Options…	{}
layer.layerMask.apply	Apply	{"layer":id?}
layer.layerMask.delete	Delete	{"layer":id?}
layer.layerMask.edit	Edit Layer Mask	{"layer":id? (default active),"document":id? (reject a stale dialog),"density":0..100?,"feather":0..1000? (pixels)} → {layer,density,feather}; at least one property required; mask pixels are preserved
layer.layerMask.enabled	Disable Layer Mask	{"layer":id?,"enabled":bool? (default: toggle)}
layer.layerMask.fromTransparency	From Transparency	{"layer":id?}
layer.layerMask.hideAll	Hide All	{"layer":id?} (no layer: every selected layer that can take a mask)
layer.layerMask.hideSelection	Hide Selection	{"layer":id?} (no layer: every selected layer that can take a mask)
layer.layerMask.linked	Unlink Layer Mask	{"layer":id?,"linked":bool? (default: toggle)}
layer.layerMask.moveTo	Move Layer Mask	{"layer":id? (the mask's layer, default active),"to":id|name (the layer or group it goes to; a recorded step names it),"toOccurrence":n? (which of several layers named `to`, in document order),"copy":bool=false (⌥-drag: a copy goes and the original stays),"replace":bool=false (replace a mask already there; otherwise refused)} → {layer,to,copy}
layer.layerMask.revealAll	Reveal All	{"layer":id?} (no layer: every selected layer that can take a mask)
layer.layerMask.revealSelection	Reveal Selection	{"layer":id?} (no layer: every selected layer that can take a mask)
layer.layerStyle.bevelEmboss	Bevel & Emboss…	{"style":"inner|outer|emboss|pillow|stroke","technique":"smooth|chiselHard|chiselSoft","contour":bool,"contourName":name|curve,"contourRange":1..100=50,"contourAntiAlias":bool,"glossContour":name|curve,"glossAntiAlias":bool,"texture":pattern id|name?,"textureScale":1..1000=100,"textureDepth":-1000..1000=100,"textureInvert":bool,"textureLink":bool=true,"depth":1..1000=100,"direction":"up|down","size":px=5,"soften":px,"angle":deg,"altitude":deg,"add":bool}
layer.layerStyle.blendingOptions	Blending Options…	{"layer":id?,"blend":"normal|multiply|…"?,"opacity":0..100?,"fillOpacity":0..100?,"blendIf":{"channel":"gray|red|green|blue|cyan|…"|index="gray","thisLayer":[black,white]|[blackLo,blackHi,whiteLo,whiteHi]?,"underlying":[…]?}|[{…},…]|null?,"channels":[bool,…]?,"knockout":"none|shallow|deep"?,"blendInteriorEffectsAsGroup":bool?,"blendClippedLayersAsGroup":bool?,"transparencyShapesLayer":bool?,"layerMaskHidesEffects":bool?,"vectorMaskHidesEffects":bool?} (Blend If values 0..255; split points fade; null resets. Advanced Blending: channels = which colour channels blend (R G B / C M Y K / L a b); PhotoCraft's defaults are knockout none, interior effects off, clipped layers as group on, transparency shapes on, masks hide effects off)
layer.layerStyle.clear	Clear Layer Style	{"layer":id? (no layer: every selected layer that has a style),"effect":index? (only that effect of "layer", as an effect row dropped on the Layers panel's Delete button)}
layer.layerStyle.colorOverlay	Color Overlay…	{"color":"#rrggbb","opacity":0..100=100,"blend":str,"add":bool}
layer.layerStyle.contours.delete	Delete Contour	{"name":str} → {deleted, count}
layer.layerStyle.contours.list	List User Contours	{} → {count, contours:[{name, contour: curve object usable as any `contour` param}]}
layer.layerStyle.contours.load	Load Contours…	{"path":".shc file"?,"data":base64 bytes?,"mode":"append"|"replace"="append"} → {loaded, count, skipped} (picker menu: Load Contours… / Replace Contours…)
layer.layerStyle.contours.new	New Contour…	{"contour":name|{"name":str,"points":[[in 0..1,out 0..1],…],"corners":[bool,…]},"name":str?="Contour N"} → {name (made unique, never a standard contour's name), contour, count} (Contour Editor › New…)
layer.layerStyle.contours.save	Save Contours…	{"path":".shc file"?,"names":[str]?=all} → {count, bytes, path | data (base64 when no path)}
layer.layerStyle.copyLayerStyle	Copy Layer Style	{"layer":id?}
layer.layerStyle.createLayer	Create Layer	{"layer":id?}
layer.layerStyle.defaultFor	Layer Style Default	{"kind":str} → {"params":{…},"user":bool} (the saved user default, else the factory defaults)
layer.layerStyle.dropShadow	Drop Shadow…	{"color":"#rrggbb","opacity":0..100=75,"blend":str="multiply","angle":deg=120,"useGlobalLight":bool,"distance":px=5,"spread":0..100,"size":px=5,"contour":"Linear|Cone|Cone - Inverted|Cove - Deep|Cove - Shallow|Gaussian|Half Round|Ring|Ring - Double|Rolling Slope - Descending|Rounded Steps|Sawtooth 1"|{"name":str,"points":[[in 0..1,out 0..1],…],"corners":[bool,…]}="Linear","antiAlias":bool,"noise":0..100,"knocksOut":bool,"add":bool,"layer":id}
layer.layerStyle.globalLight	Global Light…	{"angle":-180..180=120,"altitude":0..90=30}
layer.layerStyle.gradientOverlay	Gradient Overlay…	{"from":"#rrggbb","to":"#rrggbb","stops":[[0..1,"#rrggbb"],.]? (2..256 source stops),"opacityStops":[[0..1,0..100],.]?,"method":"classic|perceptual|linear|smooth"? (Photoshop's interpolation; omitted on new effects: straight stops; edits retain the recorded method),"smoothness":0..100=100,"style":"linear|radial|angle|reflected|diamond","angle":deg=90,"scale":10..150=100,"reverse":bool,"opacity":0..100,"blend":str,"add":bool}
layer.layerStyle.hideAllEffects	Hide All Effects	{}
layer.layerStyle.innerGlow	Inner Glow…	{"color":"#rrggbb","opacity":0..100=75,"blend":str="screen","technique":"softer|precise","source":"edge|center","choke":0..100,"size":px,"range":1..100=50,"contour":name|curve,"antiAlias":bool,"noise":0..100,"add":bool}
layer.layerStyle.innerShadow	Inner Shadow…	{"color":"#rrggbb","opacity":0..100=75,"blend":str,"angle":deg,"distance":px,"choke":0..100,"size":px,"contour":name|curve,"antiAlias":bool,"noise":0..100,"add":bool}
layer.layerStyle.makeDefault	Make Layer Style Default	{"kind":"stroke|dropShadow|innerShadow|outerGlow|innerGlow|colorOverlay|gradientOverlay|patternOverlay|satin|bevelEmboss","params":{…param set…}} (stores the user default the Layer Style dialog's Reset to Default restores)
layer.layerStyle.outerGlow	Outer Glow…	{"color":"#rrggbb","opacity":0..100=75,"blend":str="screen","technique":"softer|precise","spread":0..100,"size":px,"range":1..100=50,"contour":name|curve,"antiAlias":bool,"noise":0..100,"add":bool}
layer.layerStyle.pasteLayerStyle	Paste Layer Style	{"layer":id?,"allowGroups":bool=true} (no layer: every selected layer but the Background; false skips groups, refusing if none remain)
layer.layerStyle.patternOverlay	Pattern Overlay…	{"pattern":id|name?=first library pattern,"opacity":0..100=100,"blend":str,"scale":1..1000=100,"angle":deg=0,"link":bool=true,"phaseX":px,"phaseY":px,"add":bool}
layer.layerStyle.replace	Edit Layer Style	{"layer":id,"effects":[{"kind":"dropShadow|innerShadow|outerGlow|innerGlow|stroke|colorOverlay|gradientOverlay|patternOverlay|satin|bevelEmboss","params":{…layer.layerStyle.<kind> params…},"fx":<effect snapshot carried through the Layer Style dialog, optional>}]} (replaces the layer's whole effect list; an entry with `fx` edits that effect with the params present, one without builds from params)
layer.layerStyle.satin	Satin…	{"color":"#rrggbb","opacity":0..100=50,"blend":str,"angle":deg,"distance":px,"size":px,"contour":name|curve,"antiAlias":bool=true,"invert":bool,"add":bool}
layer.layerStyle.scaleEffects	Scale Effects…	{"scale":1..1000=100}
layer.layerStyle.showAllEffects	Show All Effects	{}
layer.layerStyle.stroke	Stroke…	{"size":px=1,"position":"inside|outside|center","color":"#rrggbb","from":"#rrggbb","to":"#rrggbb","method":"classic|perceptual|linear|smooth"?,"smoothness":0..100=100,"style":str,"angle":deg,"opacity":0..100,"blend":str,"overprint":bool,"add":bool}
layer.layerStyle.transferEffects	Move Layer Effects	{"from":id,"to":id,"effect":index? (default: all effects),"copy":bool=false}
layer.linkLayers	Link Layers	{"linked":bool?} (omitted: toggle; explicit true links, false unlinks)
layer.list	List Layers	{"document":index?,"flat":bool=false} → {"layers":[{"id","name","kind","visible","bounds":[x,y,w,h]|null,"selected","active","children"?}],"activeLayer":id?} (top-down; groups list their "children", or with "flat" every layer is one row with its "depth" and "parent" group id)
layer.lockLayers	Lock Layers…	{"transparency":bool?,"pixels":bool?,"position":bool?,"artboard":bool?,"all":bool?} (none given: toggle lock all)
layer.maskAllObjects	Mask All Objects	{"layer":id?}
layer.matting.colorDecontaminate	Color Decontaminate…	{"amount":0..100=100,"radius":1..100=4}
layer.matting.defringe	Defringe…	{"width":1..200=1}
layer.matting.removeBlackMatte	Remove Black Matte	{}
layer.matting.removeWhiteMatte	Remove White Matte	{}
layer.mergeDown	Merge Down	{"layer":id?}
layer.mergeGroup	Merge Group	{"layer":id?}
layer.mergeLayers	Merge Layers	{} (one layer selected: Merge Down)
layer.mergeVisible	Merge Visible	{}
layer.moveTo	Reorder Layer	{"layer":id|{"index":uint}|{"ordinal":"Trgt|Frwr|Bckw|Frnt|Back"}?| "layers":[id,…]?, "target":id|name|{"index":uint},"targetOccurrence":n? (which of several layers named `target`, in document order),"position":"above|below|into"="above","copy":bool=false} (typed target: pre-move recorded stack boundary, omit position; layers: one undoable move, document order preserved; copy: place duplicates there and leave the layers, as ⌥-dragging a Layers panel row; recorded typed references retain their form)
layer.new.artboard	Artboard…	{"rect":[x,y,w,h]? | "x","y","width","height"? (default: canvas size, right of the last board),"preset":"iPhone 14|Web 1920|A4|…"?,"name":str?,"background":"white|black|transparent|custom"="white","color":[r,g,b]|"#rrggbb"? (custom),"takeBackground":bool=false (the first board in the document also takes in the Background as a normal layer "Layer 0"; the Artboard tool's drag sets it)} → {layer, rect}
layer.new.artboardFromGroup	Artboard from Group…	{"layer":id? (a top-level group; default active),"background":…?,"color":[r,g,b]|"#rrggbb"?,"preset":str? (tag only; does not resize),"guideIDs":[int]? (ignored recording metadata),"changeBackground":int? (1 or absent applies background/color; other integers give white; legacy true = 1)} → {layer, rect}
layer.new.artboardFromLayers	Artboard from Layers…	{"name":text,"background":"white|black|transparent|custom"="white","color":color,"width":px=0,"height":px=0} (the selected layers; name: empty gives Artboard N; color: for custom; width, height: the board's size from the layers' top left, 0 keeps their bounds) → {layer, rect}
layer.new.backgroundFromLayer	Background From Layer	{"layer":id?} (the active layer by default; transparent pixels take the background colour and the layer drops to the bottom as the locked Background)
layer.new.frame	New Frame	{"x":i32,"y":i32,"width":u32,"height":u32,"shape":"rectangle|ellipse|triangle|polygon|custom"="rectangle","sides":3..100=5,"path":object?,"stroke":object|null?,"layer":id?,"name":str?} → {layer,frame:[x,y,w,h],shape}
layer.new.frameFromLayers	Frame from Layers	{name?:str}
layer.new.group	Group…	{"name":text?,"color":"none|red|orange|yellow|green|seafoam|blue|indigo|magenta|fuchsia|violet|gray"="none","mode":str="passThrough" (blend mode),"opacity":0..100=100 (percent),"position":"above|below"="above" (below: the Layers panel's Cmd/Ctrl-click; never under the Background)} (above the active layer, or inside it when it is an open group; clipped when it lands inside a clipping mask)
layer.new.groupFromLayers	Group from Layers…	{"layer":id?,"name":text?,"color":"none|red|orange|yellow|green|seafoam|blue|indigo|magenta|fuchsia|violet|gray"="none","mode":str="passThrough" (blend mode),"opacity":0..100=100 (percent)} (no layer: every selected layer; the new group starts collapsed)
layer.new.layer	Layer…	{"name":str?,"clipToPrevious":bool=false (Use Previous Layer to Create Clipping Mask; inside a clip group the layer joins it anyway),"color":"none|red|orange|yellow|green|seafoam|blue|indigo|magenta|fuchsia|violet|gray"="none","mode":"Normal|Multiply|…"="Normal","opacity":0..1=1,"fillNeutral":bool=false (fill with the mode's neutral color: modes without one are an error),"position":"above|below"="above" (below: the Layers panel's Cmd/Ctrl-click; never under the Background)} (above the active layer, or the top layer inside it when it is an open group)
layer.new.layerFromBackground	Layer From Background…	{"ifPresent":bool=false (true: a document without a Background is left as it is, as a Photoshop action's step needs on an image that opened as a normal layer),"select":bool=true (false: the targeted layer stays targeted)}
layer.new.layerViaCopy	Layer Via Copy	{}
layer.new.layerViaCut	Layer Via Cut	{}
layer.newAdjustmentLayer.blackWhite	Black & White…	{"reds":-200..300=40,"yellows":-200..300=60,"greens":-200..300=40,"cyans":-200..300=60,"blues":-200..300=20,"magentas":-200..300=80,"tint":bool=false,"tintColor":"#rrggbb"} + {"path":"work"|saved path name|{…path}? (the active path: becomes the vector mask; else the selection is the layer mask, or white with no selection),"opacity":0..1=1,"name":str?=the adjustment's name + number,"mode":blend mode name="normal" (not Pass Through),"clipToPrevious":bool=false}
layer.newAdjustmentLayer.brightnessContrast	Brightness/Contrast…	{"brightness":-150..150=0,"contrast":-50..100=0,"legacy":bool=false} + {"path":"work"|saved path name|{…path}? (the active path: becomes the vector mask; else the selection is the layer mask, or white with no selection),"opacity":0..1=1,"name":str?=the adjustment's name + number,"mode":blend mode name="normal" (not Pass Through),"clipToPrevious":bool=false}
layer.newAdjustmentLayer.channelMixer	Channel Mixer…	{"red":json,"green":json,"blue":json,"gray":json,"monochrome":bool=false} (per output channel [red %, green %, blue %, constant %] in -200..200; gray = the monochrome mix) + {"path":"work"|saved path name|{…path}? (the active path: becomes the vector mask; else the selection is the layer mask, or white with no selection),"opacity":0..1=1,"name":str?=the adjustment's name + number,"mode":blend mode name="normal" (not Pass Through),"clipToPrevious":bool=false}
layer.newAdjustmentLayer.colorBalance	Color Balance…	{"shadows":json,"midtones":json,"highlights":json,"preserveLuminosity":bool=true} (each tone [cyan-red, magenta-green, yellow-blue] in -100..100) + {"path":"work"|saved path name|{…path}? (the active path: becomes the vector mask; else the selection is the layer mask, or white with no selection),"opacity":0..1=1,"name":str?=the adjustment's name + number,"mode":blend mode name="normal" (not Pass Through),"clipToPrevious":bool=false}
layer.newAdjustmentLayer.colorLookup	Color Lookup…	{"lut":"none|warm|cool|tealOrange|bleachBypass|fadedFilm|dayForNight|monoContrast|crossProcess"="none","file":text,"interpolation":"trilinear|tetrahedral"="trilinear","dither":bool=false,"data":text,"dataEncoding":"text|base64"="text","fileName":text,"lutFormat":"auto|cube|3dl|look"="auto"} (file: LUT path; data: file text or encoded bytes; lutFormat overrides format detection, auto detects it) + {"path":"work"|saved path name|{…path}? (the active path: becomes the vector mask; else the selection is the layer mask, or white with no selection),"opacity":0..1=1,"name":str?=the adjustment's name + number,"mode":blend mode name="normal" (not Pass Through),"clipToPrevious":bool=false}
layer.newAdjustmentLayer.curves	Curves…	{"points":json,"red":json,"green":json,"blue":json,"pencil":bool=false,"smooth":0..10=0,"eyedropper":json} (curves as [[in,out],…] in 0..255, 2..19 points: points = composite; red/green/blue, gray, cyan/magenta/yellow/black or lightness/a/b per channel; pencil = drawn curves (Draw to modify the curve): each curve is 256 output levels in 0..255 (point curves given are drawn in, and turning pencil off fits points to the drawing); smooth = Smooth passes over the drawn curves; eyedropper = the dialog's Set Black/Neutral Gray/White Point picker {"point":"black|gray|white","at":[x,y],"size":1..101=1} or {"point",…,"color":[r,g,b] 0..1}, colour composites: RGB and Grayscale (no gray); Image adjustments targeting a mask, alpha or Quick Mask sample that gray plane in any document mode, applied over the given curves) + {"path":"work"|saved path name|{…path}? (the active path: becomes the vector mask; else the selection is the layer mask, or white with no selection),"opacity":0..1=1,"name":str?=the adjustment's name + number,"mode":blend mode name="normal" (not Pass Through),"clipToPrevious":bool=false}
layer.newAdjustmentLayer.exposure	Exposure…	{"exposure":-20..20=0,"offset":-0.5..0.5=0,"gamma":0.01..9.99=1} + {"path":"work"|saved path name|{…path}? (the active path: becomes the vector mask; else the selection is the layer mask, or white with no selection),"opacity":0..1=1,"name":str?=the adjustment's name + number,"mode":blend mode name="normal" (not Pass Through),"clipToPrevious":bool=false}
layer.newAdjustmentLayer.gradientMap	Gradient Map…	{"stops":json,"reverse":bool=false,"dither":bool=false} (stops [[location 0..1, "#rrggbb"], …], 2..64) + {"path":"work"|saved path name|{…path}? (the active path: becomes the vector mask; else the selection is the layer mask, or white with no selection),"opacity":0..1=1,"name":str?=the adjustment's name + number,"mode":blend mode name="normal" (not Pass Through),"clipToPrevious":bool=false}
layer.newAdjustmentLayer.hueSaturation	Hue/Saturation…	{"hue":-180..180=0,"saturation":-100..100=0,"lightness":-100..100=0,"colorize":bool=false,"reds":json,"yellows":json,"greens":json,"cyans":json,"blues":json,"magentas":json} (per range {"hue","saturation","lightness","range":[4 hue degrees]}; colorize: hue 0..360, saturation 0..100) + {"path":"work"|saved path name|{…path}? (the active path: becomes the vector mask; else the selection is the layer mask, or white with no selection),"opacity":0..1=1,"name":str?=the adjustment's name + number,"mode":blend mode name="normal" (not Pass Through),"clipToPrevious":bool=false}
layer.newAdjustmentLayer.invert	Invert	{} + {"path":"work"|saved path name|{…path}? (the active path: becomes the vector mask; else the selection is the layer mask, or white with no selection),"opacity":0..1=1,"name":str?=the adjustment's name + number,"mode":blend mode name="normal" (not Pass Through),"clipToPrevious":bool=false}
layer.newAdjustmentLayer.levels	Levels…	{"inBlack":0..253=0,"gamma":0.01..9.99=1,"inWhite":2..255=255,"outBlack":0..255=0,"outWhite":0..255=255,"red":json,"green":json,"blue":json,"eyedropper":json} (top level = composite; per channel {"inBlack","gamma","inWhite","outBlack","outWhite"} under red/green/blue, gray, cyan/magenta/yellow/black or lightness/a/b; eyedropper = the dialog's Set Black/Neutral Gray/White Point picker {"point":"black|gray|white","at":[x,y],"size":1..101=1} or {"point",…,"color":[r,g,b] 0..1}: black/white set each channel's input black/white to the sample, gray each channel's gamma so the sample turns neutral at its luma; colour composites: RGB and Grayscale (no gray); Image adjustments targeting a mask, alpha or Quick Mask sample that gray plane in any document mode, applied over the given levels) + {"path":"work"|saved path name|{…path}? (the active path: becomes the vector mask; else the selection is the layer mask, or white with no selection),"opacity":0..1=1,"name":str?=the adjustment's name + number,"mode":blend mode name="normal" (not Pass Through),"clipToPrevious":bool=false}
layer.newAdjustmentLayer.photoFilter	Photo Filter…	{"filter":"warming85|warmingLBA|warming81|cooling80|coolingLBB|cooling82|red|orange|yellow|green|cyan|blue|violet|magenta|sepia|deepRed|deepBlue|deepEmerald|deepYellow|underwater","color":"#rrggbb","density":0..100=25,"preserveLuminosity":bool=true} + {"path":"work"|saved path name|{…path}? (the active path: becomes the vector mask; else the selection is the layer mask, or white with no selection),"opacity":0..1=1,"name":str?=the adjustment's name + number,"mode":blend mode name="normal" (not Pass Through),"clipToPrevious":bool=false}
layer.newAdjustmentLayer.posterize	Posterize…	{"levels":2..255=4} + {"path":"work"|saved path name|{…path}? (the active path: becomes the vector mask; else the selection is the layer mask, or white with no selection),"opacity":0..1=1,"name":str?=the adjustment's name + number,"mode":blend mode name="normal" (not Pass Through),"clipToPrevious":bool=false}
layer.newAdjustmentLayer.selectiveColor	Selective Color…	{"method":"relative|absolute"="relative","colors":"reds|yellows|greens|cyans|blues|magentas|whites|neutrals|blacks"="reds","cyan":-100..100=0,"magenta":-100..100=0,"yellow":-100..100=0,"black":-100..100=0,"reds":json} (per-range [c,m,y,k] arrays: reds yellows greens cyans blues magentas whites neutrals blacks) + {"path":"work"|saved path name|{…path}? (the active path: becomes the vector mask; else the selection is the layer mask, or white with no selection),"opacity":0..1=1,"name":str?=the adjustment's name + number,"mode":blend mode name="normal" (not Pass Through),"clipToPrevious":bool=false}
layer.newAdjustmentLayer.threshold	Threshold…	{"level":1..255=128} + {"path":"work"|saved path name|{…path}? (the active path: becomes the vector mask; else the selection is the layer mask, or white with no selection),"opacity":0..1=1,"name":str?=the adjustment's name + number,"mode":blend mode name="normal" (not Pass Through),"clipToPrevious":bool=false}
layer.newAdjustmentLayer.vibrance	Vibrance…	{"vibrance":-100..100=0,"saturation":-100..100=0} + {"path":"work"|saved path name|{…path}? (the active path: becomes the vector mask; else the selection is the layer mask, or white with no selection),"opacity":0..1=1,"name":str?=the adjustment's name + number,"mode":blend mode name="normal" (not Pass Through),"clipToPrevious":bool=false}
layer.newFillLayer.gradient	Gradient…	{"from":"#rrggbb","to":"#rrggbb","angle":deg=90,"style":"linear|radial|angle|reflected|diamond","reverse":bool,"path":"work"|saved path name|{…path}? (the active path: becomes the vector mask; else the selection is the layer mask),"stops"?,"transparency"?,"midpoints"?,"scale"?,"offset"?,"dither"?,"align"? (as gradient.fill.set; stops replace from/to)}
layer.newFillLayer.pattern	Pattern…	{"pattern":id|name?=first library pattern,"patternName":name? (then `pattern` is an id; the name is used when no pattern has that id),"scale":1..1000=100,"angle":deg=0,"link":bool=true,"phase":[x,y]?,"path":"work"|saved path name|{…path}? (the active path: becomes the vector mask; else the selection is the layer mask)}
layer.newFillLayer.solidColor	Solid Color…	{"color":"#rrggbb"=foreground,"cmyk":[c,m,y,k]? (inks 0..1 the colour was picked as: a CMYK document's fill holds exactly these; default the foreground's CMYK pick),"path":"work"|saved path name|{…path}? (the active path: becomes the vector mask, making a shape; else the selection is the layer mask)}
layer.newLayerBasedSlice	New Layer Based Slice	{"layer":id?,"name":str?,"url":str?,"alt":str?} (follows the layer's bounds with effects) → {slice, rect}
layer.pickAt	Auto-Select Layer	{"x":px,"y":px,"target":"layer|group"="layer","select":bool=true,"mode":"replace|toggle|add"="replace","moveAutoSelect":bool=false (also skip Position locks),"list":bool=false (return visible layers at the point, including text bounds, topmost first)} → {layer} | {layers}
layer.quickExportAsPng	Quick Export as PNG	{"layer":id?,"path":text}
layer.rasterize.allLayers	All Layers	{}
layer.rasterize.fillContent	Fill Content	{"layer":id?} (no layer: every selected layer it applies to)
layer.rasterize.layer	Layer	{"layer":id?} (no layer: every selected layer it applies to)
layer.rasterize.layerStyle	Layer Style	{"layer":id?} (no layer: every selected layer with effects; bakes the effects, fill opacity and masks into the pixels)
layer.rasterize.shape	Rasterize Shape	{"layer":id?} (no layer: every selected shape layer)
layer.rasterize.smartObject	Smart Object	{"layer":id?} (no layer: every selected layer it applies to)
layer.rasterize.type	Type	{"layer":id?} (no layer: every selected layer it applies to)
layer.rasterize.vectorMask	Rasterize Vector Mask	{"layer":id?} (multiplied into the layer mask)
layer.rasterize.video	Video	{} → {}
layer.releaseClippingMask	Release Clipping Mask	{"layer":id?} (no layer: every selected layer)
layer.removeBackground	Remove Background	{"layer":id?,"sampleAllLayers":bool=false,"refine":bool=true} → {layer,bounds} (adds a layer mask from Select Subject; the Background becomes a normal layer)
layer.renameLayer	Rename Layer	{"layer":id?,"name":str}
layer.select	Select Layer	{"layer":id|str|{"index":uint}|{"ordinal":"Trgt|Frwr|Bckw|Frnt|Back"} | "name":str,"occurrence":index?,"mode":"replace|toggle|range|add|remove"="replace"} (typed references use the recorded full layer stack; name occurrence: zero-based document walk order; required for duplicate names; toggle = ⌘-click, range = ⇧-click, remove = deselect it, keeping at least one)
layer.selectAbove	Select Layer Above	{} (follows the Layers panel's rows; collapsed groups are one row)
layer.selectBelow	Select Layer Below	{} (follows the Layers panel's rows; collapsed groups are one row)
layer.selectBottom	Select Bottom Layer	{} (follows the Layers panel's rows; collapsed groups are one row)
layer.selectInRect	Select Layers in Marquee	{"x":px,"y":px,"width":px,"height":px,"target":"layer|group"="layer","mode":"replace|add"="replace","moveAutoSelect":bool=false (also skip effective Position locks),"clearOnEmpty":bool=false (clear on no hits in replace mode only)} → {layers} (layers whose content touches the rect, topmost first, skipping effective All locks and Background)
layer.selectLinkedLayers	Select Linked Layers	{}
layer.selectTop	Select Top Layer	{} (follows the Layers panel's rows; collapsed groups are one row)
layer.setAdjustment	Adjustment Properties	{"layer":id?, …params of that adjustment kind} (Levels, Curves: "eyedropper":{"point":"black|gray|white","at":[x,y],"size":1..101=1} or {"point",…,"color":[r,g,b] 0..1} = the Properties panel's Set Black/Neutral Gray/White Point, sampling the image below the layer, RGB and Grayscale (no gray) only)
layer.setEffectsExpanded	Expand/Collapse Effects	{"layer":id?,"expanded":bool?,"all":bool?} (no expanded: toggle; all: every layer with effects or smart filters; view state, not an undo step)
layer.setEffectsVisible	Show/Hide Effects	{"layer":id?,"index":n?,"visible":bool?} (no index: all of the layer's effects, the "Effects" row; index: the effect at that position in the layer's list; no visible: toggle)
layer.setExpanded	Expand/Collapse Group	{"layer":id?,"expanded":bool?,"all":bool?} (no expanded: toggle; all: every group; not an undo step)
layer.setLabelColor	Layer Color	{"color":"none|red|orange|yellow|green|seafoam|blue|indigo|magenta|fuchsia|violet|gray","layer":id|name|{"background":true}?} (no layer: selected layers; groups include descendants)
layer.setProps	Layer Properties	{"layer":id?,"layers":[id,…]? (the same change to each, one step: the Layers panel's controls with several layers selected),"name":str? (one layer only),"visible":bool?,"opacity":0..1?,"fill":0..1?,"blend":"Multiply|…"?,"clipped":bool?,"locked":bool?,"locks":{"transparency","pixels","position","artboard","all":bool}?,"channels":[bool,…]? (Advanced Blending: which colour channels blend, R G B / C M Y K / L a b)}
layer.showLayers	Show Layers	{"layer":id?}
layer.showOnly	Show Only This Layer	{"layer":id?} → {shownAlone} (⌥-click a layer's eye; again restores the other layers' visibility)
layer.smartFilter.blendingOptions	Blending Options…	{"layer":id?,"index":u32? (0 = bottom; default top),"blend":str?,"opacity":0..1?}
layer.smartFilter.clearSmartFilters	Clear Smart Filters	{"layer":id?}
layer.smartFilter.delete	Delete Smart Filter	{"layer":id?,"index":u32?}
layer.smartFilter.deleteFilterMask	Delete Filter Mask	{"layer":id?,"ifPresent":bool=false (true: a smart object without a filter mask is left as it is, as a Photoshop action's step needs where Photoshop added the mask by default)}
layer.smartFilter.disableFilterMask	Disable Filter Mask	{"layer":id?,"enabled":bool? (default: toggle)}
layer.smartFilter.disableSmartFilters	Disable Smart Filters	{"layer":id?,"enabled":bool? (default: toggle)}
layer.smartFilter.move	Move Smart Filter	{"layer":id?,"index":u32?,"to":u32}
layer.smartFilter.setParams	Edit Smart Filter	{"layer":id?,"index":u32?,"params":{…} (merged),"replace":bool=false (params replace the stored ones instead)}
layer.smartFilter.setVisible	Show/Hide Smart Filter	{"layer":id?,"index":u32?,"visible":bool? (default: toggle)}
layer.smartFilter.transfer	Move or Copy Smart Filters	{"from":id,"to":id,"filter":u32? (default: all, with the filter mask),"copy":bool=false}
layer.smartObjects.convertToEmbedded	Embed Linked	{"layer":id?}
layer.smartObjects.convertToLayers	Convert to Layers	{"layer":id?} (contents unpacked at the placement: one layer, or a group named after the smart object; smart filters are discarded)
layer.smartObjects.convertToLinked	Convert to Linked…	{"layer":id?,"path":str} (writes the contents there)
layer.smartObjects.convertToSmartObject	Convert to Smart Object	{"layer":id?} (default: combine selected layers)
layer.smartObjects.editContents	Edit Contents	{"layer":id?} → opens the contents as a new document; saving (layer.smartObjects.saveContents) or closing it updates the smart object
layer.smartObjects.embedAllLinked	Embed All Linked	{} (every linked smart object of the active document becomes embedded in one history step; a linked file that can't be read refuses the whole step and the error names it) -> {embedded: [layer ids]}
layer.smartObjects.exportContents	Export Contents…	{"layer":id?,"path":str (another extension than the contents' own exports them in that format)}
layer.smartObjects.exportSvg	Export SVG Contents	{"layer":id?} → {document,svg?|sourceBase64?,extension,sourceSize,fingerprint,contentsId}
layer.smartObjects.newSmartObjectViaCopy	New Smart Object via Copy	{"layer":id?}
layer.smartObjects.perspectiveWarp	Perspective Warp	{"planes":[{"src":[[x,y]×4],"dst":[[x,y]×4]}…] (corners clockwise from top-left; corners that coincide in src are linked),"straighten":"horizontal|vertical|auto"?,"interpolation":"bicubic|bilinear|nearest","layer":id?}
layer.smartObjects.puppetWarp	Puppet Warp	{"pins":[{"src":[x,y],"dst":[x,y],"rotate":deg?,"depth":n?}…],"mode":"rigid|normal|distort"="normal","density":"fewer|normal|more"="normal","expansion":px=2,"interpolation":"bicubic|bilinear|nearest","layer":id?} — mesh over the opaque region, as-rigid-as-possible; on a smart object it becomes a smart filter
layer.smartObjects.rasterize	Rasterize	{"layer":id?}
layer.smartObjects.relinkToFile	Relink to File…	{"layer":id?,"path":str}
layer.smartObjects.replaceContents	Replace Contents…	{"layer":id?,"path":str}
layer.smartObjects.resetTransform	Reset Transform	{"layer":id?} (the placement returns to 100 % of the current contents' own size with rotation, skew, Distort, Perspective and the Warp cleared, centred on the average of the placement's four corners; the smart filters stay; refused with nothing changed when the object can't be re-rendered (a visible filter PhotoCraft doesn't have, or contents that can't be read); one undo step)
layer.smartObjects.revealInFinder	Reveal in Finder	{"dryRun":bool=false}
layer.smartObjects.saveContents	Save Contents	{} (in an Edit Contents document)
layer.smartObjects.stackMode.entropy	Entropy	{"layer":id?}
layer.smartObjects.stackMode.kurtosis	Kurtosis	{"layer":id?}
layer.smartObjects.stackMode.maximum	Maximum	{"layer":id?}
layer.smartObjects.stackMode.mean	Mean	{"layer":id?}
layer.smartObjects.stackMode.median	Median	{"layer":id?}
layer.smartObjects.stackMode.minimum	Minimum	{"layer":id?}
layer.smartObjects.stackMode.none	None	{"layer":id?}
layer.smartObjects.stackMode.range	Range	{"layer":id?}
layer.smartObjects.stackMode.skewness	Skewness	{"layer":id?}
layer.smartObjects.stackMode.standardDeviation	Standard Deviation	{"layer":id?}
layer.smartObjects.stackMode.summation	Summation	{"layer":id?}
layer.smartObjects.stackMode.variance	Variance	{"layer":id?}
layer.smartObjects.updateAllModifiedContent	Update All Modified Content	{}
layer.smartObjects.updateChanged	Update Changed Linked Content	{} — re-render the active document's linked smart objects whose files changed on disk since they were last seen (size or modification time); the desktop app does this by itself every two seconds, as Photoshop does while a document is open. Files seen for the first time are only remembered. One Update Modified Content undo step per file → {updated: [layer ids]}
layer.smartObjects.updateModifiedContent	Update Modified Content	{"layer":id?}
layer.smartObjects.updateSvg	Update SVG Contents	{"document":id,"layer":id,"svg":"<svg …>","fingerprint":"original BLAKE3 hex","contentsId":id} → {layer,contentsId,fingerprint,updated}
layer.smartObjects.updateVectorSource	Update Vector Contents	{"document":id,"layer":id,"sourceBase64":"native bytes","extension":"ai|pdf|eps","previewSvg":"bounded display SVG","fingerprint":"original BLAKE3 hex","contentsId":id}
layer.smartObjects.warp	Warp	{"layer":id?,"rect":[x0,y0,x1,y1]? (warp box; default = layer content ∩ selection),"style":"custom|none|arc|arcLower|arcUpper|arch|bulge|shellLower|shellUpper|flag|wave|fish|rise|fisheye|inflate|squeeze|twist|cylinder","bend":%=50,"hDistort":%,"vDistort":%,"vertical":bool,"values":[left,bottom,right,top,topDepth,bottomDepth,wrap]? (cylinder: silhouettes and edges in document px, the ellipses' depths in half-axis units, wrap 0..1; horizontal only),"mesh":{"us":[0,…,1],"vs":[0,…,1],"points":[[x,y]…]} ((3c+1)×(3r+1) control points, row-major, document px; on a smart object `us`/`vs` span the source contents, so points equal to the placement are an identity warp even when it is skewed),"grid":[cols,rows]?,"warp":{full warp object}?,"interpolation":"bicubic|bilinear|nearest"} — on a type layer a style (or none) sets its Warp Text and the type stays editable
layer.stampDown	Stamp Down	{} → {layer} (a copy of the active layer merged into the pixel layer below; several selected: into a new layer above them)
layer.stampVisible	Stamp Visible	{} → {layer} (visible layers merged into a new layer above the active one, or into the active one if it is an empty pixel layer)
layer.toggleLockTransparency	Lock Transparent Pixels	{"layer":id?} (toggles; several layers selected: locks them all unless every one is locked)
layer.toggleMaskOverlay	Toggle Layer Mask Overlay	{"layer":id?} (shows or hides the active layer's mask as a rubylith over the composite, the `\` key; red at 50% unless Layer Mask Display Options, channel.options {"channel":"mask"}, set it; view state, not an undo step; painting while shown paints the mask)
layer.translate	Move Layer	{"layer":id?,"dx":i32,"dy":i32,"units":"px"|"pt"="px" (pt: points, whole pixels at the document's resolution),"target":"pixels"|"mask"="pixels","selection":bool=false,"wrap":bool=false,"nest":bool=false} → null | {nested:[id]} (no layer: every selected layer; linked layers follow; target mask: a layer whose mask is unlinked moves that mask alone, a linked mask moves with the layer; selection: the selection moves too, in the same step; wrap: View › Pattern Preview, pixels that leave the canvas come back on the opposite edge so the tile stays seamless; nest: auto-nesting as the Move tool does it, a layer whose bounds centre lands on another artboard joins it and one whose centre is off every artboard leaves for the top level; a clipping base takes the layers clipped to it along and a clipped layer goes only where its base goes; artboards, the Background, empty layers, layers whose board doesn't change, groups that would nest too deep and layers locked with Prevent Auto-Nesting (on the layer, a group around it or the destination board) stay put, with their whole clipping group; nested lists the layers that changed board)
layer.ungroupLayers	Ungroup Layers	{"layer":id?}
layer.vectorMask.add	Add Vector Mask	{"layer":id?,"path":{…}? | "name":str|"work"? (copy a document path),"hide":bool=false (Hide All = inverted)} → vector mask info. Without a path the mask reveals all.
layer.vectorMask.currentPath	Vector Mask: Current Path	{"layer":id?,"name":str|"work"="work"}
layer.vectorMask.delete	Delete Vector Mask	{"layer":id?}
layer.vectorMask.edit	Edit Vector Mask	{"layer":id?,"path":{…}?,"enabled":bool?,"linked":bool?,"density":0..100?,"feather":0..1000? (pixels),"invert":true?}. On a shape layer (whose path is its vector mask) only density and feather apply: they soften its fill, which shows beyond the path at 100 − density %. path: {"subpaths":[{"closed":bool=true,"op":"combine|subtract|intersect|exclude","knots":[[x,y] | {"anchor":[x,y],"in":[x,y],"out":[x,y],"smooth":bool}]}],"fillRule":"nonzero|evenodd","inverted":bool}
layer.vectorMask.enabled	Enable Vector Mask	{"layer":id?,"enabled":bool? (default: toggle)}
layer.vectorMask.fromPath	Vector Mask from Current Path	{"layer":id?,"name":str|"work"="work"}
layer.vectorMask.hideAll	Vector Mask: Hide All	{"layer":id?}
layer.vectorMask.info	Vector Mask Info	{"layer":id?} → {layer,path,enabled,linked,density,feather}
layer.vectorMask.linked	Link Vector Mask	{"layer":id?,"linked":bool? (default: toggle)}
layer.vectorMask.revealAll	Vector Mask: Reveal All	{"layer":id?}
layer.videoLayers.deleteFrame	Delete Frame	{} → {}
layer.videoLayers.duplicateFrame	Duplicate Frame	{} → {}
layer.videoLayers.insertBlankFrame	Insert Blank Frame	{} → {}
layer.videoLayers.interpretFootage	Interpret Footage…	{} → {}
layer.videoLayers.newBlankVideoLayer	New Blank Video Layer	{} → {}
layer.videoLayers.newVideoLayerFromFile	New Video Layer from File…	{} → {}
layer.videoLayers.rasterize	Rasterize	{} → {}
layer.videoLayers.reloadFrame	Reload Frame	{} → {}
layer.videoLayers.replaceFootage	Replace Footage…	{} → {}
layer.videoLayers.restoreAllFrames	Restore All Frames	{} → {}
layer.videoLayers.restoreFrame	Restore Frame	{} → {}
layer.videoLayers.showAlteredVideo	Show Altered Video	{} → {}
layer.xmpMetadata	Layer XMP Metadata	{"layer":id?,"rawData":string|null?} → {"layer","rawData","changed"} (no layer: the active layer; no rawData: read it; a string sets the layer's XMP packet, null removes it; as Photoshop's layer.xmpMetadata.rawData)
```

## layerComp（14）

```text
layerComp.apply	Apply Layer Comp	{"comp":id|name|{"index":int}|{"id":uint}|{"ordinal":"Trgt|Nxt|Prvs|Frst|Lst|Al"}? (default: last applied; typed index is one-based panel order, invalid indexes do nothing)} → {comp, missingLayers}
layerComp.delete	Delete Layer Comp	{"comp":id|name?}
layerComp.duplicate	Duplicate Layer Comp	{"comp":id|name?} → {comp}
layerComp.list	List Layer Comps	{} → {comps:[{id,name,comment,visibility,position,appearance,layers,missingLayers}],lastApplied,hasLastDocumentState}
layerComp.new	New Layer Comp…	{"name":str="Layer Comp N","comment":str="","visibility":bool=true,"position":bool=true,"appearance":bool=true} → {comp}
layerComp.next	Apply Next Layer Comp	{}
layerComp.previous	Apply Previous Layer Comp	{}
layerComp.rename	Rename Layer Comp	{"comp":id|name?,"name":str}
layerComp.reorder	Reorder Layer Comp	{"comp":id|name?,"index":integer (zero-based final position)}
layerComp.restoreLastDocumentState	Restore Last Document State	{}
layerComp.setComment	Layer Comp Comment	{"comp":id|name?,"comment":str}
layerComp.setOptions	Layer Comp Options…	{"comp":id|name?,"visibility":bool?,"position":bool?,"appearance":bool?,"name":str?,"comment":str?}
layerComp.update	Update Layer Comp	{"comp":id|name|"*"? (default: last applied; "*" = all),"what":"all|visibility|position|appearance"="all"}
layerComp.updateWarnings	Layer Comp Warnings	{"comp":id|name? (default: every comp; limits the report and the clear to that comp),"clear":bool=false (drop states of deleted layers)} → {warnings:[{comp,name,missingLayers}],count}
```

## measurementLog（3）

```text
measurementLog.delete	Delete Measurements	{"rows":[ids]}|{"all":true}
measurementLog.export	Export Measurements…	{"path":str? (CSV file; omitted → returns the CSV text),"rows":[ids]?}
measurementLog.list	Measurement Log	{} → rows and columns
```

## notes（4）

```text
notes.add	New Note	{"x":px,"y":px,"text":str="","author":str="","color":"#rrggbb"|[r,g,b]=pale yellow,"open":bool=true}
notes.delete	Delete Note	{"index":n}|{"all":true}
notes.list	Notes	{} → notes (index, author, text, colour, position, open, modified)
notes.set	Edit Note	{"index":n,"text":str?,"author":str?,"color":"#rrggbb"|[r,g,b]?,"x":px?,"y":px?,"open":bool?}
```

## paint（28）

```text
paint.artHistoryBrush	Art History Brush	{"points":[[x,y,pressure?],…],"size":1..5000 px=tool size,"hardness":0..100=tool hardness,"opacity":1..100=100,"flow":1..100=100,"spacing":1..1000 (% of size)=Brush Settings spacing,"smoothing":0..100=options bar Smoothing,"layer":id?=active,"target":"pixels"|"mask"|"filterMask"|"quickMask"|{"channel":i}=Channels panel target,"state":row (a History panel row, as history.setSource),"snapshot":id (a history.newSnapshot id; default: the History panel's source, as paint.historyBrush; a source of another canvas size or colour mode is an error),"style":"tightShort|tightMedium|tightLong|looseMedium|looseLong|dab|tightCurl|looseCurl"="tightMedium","area":0..100=50,"tolerance":0..100=0,"opacity":0..100=100 (overrides the common 1..100: how strongly the history state is painted; 0 changes nothing; no flow, mode is Normal)}
paint.backgroundEraser	Background Eraser	{"points":[[x,y,pressure?],…],"size":px?,"hardness":0..1?,"brush":{…}?,"preset":name?,"sampling":"continuous|once|backgroundSwatch"="continuous","limits":"discontiguous|contiguous|findEdges"="contiguous","tolerance":1..100=50,"protectForegroundColor":bool=false,"seed":u64?}
paint.blur	Blur	{"points":[[x,y,pressure?],…],"size":1..5000 px=tool size,"hardness":0..100=tool hardness,"opacity":1..100=100,"flow":1..100=100,"spacing":1..1000 (% of size)=Brush Settings spacing,"smoothing":0..100=options bar Smoothing,"layer":id?=active,"target":"pixels"|"mask"|"filterMask"|"quickMask"|{"channel":i}=Channels panel target,"strength":1..100=50,"sampleAllLayers":bool=false}
paint.bucket	Paint Bucket	{"x":px,"y":px,"tolerance":0..255=32,"contiguous":bool=true,"antiAlias":bool=true,"sampleAllLayers":bool=false,"contents":"foreground|pattern"="foreground","color":"#rrggbb"=foreground,"pattern":id|name (contents=pattern),"scale":%=100,"angle":deg,"opacity":1..100=100,"mode":"normal|multiply|…|clear (erases the filled area)"="normal","target":"pixels"|"mask"|"filterMask"|"quickMask"|{"channel":i}=Channels panel target}
paint.burn	Burn	{"points":[[x,y,pressure?],…],"size":1..5000 px=tool size,"hardness":0..100=tool hardness,"opacity":1..100=100,"flow":1..100=100,"spacing":1..1000 (% of size)=Brush Settings spacing,"smoothing":0..100=options bar Smoothing,"layer":id?=active,"target":"pixels"|"mask"|"filterMask"|"quickMask"|{"channel":i}=Channels panel target,"range":"shadows|midtones|highlights"="midtones","exposure":1..100=50,"protectTones":bool=true}
paint.cloneStamp	Clone Stamp	{"points":[[x,y,pressure?],…],"size":1..5000 px=tool size,"hardness":0..100=tool hardness,"opacity":1..100=100,"flow":1..100=100,"spacing":1..1000 (% of size)=Brush Settings spacing,"smoothing":0..100=options bar Smoothing,"layer":id?=active,"target":"pixels"|"mask"|"filterMask"|"quickMask"|{"channel":i}=Channels panel target,"source":[sx,sy] (sampled under the first point) | "offset":[dx,dy],"aligned":bool=true,"sampleLayer":"current|currentAndBelow|all"="current","mode":"normal|multiply|…"="normal","wrap":bool=false (repeat source and stroke at document edges for Pattern Preview) → {"damage","offset","aligned","nextSource"}}
paint.colorReplacement	Color Replacement Tool	{"points":[…],"brush":{…}?,"size":px?,"mode":"hue|saturation|color|luminosity"="color","sampling":"continuous|once|backgroundSwatch"="continuous","limits":"contiguous|discontiguous|findEdges"="contiguous","tolerance":1..100=30,"antiAlias":bool=true,"color":"#rrggbb"?=foreground,"target":"pixels"="pixels","seed":u64?}
paint.contentAwareMove	Content-Aware Move	{"offset":[dx,dy] (how far the selection was dragged),"mode":"move|extend"="move","structure":1..7=4 (3..7 copy the content exactly but for a band about a patch wide along its edge; 2 widens the band, 1 re-synthesises the content too),"color":0..10=0 (0 keeps the content's level; higher values bring it towards its new place, by up to about 0.04 × color),"sampleAllLayers":bool=false,"scaleX":%=100,"scaleY":%=100 (Transform On Drop: 1..10000, negative flips),"rotate":deg=0 (Transform On Drop, clockwise; scale and rotation are about the selection's centre, before the offset; a transformed patch may reach past the canvas edge),"layer":id?=active,"target":"pixels"|"mask"|"filterMask"|"quickMask"|{"channel":i}=Channels panel target} → {"damage","offset","mode","transformed"?} (a background job; the selection moves, and is transformed, with the content)
paint.dodge	Dodge	{"points":[[x,y,pressure?],…],"size":1..5000 px=tool size,"hardness":0..100=tool hardness,"opacity":1..100=100,"flow":1..100=100,"spacing":1..1000 (% of size)=Brush Settings spacing,"smoothing":0..100=options bar Smoothing,"layer":id?=active,"target":"pixels"|"mask"|"filterMask"|"quickMask"|{"channel":i}=Channels panel target,"range":"shadows|midtones|highlights"="midtones","exposure":1..100=50,"protectTones":bool=true}
paint.gradient	Gradient	{"from":[x,y],"to":[x,y],"style":"linear|radial|angle|reflected|diamond"="linear","colors":["#rrggbb",…]? (evenly spaced),"gradient":preset name?,"stops":[[t,"#rrggbb"|"foreground"|"background"],…]?,"transparency":[[t,0..100],…]? (default: the current gradient, see gradient.presets.select),"method":"classic|perceptual|linear|smooth"? (Photoshop's interpolation; omitted: straight stops),"smoothness":0..100=100,"reverse":bool=false,"dither":bool=true,"opacity":1..100=100,"mode":"normal|multiply|…"="normal","target":"pixels"|"mask"|"filterMask"|"quickMask"|{"channel":i}=Channels panel target}
paint.healingBrush	Healing Brush	{"points":[[x,y,pressure?],…],"size":1..5000 px=tool size,"hardness":0..100=tool hardness,"opacity":1..100=100,"flow":1..100=100,"spacing":1..1000 (% of size)=Brush Settings spacing,"smoothing":0..100=options bar Smoothing,"layer":id?=active,"target":"pixels"|"mask"|"filterMask"|"quickMask"|{"channel":i}=Channels panel target,"source":[sx,sy] | "offset":[dx,dy],"aligned":bool=true,"sampleLayer":"current|currentAndBelow|all"="current","mode":"normal|…"="normal","wrap":bool=false (View › Pattern Preview: the stroke goes on across the canvas edges) → {"damage","offset","aligned","nextSource"}}
paint.historyBrush	History Brush	{"points":[[x,y,pressure?],…],"size":1..5000 px=tool size,"hardness":0..100=tool hardness,"opacity":1..100=100,"flow":1..100=100,"spacing":1..1000 (% of size)=Brush Settings spacing,"smoothing":0..100=options bar Smoothing,"layer":id?=active,"target":"pixels"|"mask"|"filterMask"|"quickMask"|{"channel":i}=Channels panel target,"state":row (a History panel row, as history.setSource: 0 = oldest state, then the current one, then the greyed redo states),"snapshot":id (a history.newSnapshot id; default: the History panel's source, else the oldest held state; a source of another canvas size is an error),"eraseToHistory":bool=false (a layer missing from a source state that holds a single layer paints that layer's own pixels, or a shape's solid colour, else white, outside its shape too, as the Eraser's Erase to History does, instead of an error),"pencil":bool=false and "block":bool=false with "zoom" (with eraseToHistory: the hard aliased tip or the square, as paint.pencil's),"brush":{…}? (BrushSettings fields, deep-merged onto the session brush as paint.stroke's: the brush the stroke was pressed with, so a tool picked mid-stroke changes nothing)}
paint.magicEraser	Magic Eraser	{"x":px,"y":px,"tolerance":0..255=32,"antiAlias":bool=true,"contiguous":bool=true,"sampleAllLayers":bool=false,"opacity":1..100=100}
paint.mixerBrush	Mixer Brush	{"points":[…] (long segments are interpolated),"brush":{…}?,"preset":name?,"size":0.5..5000 px?,"wet":0..100=brush.mixer.wet,"load":0..100=brush.mixer.load,"mix":0..100=brush.mixer.mix,"flow":0..100=brush.mixer.flow,"color":"#rrggbb"?=foreground,"sampleAllLayers":bool=brush.mixer.sampleAllLayers,"cleanAfterStroke":bool=brush.mixer.cleanAfterStroke,"loadAfterStroke":bool=brush.mixer.loadAfterStroke,"seed":u64?,"mixerState":{reservoir,amount,pickup,spatial,color} (optional captured replay state; spatial is null or 4096 RGBA colors)}
paint.mixerLoad	Load Mixer Brush	{"x":px,"y":px,"size":"point"|1|3|5|11|31|51|101=1,"sampleAllLayers":bool=brush.mixer.sampleAllLayers} → {"loaded":bool,"color"?:[r,g,b,a]} (loads the Mixer Brush reservoir from the canvas colour there, as ⌥-click does; the foreground colour is unchanged; the next strokes keep that load while the foreground stays as it is)
paint.patch	Patch	{"offset":[dx,dy] (how far the selection was dragged),"mode":"source|destination"="source","contentAware":bool=false (fill the selection content-aware from the dragged-to place; a background job),"structure":1..7=4 (content-aware: 3..7 copy the middle exactly, 1..2 re-synthesise more of it),"color":0..10=0 (content-aware: how far the copy's level adapts to the selection's surroundings),"sampleAllLayers":bool=false (content-aware),"layer":id?=active,"target":"pixels"|"mask"|"filterMask"|"quickMask"|{"channel":i}=Channels panel target} → {"damage","offset"}
paint.patternStamp	Pattern Stamp	{"points":[[x,y,pressure?],…],"size":1..5000 px=tool size,"hardness":0..100=tool hardness,"opacity":1..100=100,"flow":1..100=100,"spacing":1..1000 (% of size)=Brush Settings spacing,"smoothing":0..100=options bar Smoothing,"layer":id?=active,"target":"pixels"|"mask"|"filterMask"|"quickMask"|{"channel":i}=Channels panel target,"pattern":id|name?=Patterns panel current,"scale":1..1000 %=100,"angle":deg=0,"aligned":bool=true,"impressionist":bool=false,"mode":"normal|multiply|…|behind (paints beneath existing pixels)"="normal","phase":[px,py]? → {"damage","phase","aligned","pattern"}}
paint.pencil	Pencil	{"points":[[x,y,pressure?,tiltX?,tiltY?,rotation?,timeMs?,wheel?],…],"brush":{…}?,"preset":name?,"size":0.5..5000 px?,"opacity":0..1?,"color":"#rrggbb"?=foreground,"mode":"normal|multiply|screen|…|behind (paints beneath existing pixels)|clear (erases with this brush)"="normal","erase":bool?,"block":bool=false (a hard 16×16 screen-px square, 16/zoom doc px; size, opacity, flow, hardness and dynamics ignored: the Eraser's Block mode),"zoom":view zoom=1,"autoErase":bool=false,"seed":u64?,"target":"pixels"|"mask"|"filterMask"|"quickMask"|{"channel":i}=Channels panel target}
paint.redEye	Red Eye	{"x":px, "y":px} | {"points":[[x,y],…] (at most 64)},"pupilSize":1..100=50,"darken":0..100=50,"layer":id?=active,"target":"pixels"|"mask"|"filterMask"|"quickMask"|{"channel":i} → {"damage":[x,y,w,h], "pixels":n}
paint.remove	Remove	{"points":[[x,y,pressure?],…],"size":1..5000 px=tool size,"hardness":0..100=tool hardness,"opacity":1..100=100,"flow":1..100=100,"spacing":1..1000 (% of size)=Brush Settings spacing,"smoothing":0..100=options bar Smoothing,"layer":id?=active,"target":"pixels"|"mask"|"filterMask"|"quickMask"|{"channel":i}=Channels panel target,"strokes":[[[x,y,pressure?],…]|{"points":[…],"size"?,"hardness"?,"spacing"?},…]? (several strokes removed together, as one job and one undo step, each with its own size, hardness and spacing when given; else "points"),"closeLoops":bool=true (a stroke around an object removes what it encloses),"sampleAllLayers":bool=false,"newLayer":bool=false (the fill goes to a new layer above the target, which stays as it was) → {"damage","layer"?} (a background job)}
paint.setSymmetry	Set Painting Symmetry	{"mode":"vertical|horizontal|dual|diagonal","center":[x,y]?,"rotation":degrees=0}
paint.sharpen	Sharpen	{"points":[[x,y,pressure?],…],"size":1..5000 px=tool size,"hardness":0..100=tool hardness,"opacity":1..100=100,"flow":1..100=100,"spacing":1..1000 (% of size)=Brush Settings spacing,"smoothing":0..100=options bar Smoothing,"layer":id?=active,"target":"pixels"|"mask"|"filterMask"|"quickMask"|{"channel":i}=Channels panel target,"strength":1..100=50,"protectDetail":bool=true,"sampleAllLayers":bool=false}
paint.smudge	Smudge	{"points":[[x,y,pressure?],…],"size":1..5000 px=tool size,"hardness":0..100=tool hardness,"opacity":1..100=100,"flow":1..100=100,"spacing":1..1000 (% of size)=Brush Settings spacing,"smoothing":0..100=options bar Smoothing,"layer":id?=active,"target":"pixels"|"mask"|"filterMask"|"quickMask"|{"channel":i}=Channels panel target,"strength":1..100=50,"fingerPainting":bool=false (starts with the foreground colour),"sampleAllLayers":bool=false,"mode":"normal|darken|lighten|hue|saturation|color|luminosity"="normal" (how the smudged colour replaces the pixel; 8-bit RGB, else Normal)}
paint.sponge	Sponge	{"points":[[x,y,pressure?],…],"size":1..5000 px=tool size,"hardness":0..100=tool hardness,"opacity":1..100=100,"flow":1..100=100,"spacing":1..1000 (% of size)=Brush Settings spacing,"smoothing":0..100=options bar Smoothing,"layer":id?=active,"target":"pixels"|"mask"|"filterMask"|"quickMask"|{"channel":i}=Channels panel target,"mode":"desaturate|saturate"="desaturate","vibrance":bool=true (flow = sponge strength)}
paint.spotHealing	Spot Healing Brush	{"points":[[x,y,pressure?],…],"size":1..5000 px=tool size,"hardness":0..100=tool hardness,"opacity":1..100=100,"flow":1..100=100,"spacing":1..1000 (% of size)=Brush Settings spacing,"smoothing":0..100=options bar Smoothing,"layer":id?=active,"target":"pixels"|"mask"|"filterMask"|"quickMask"|{"channel":i}=Channels panel target,"type":"contentAware|createTexture|proximityMatch"="contentAware","sampleAllLayers":bool=false}
paint.stroke	Brush Stroke	{"points":[[x,y,pressure?,tiltX?,tiltY?,rotation?,timeMs?,wheel?],…],"brush":{…BrushSettings}?,"preset":name?,"size":0.5..5000 px?,"hardness":0..1?,"opacity":0..1?,"flow":0..1?,"fill":bool=false (fill the region the closed `points` enclose with the brush colour, its edge anti-aliased and softened by hardness, instead of stamping the outline; a closed gesture paints a filled dab, not a ring),"spacing":0..10?,"color":"#rrggbb"?=foreground,"mode":"normal|multiply|screen|…|clear (erases with this brush)"="normal","erase":bool?,"smoothing":0..1?,"zoom":number=1,"seed":u64?,"target":"pixels"|"mask"|"filterMask"|"quickMask"|{"channel":i}=Channels panel target}
paint.symmetryDisable	Disable Painting Symmetry	{}
paint.symmetryFromPath	Make Symmetry Path	{"name":"work"|"layer"|savedPathName="work"} — mirror Brush, Pencil and Eraser strokes across the path
```

## path（27）

```text
path.addAnchor	Add Anchor Point	{"name":str|"work"|"layer"="work","layer":id? (with "layer": a shape layer's path, a vector mask, or else type on a path's Type Path),"typePath":bool=false (with "layer": the Type Path even when the type layer has a vector mask),"subpath":i,"knot":j (the segment leaving it),"t":0<t<1=0.5 (where on the segment) (a curve is split there without changing its shape and gets a smooth anchor; a straight segment gets a corner) (the result also has anchor:{subpath,knot})} → {name,path}
path.addToSelection	Add Path to Selection	{"name":str|"work"|"layer"="work","feather":px=0,"antiAlias":bool=true} (path.toSelection with mode "add")
path.bendSegment	Drag Segment	{"name":str|"work"|"layer"="work","layer":id? (with "layer": a shape layer's path, a vector mask, or else type on a path's Type Path),"typePath":bool=false (with "layer": the Type Path even when the type layer has a vector mask),"subpath":i,"knot":j (the segment leaving it),"t":0..1=0.5 (where it was grabbed),"move":[dx,dy] (a straight segment moves with its anchors; a curve reshapes through the dragged point)} → {name,path}
path.clippingPath.clear	Clear Clipping Path	{}
path.clippingPath.set	Clipping Path	{"name":savedPathName,"flatness":0..100=0} (PSD export clipping path)
path.convertPoint	Convert Point	{"name":str|"work"|"layer"="work","layer":id? (with "layer": a shape layer's path, a vector mask, or else type on a path's Type Path),"typePath":bool=false (with "layer": the Type Path even when the type layer has a vector mask),"subpath":i,"knot":j,"out":[x,y]? (none: corner with retracted handles; given: smooth with this out handle and its mirror),"curvature":bool=false (the Curvature Pen's double-click: toggles smooth/corner and reflows the smooth knots of the subpath; out ignored),"stepName":"Change Anchor Point"? (History step name; the Convert Point tool sends it; default "Convert Point"; any other value is refused)} → {name,path}
path.delete	Delete Path	{"name":str|"work"="work"}
path.deleteAnchor	Delete Anchor Point	{"name":str|"work"|"layer"="work","layer":id? (with "layer": a shape layer's path, a vector mask, or else type on a path's Type Path),"typePath":bool=false (with "layer": the Type Path even when the type layer has a vector mask),"subpath":i,"knot":j,"segments":bool=false (its neighbours are joined, keeping their handles; segments = ⌫/Delete on a selected anchor: its two segments go too, so a closed subpath opens there and an open one splits; a subpath's last anchor removes the subpath; the path's only anchor empties a saved path and is refused elsewhere) (the result also has subpathRemoved:bool)} → {name,path}
path.fill	Fill Path	{"name":str|"work"|"layer"="work","layer":id? (pixel layer, default active),"color":"#rrggbb"=foreground,"opacity":0..100=100,"mode":"normal|multiply|…"="normal","feather":px=0,"antiAlias":bool=true}
path.info	Path Info	{"name":str|"work"|"layer"="work"} → {name,path}
path.intersectWithSelection	Intersect Path with Selection	{"name":str|"work"|"layer"="work","feather":px=0,"antiAlias":bool=true} (path.toSelection with mode "intersect")
path.list	List Paths	{} → {paths:[{name,knots,subpaths}],workPath,clippingPath,layerPath (active layer's shape path / vector mask),typePath (active type layer's Type Path, if it is on a path)}
path.mergeShapeComponents	Merge Shape Components	{"name":str|"work"|"layer"="work","layer":id? (with "layer": a shape layer's path, a vector mask, or else type on a path's Type Path),"typePath":bool=false (with "layer": the Type Path even when the type layer has a vector mask),"tolerance":px=0.1 (bakes the components' path operations into plain combined outlines, traced from the exact coverage)} → {name,path}
path.moveAnchors	Drag Anchor Points	{"name":str|"work"|"layer"="work","layer":id? (with "layer": a shape layer's path, a vector mask, or else type on a path's Type Path),"typePath":bool=false (with "layer": the Type Path even when the type layer has a vector mask),"anchors":[[subpath,knot],…],"move":[dx,dy],"curvature":bool=false (anchors move with their handles; Direct Selection drag. curvature = the Curvature Pen's drag: every smooth knot of the touched subpaths gets its handles recomputed so the curve flows through the anchors),"stepName":"Drag Path"? (History step name; the Convert Point tool sends it when it drags a whole path; default "Drag Anchor Points"; any other value is refused)} → {name,path}
path.moveHandle	Drag Direction Point	{"name":str|"work"|"layer"="work","layer":id? (with "layer": a shape layer's path, a vector mask, or else type on a path's Type Path),"typePath":bool=false (with "layer": the Type Path even when the type layer has a vector mask),"subpath":i,"knot":j,"handle":"in|out","to":[x,y],"independent":bool=false (a smooth point turns its other handle to stay collinear; independent = ⌥ / Convert Point, makes a corner),"stepName":"Corner Drag"? (History step name; the Convert Point tool sends it; default "Drag Direction Point"; any other value is refused)} → {name,path}
path.rename	Rename Path	{"name":str|"work"="work","to":str} (renaming the work path saves it)
path.set	Set Path	{"name":str|"work"="work","path":{…},"op":"combine|subtract|intersect|exclude"? (append to the existing path with this op instead of replacing)}. path: {"subpaths":[{"closed":bool=true,"op":"combine|subtract|intersect|exclude","knots":[[x,y] | {"anchor":[x,y],"in":[x,y],"out":[x,y],"smooth":bool}]}],"fillRule":"nonzero|evenodd","inverted":bool}
path.setOperation	Path Operation	{"name":str|"work"|"layer"="work","layer":id? (with "layer": a shape layer's path, a vector mask, or else type on a path's Type Path),"typePath":bool=false (with "layer": the Type Path even when the type layer has a vector mask),"subpaths":[i,…],"op":"combine|subtract|intersect|exclude" (the shape components holding these subpaths take the operation; the first component always combines and keeps its own; the Path Operations menu with components selected)} → {name,path}
path.stroke	Stroke Path	{"name":str|"work"|"layer"="work","layer":id? (pixel layer),"tool":"brush|pencil|eraser|backgroundEraser|cloneStamp|patternStamp|healingBrush|spotHealingBrush|historyBrush|blur|sharpen|smudge|dodge|burn|sponge|colorReplacement|mixerBrush"="brush","simulatePressure":bool=false (taper both ends when the brush follows pen pressure),"size":0.5..5000 px?,"hardness":0..1?,"opacity":0..100?,"color":"#rrggbb"=foreground} (current brush settings otherwise; tools past the Eraser run their paint.* command along the path and take its params)
path.style.copyFill	Copy Fill	{} (copies active shape layer fill)
path.style.copyStroke	Copy Complete Stroke	{} (copies active shape layer stroke)
path.style.pasteFill	Paste Fill	{"layer":id?} (pastes copied fill onto active shape layer)
path.style.pasteStroke	Paste Complete Stroke	{"layer":id?} (pastes copied stroke onto active shape layer)
path.subtractFromSelection	Subtract Path from Selection	{"name":str|"work"|"layer"="work","feather":px=0,"antiAlias":bool=true} (path.toSelection with mode "subtract")
path.toSelection	Make Selection from Path	{"name":str|"work"|"layer"="work","feather":px=0,"antiAlias":bool=true,"mode":"replace|add|subtract|intersect"="replace"}
path.toShape	Make Shape from Path	{"name":str|"work"|"layer"="work" (the Work Path becomes the shape's path; a saved path stays) | "path":{subpaths} (inline; not with name),"consumeWorkPath":bool=false (with path: it was drawn into the Work Path, which goes),"fill":"#rrggbb"|[r,g,b,a]|{"gradient":{"stops":[[t,"#hex"|[r,g,b,a]|stored Color]],"angle":deg,"scale":%,"style":"linear|radial|angle|reflected|diamond","reverse":bool,"opacityStops":[[t,0..1]]?,"midpoints":[0..1]?,"offset":[x,y]?,"dither":bool?,"align":bool?}}|{"pattern":name}|null (no fill)=foreground,"stroke":{"width":px,"color":"#rrggbb"|fill,"opacity":0..100,"align":"inside|center|outside","cap":"butt|round|square","join":"miter|round|bevel","miterLimit":n,"dashes":[multiples of width],"dashOffset":n}|null=none,"layerName":str?} → shape.info
path.transform	Free Transform Path	{"name":str|"work"|"layer"="work","layer":id? (with layer target),"vectorMask":bool=false (with the layer target: its vector mask's path, not a shape layer's path),"matrix":[a,b,c,d,e,f] | "quad":[[x,y]×4] (Distort/Perspective: where the frame's corners go, clockwise from top-left) | "style"|"mesh"|"warp":… (Warp, as edit.transform.warp) | "translateX":px?,"translateY":px?,"scaleX":factor?,"scaleY":factor?,"angle":degrees?,"rect":[x0,y0,x1,y1]? (the quad's or warp's frame; default = path control bounds)} (numeric transforms pivot on path bounds center)
```

## pattern（10）

```text
pattern.delete	Delete Pattern	{"pattern":id|name} (library only; documents keep their copy)
pattern.export	Export Patterns…	{"path":".pat file","patterns":[id|name]? (default: the whole library)}
pattern.import	Import Patterns…	{"path":".pat file"?,"data":base64 bytes? (instead of a path)} → {imported:[ids],count}
pattern.list	Patterns	{} → [{id,name,width,height,mode,depth,inDocument,inLibrary}]
pattern.presets.apply	New Pattern Fill Layer from Preset	{"pattern":id|name?=selected,"scale":1..1000=100,"angle":deg=0} → {layer}
pattern.presets.edit	Edit Pattern Presets	{"action":"rename|delete|move|newGroup|renameGroup|deleteGroup","preset":name|[names] (rename/delete/move),"group":name? (narrows the lookup; the group for renameGroup/deleteGroup),"name":str (rename: new name; newGroup/renameGroup: group name),"to":group (move),"index":n? (move)}
pattern.presets.list	Pattern Presets	{} → {groups:[{name,patterns:[{id,name,width,height}]}],current}
pattern.presets.new	New Pattern Preset	{"name":str?,"group":name?,"rect":[x0,y0,x1,y1]?} (Define Pattern from the selection/canvas into a group)
pattern.presets.select	Select Pattern	{"pattern":id|name,"applyToLayer":bool=true (also changes a selected Pattern Fill layer)} (Fill and new Pattern Fill layers default to it)
pattern.rename	Rename Pattern	{"pattern":id|name,"name":str}
```

## plugin（5）

```text
plugin.install	Install Plug-in…	{"path":text,"data":json,"replace":bool=true} (path: a .wasm file, native only; data: the module as base64)
plugin.list	List Plug-ins	{}
plugin.reload	Reload Plug-ins	{"path":text} (a folder of .wasm plug-ins; default: the Plug-ins preference folder)
plugin.remove	Remove Plug-in	{"id":text}
plugin.run	Run Plug-in	{"id":text,"params":json} (plug-in parameters under "params" or at the top level; see plugin.list)
```

## prefs（3）

```text
prefs.get	Get Preferences	{"path":"section.key"?=everything (e.g. "performance.historyStates", "colorSettings.workingRgb")}
prefs.reset	Reset Preferences	{"path":"section|section.key"?=everything}
prefs.set	Set Preferences	{"path":"section.key","value":json} or {"values":{"section.key":json,…}} (validated; all or nothing)
```

## select（35）

```text
select.all	All	{}
select.allLayers	All Layers	{}
select.colorRange	Color Range…	{"select":"sampledColors|reds|yellows|greens|cyans|blues|magentas|highlights|midtones|shadows|skinTones|outOfGamut"="sampledColors","color":"#rrggbb"=foreground,"colors":["#rrggbb",…]?,"points":[[x,y],…]? (eyedropper samples),"subtractPoints":[[x,y],…]? (minus eyedropper),"order":["+"|"-",…]? (click order of points and subtractPoints; default all points first),"fuzziness":0..200=40 (tones: 0..100 %=20),"detectFaces":bool=false (not available yet: refused),"localized":bool=false,"range":0..100=100 (% of the longer side),"tonalRange":level|[lo,hi] (shadows 65, highlights 190, midtones [105,150]),"invert":bool=false,"sampleAllLayers":bool=true,"mode":"replace|add|subtract|intersect"="replace"}
select.convertToShape	Convert to Shape	{"tolerance":0.5..10 px=2} → shape.info
select.deselect	Deselect	{}
select.deselectLayers	Deselect Layers	{}
select.drop	Drop Floating Selection	{} → {dropped, offset} (drops the floating piece into its layer and moves the selection with it, shrunk to the moved pixels: the selection limited to where the layer has pixels, as in Photoshop; a mask or an empty piece keeps the selection's shape; one history step)
select.editInQuickMaskMode	Edit in Quick Mask Mode	{"on":bool?=toggle}
select.findLayers	Find Layers	{"name":str?} (filters the Layers panel by Name, a case-insensitive substring, selecting none of the matches; without `name` the panel's Name text is kept; replies with the matching layers)
select.float	Float Selection	{"dx":px=0,"dy":px=0,"copy":bool=false,"stepName":string="Move" (History name of the step that drops the piece; blank or over 64 characters falls back to Move),"target":"pixels"|"mask"="pixels" (mask: float the selected part of the layer's mask, the hole takes the background colour)} → {layer, offset} (cuts the selected pixels of the active layer into a floating piece the first time, or with copy leaves them and floats a duplicate; on the Background the hole takes the background colour; then moves it by whole pixels; dropped by select.drop or any other command, put back by edit.undo)
select.focusArea	Focus Area…	{"range":0..1=0.5,"noise":0..1=0,"sampleAllLayers":bool=true,"mode":"replace|add|subtract|intersect"="replace"}
select.grow	Grow	{"tolerance":0..255=32,"sampleAllLayers":bool=false}
select.inverse	Inverse	{}
select.isolateLayers	Isolate Layers	{"on":bool? (default: toggle)} — Layers panel lists only the selected layers → {isolated, layers}
select.lasso	Lasso	{"points":[[x,y],…],"mode":"replace|add|subtract|intersect"="replace","antiAlias":bool=true,"feather":px=0,"polygonal":bool=false,"historyName"?:text (1..64 characters with a visible one, no control, line-break or hidden format characters, invisible padding at the ends (spaces, joiners, fillers, blank Braille and other default-ignorable blanks, and selectors cut off by them) trimmed; the History step name when a tool other than the Lasso draws it, e.g. "Patch Tool"; default "Lasso")}
select.loadLuminosity	Load Luminosity	{}
select.loadSelection	Load Selection…	{"channel":index|name|"composite"|"red|green|blue|…"|"transparency"|"mask"|"vectorMask"|"quickMask"|"selection"|"targeted" (the Channels panel's target),"layer":id|name|{"name":str}|{"background":true}?,"document":index?,"invert":bool=false,"operation":"new|add|subtract|intersect"="new"}
select.magicWand	Magic Wand	{"x":px,"y":px,"tolerance":0..255=32,"contiguous":bool=true,"antiAlias":bool=true,"sampleAllLayers":bool=false,"mode":"replace|add|subtract|intersect"="replace"} (samples the visible alpha, Quick Mask, or layer mask when that is the picture)
select.magneticLasso	Magnetic Lasso	{"points":[[x,y],…] (≥3 fastening points in order; with trace=false, the finished outline),"width":1..256=10 (px: follows edges this close to the points),"contrast":1..100=10 (%: weaker edges are ignored),"close":"magnetic|straight"="magnetic" (how the last point joins the first),"trace":bool=true,"mode":"replace|add|subtract|intersect"="replace","antiAlias":bool=true,"feather":0..1000=0 (px)}
select.modify.border	Border…	{"radius":1..200=1}
select.modify.contract	Contract…	{"radius":1..500=1,"applyAtCanvasBounds":bool=false}
select.modify.expand	Expand…	{"radius":1..500=1,"applyAtCanvasBounds":bool=false}
select.modify.feather	Feather…	{"radius":0.1..1000=1,"applyAtCanvasBounds":bool=false}
select.modify.smooth	Smooth…	{"radius":1..500=1,"applyAtCanvasBounds":bool=false}
select.object	Object Selection	{"rect":[x,y,w,h] | "point":[x,y],"mode":"replace|add|subtract|intersect"="replace","sampleAllLayers":bool=false} (point: the Object Finder's object under the point, as hovering previews it)
select.quick	Quick Selection	{"points":[[x,y],…],"size":px=30,"mode":"add|subtract|replace"="add","sampleAllLayers":bool=false,"enhanceEdge":bool=false}
select.rect	Rectangular Selection	{"x":i32,"y":i32,"width":u32,"height":u32,"mode":"replace|add|subtract|intersect"="replace","ellipse":bool=false,"line":"row|column"?,"antiAlias":bool=true,"feather":px=0}
select.refineEdge	Refine Edge	{"radius":px=0,"smartRadius":bool=false,"smooth":0..100=0,"feather":px=0,"contrast":0..100=0,"shiftEdge":-100..100=0,"decontaminate":bool=false,"amount":0..100=100,"output":"selection|layerMask|newLayer|newLayerWithMask|newDocument|newDocumentWithMask"="selection","sampleAllLayers":bool=false,"refineStrokes":[{"points":[[x,y],…],"size":px=30,"mode":"add|subtract"="add"},…]=[],"edits":[{"tool":"quick","points":[[x,y],…],"size":px=30,"mode":"add|subtract"="add","sampleAllLayers":bool=false} | {"tool":"brush","points":[[x,y],…],"size":px=30,"hardness":0..100=100,"mode":"add|subtract"="add"} | {"tool":"lasso","points":[[x,y],…≥3],"mode":"add|subtract"="add"} | {"tool":"object","rect":[x,y,w,h] | "point":[x,y],"mode":"add|subtract"="add","sampleAllLayers":bool=false} | {"tool":"subject","mode":"replace|add|subtract"="replace","sampleAllLayers":bool=true} | {"tool":"clear"} | {"tool":"invert"},…]=[]} (refineStrokes: the Refine Edge Brush, in painting order: add refines the painted area from the image, subtract keeps the original edge there; edits: the workspace's Quick Selection, Brush, Lasso, Object Selection, Select Subject, Clear Selection and Invert, applied in order to the selection before its edge is refined)
select.reselect	Reselect	{}
select.saveSelection	Save Selection…	{"name":str?,"channel":"new"|index|name="new","document":index?,"operation":"new|replace|add|subtract|intersect"="new"}
select.similar	Similar	{"tolerance":0..255=32,"sampleAllLayers":bool=false}
select.sky	Sky	{"mode":"replace|add|subtract|intersect"="replace","sampleAllLayers":bool=true,"threshold":0..100=50 (higher = stricter),"softness":0..100=50 (edge softness)} → {selected, changed, coverage (0–1 of the canvas), bounds [x,y,w,h]}
select.subject	Subject	{"sampleAllLayers":bool=false,"mode":"replace|add|subtract|intersect"="replace"} (samples the selected layer; the composite when no pixel layer is selected)
select.toWorkPath	Make Work Path	{"tolerance":0.5..10 px=2} → {subpaths,knots}
select.transformSelection	Transform Selection	{"rect":[x0,y0,x1,y1]? (frame; default = selection bounds),"quad"|"corners":[[x,y]×4]? (where the frame's corners go: distort/perspective),"matrix":[a,b,c,d,e,f]?,"scaleX":%=100,"scaleY":%=100,"rotate":deg=0,"skewX":deg=0,"skewY":deg=0,"dx":px=0,"dy":px=0,"stepName":"Move Selection"? (History step name for a plain move; the UI sends it for a drag of the outline; default "Transform Selection"; any other value is refused),"reference":"center|topLeft|top|topRight|left|right|bottomLeft|bottom|bottomRight"|[x,y]="center","style"|"mesh"|"grid"|"warp":… (warp, as edit.transform.warp),"interpolation":"bilinear|bicubic|nearest|bicubicSharper|bicubicSmoother|bicubicAutomatic"="bilinear" (Photoshop's bicubic variants render as Bicubic)}
```

## session（1）

```text
session.inspect	Inspect Session	{}
```

## shape（10）

```text
shape.create	New Shape Layer	{"kind":"rect|roundedRect|ellipse|polygon|star|line|path"="rect","rect":[x,y,w,h] (rect/roundedRect/ellipse/polygon/star),"radii":[tl,tr,br,bl]|r (roundedRect=10),"sides":3..100=5,"starRatio":0..1 (star=0.5),"cornerRadius":px=0 (polygon: rounds every vertex, star: its outer points; the Triangle tool is a 3-sided polygon),"from":[x,y],"to":[x,y],"weight":px=1 (line),"arrowStart":bool=false,"arrowEnd":bool=false,"arrowWidth":px=52,"arrowLength":px=50,"arrowConcavity":0..100=0 (line),"path":{…} (kind path),"fill":"#rrggbb"|[r,g,b,a]|{"gradient":{"stops":[[t,"#hex"|[r,g,b,a]|stored Color]],"angle":deg,"scale":%,"style":"linear|radial|angle|reflected|diamond","reverse":bool,"opacityStops":[[t,0..1]]?,"midpoints":[0..1]?,"offset":[x,y]?,"dither":bool?,"align":bool?}}|{"pattern":name}|null (no fill)=foreground,"stroke":{"width":px,"color":"#rrggbb"|fill,"opacity":0..100,"align":"inside|center|outside","cap":"butt|round|square","join":"miter|round|bevel","miterLimit":n,"dashes":[multiples of width],"dashOffset":n}|null=none,"name":str?,"addTo":layerId? + "op":"combine|subtract|intersect|exclude" (append to an existing shape layer)} → shape.info. path: {"subpaths":[{"closed":bool=true,"op":"combine|subtract|intersect|exclude","knots":[[x,y] | {"anchor":[x,y],"in":[x,y],"out":[x,y],"smooth":bool}]}],"fillRule":"nonzero|evenodd","inverted":bool}
shape.edit	Edit Shape	{"layer":id?,"path":{…}? (replaces; drops live shape),"kind":str?,"rect":[x,y,w,h]?,"radii":[tl,tr,br,bl]|r?,"sides":n?,"starRatio":r?,"cornerRadius":px?,"from":[x,y]?,"to":[x,y]?,"weight":px? (live-shape params regenerate the path),"arrowStart":bool?,"arrowEnd":bool?,"arrowWidth":px?,"arrowLength":px?,"arrowConcavity":0..100? (line arrows),"move":[dx,dy]?,"transform":[a,b,c,d,e,f]?,"op":"combine|…"? + "subpath":index? (default all but the first),"fillRule":"nonzero|evenodd"?,"fill":"#rrggbb"|[r,g,b,a]|{"gradient":{"stops":[[t,"#hex"|[r,g,b,a]|stored Color]],"angle":deg,"scale":%,"style":"linear|radial|angle|reflected|diamond","reverse":bool,"opacityStops":[[t,0..1]]?,"midpoints":[0..1]?,"offset":[x,y]?,"dither":bool?,"align":bool?}}|{"pattern":name}|null (no fill)?,"stroke":{"width":px,"color":"#rrggbb"|fill,"opacity":0..100,"align":"inside|center|outside","cap":"butt|round|square","join":"miter|round|bevel","miterLimit":n,"dashes":[multiples of width],"dashOffset":n}|null? (merged into the current stroke),"name":str?} → shape.info
shape.info	Shape Layer Info	{"layer":id?} → {layer,name,kind,path,fill,stroke,live,bounds:[x,y,w,h]}
shape.presets.edit	Edit Shape Presets	{"action":"rename|delete|move|newGroup|renameGroup|deleteGroup","preset":name|[names] (rename/delete/move),"group":name? (narrows the lookup; the group for renameGroup/deleteGroup),"name":str (rename: new name; newGroup/renameGroup: group name),"to":group (move),"index":n? (move)}
shape.presets.importCsh	Import Shapes	{"path":str (.csh) | "data":str (base64),"group":str?} → {group,count,names}; appends a uniquely named group, never replaces existing presets
shape.presets.list	Shape Presets	{} → {groups:[{name,shapes:[{name,id?,subpaths}]}]}
shape.presets.new	New Shape Preset	{"name":str="Shape","id":str? (an imported library's opaque identity),"group":name?,"path":{…path}|"M x y L …" (preset path language)|"work"|saved path name? (default: work path, active shape layer or vector mask)}
shape.presets.place	Place Custom Shape	{"preset":name,"group":name?,"rect":[x,y,w,h]? (default: centred, half the canvas),"keepAspect":bool=true,"fill":…?=foreground,"stroke":…?,"name":str?,"addTo":layerId?,"op":"combine|subtract|intersect|exclude"?} → shape.info (Custom Shape tool / Shapes panel; fill and stroke as in shape.create)
shape.presets.reset	Restore Default Shapes	{"append":bool=false}
shape.rasterize	Rasterize Shape	{"layer":id?}
```

## slice（7）

```text
slice.delete	Delete Slice	{"slice":id | "number":n | "slices":[id…]} → {deleted}
slice.divide	Divide Slice…	{"slice":id | "number":n,"horizontal":n=1 (slices down),"vertical":n=1 (slices across); at most 10000 parts} → {slices}
slice.fromGuides	Slices From Guides	{} (replaces every slice by the grid of the canvas guides) → {slices}
slice.list	List Slices	{} → {slices:[{number,id,origin:auto|layer|user,name,rect:[x,y,w,h],kind,layer,url,alt,…,pieces?:[{number,name,rect}] (a stored slice's visible parts; number null when wholly covered)}], locked}
slice.new	Slice Tool	{"rect":[x,y,w,h] | "x","y","width","height", plus Slice Options ("name","kind":"image|noImage|table","url","target","message","alt","cellText","cellTextIsHtml","background":"none|#rrggbb")?} → {slice, number}
slice.promote	Promote	{"slice":id | "number":n} (auto or layer-based → user slice) → {slice}
slice.set	Slice Options…	{"slice":id | "number":n (an auto slice is promoted), "name"?,"kind":"image|noImage|table"?,"url"?,"target"?,"message"?,"alt"?,"cellText"?,"cellTextIsHtml"?,"horizontalAlign":0..4?,"verticalAlign":0..4?,"background":"none|#rrggbb"?,"outsets":[t,l,b,r]? (layer slices),"rect":[x,y,w,h]? (move/resize; a layer slice becomes a user slice)} → the slice
```

## style（7）

```text
style.presets.apply	Apply Style	{"preset":name,"group":name?,"layers":[ids]?|"layer":id? (default: the selected layers),"add":bool=false (⇧-click: add to the existing effects)} → {layers,style}
style.presets.edit	Edit Style Presets	{"action":"rename|delete|move|newGroup|renameGroup|deleteGroup","preset":name|[names] (rename/delete/move),"group":name? (narrows the lookup; the group for renameGroup/deleteGroup),"name":str (rename: new name; newGroup/renameGroup: group name),"to":group (move),"index":n? (move)}
style.presets.exportAsl	Export Styles…	{"group":name? (only that group),"styles":[names]? (only these),"path":".asl file"? (else the bytes come back as base64 `data`)} → {count, bytes, patterns, warnings, path|data}
style.presets.importAsl	Import Styles…	{"path":".asl file"?,"data":base64 bytes?,"group":string?=file name (a built-in group's name becomes "<name> 2": built-ins are never replaced),"replace":bool=true (replace a group of the same name)} → {group, imported, count, patterns (ids added to the pattern library), warnings}
style.presets.list	Style Presets	{} → {groups:[{name,presets:[{name,effects,blend,fillOpacity,opacity}]}]}
style.presets.new	New Style…	{"name":str="Style","group":name?,"layer":id?,"includeEffects":bool=true,"includeBlending":bool=true,"effects":[[kind, params]]? (explicit list, e.g. the Layer Style dialog's pending state; overrides includeEffects),"blend":str?,"fillOpacity":0..100?,"opacity":0..100? (override the layer's blending options)}
style.presets.reset	Restore Default Styles	{"append":bool=false}
```

## swatches（12）

```text
swatches.add	New Swatch…	{"color":"#rrggbb"|{"model":"rgb|hsb|cmyk|lab|gray","values":[rgb 0..255 | hue°,s%,b% | c%,m%,y%,k% | L,a,b | k%]}?=foreground,"name":str?="Color Swatch N","group":name?=first (created when missing),"index":n?=end,"kind":"process|global|spot"="process"} → {name,group,index}
swatches.delete	Delete Swatch	{"swatch":name (or "index":n across all groups),"group":name? (narrows the name lookup); "swatch" may be a list of names} → {deleted:[names]}
swatches.deleteGroup	Delete Swatch Group	{"group":name,"keepSwatches":bool=false (move its swatches into the group above)} → {group,deleted|kept}
swatches.export	Export Swatches…	{"format":"aco|act|ase"?=from path, else aco,"path":file? (else the bytes come back as base64 `data`),"group":name? (only that group),"swatches":[names]? (only these)} → {format,count,bytes,warnings,path|data}
swatches.import	Import Swatches…	{"path":".aco, .act or .ase file"?,"data":base64 bytes?,"format":"aco|act|ase"? (detected; an .act by its .act path or its 768/772-byte length),"mode":"append|replace"="append","group":str?=file name (the group for ungrouped colours)} → {format,mode,groups,count,warnings}
swatches.list	Swatches	{} → {groups:[{name,swatches:[{name,model,values,hex,kind?}]}],count}. values are in Color Picker units; hex is the colour in the RGB working space.
swatches.move	Move Swatch	{"swatch":name (or "index":n across all groups),"group":name? (narrows the name lookup),"to":group?=its own group,"position":n?=end} → {group,position}
swatches.newGroup	New Swatch Group…	{"name":str="Group" (made unique),"swatches":[names]? (moved into the new group)} → {group,moved}
swatches.rename	Rename Swatch…	{"swatch":name (or "index":n across all groups),"group":name? (narrows the name lookup),"name":str} → {name}
swatches.renameGroup	Rename Swatch Group…	{"group":name,"name":str} → {group}
swatches.reset	Reset Swatches	{"append":bool=false (add the defaults instead of replacing the library)} → {groups,count}
swatches.use	Use Swatch	{"swatch":name (or "index":n across all groups),"group":name? (narrows the name lookup),"target":"foreground|background"="foreground"} → {swatch,target,hex}. CMYK, Lab and gray swatches are converted to the RGB working space with colour management.
```

## timeline（7）

```text
timeline.create	Create Video Timeline	{duration?:30, fps?:30} → {timeline}
timeline.delete	Delete Timeline	{} → {timeline:null}
timeline.info	Timeline Info	{} → {timeline}
timeline.nextFrame	Next Frame	{} → {timeline}
timeline.previousFrame	Previous Frame	{} → {timeline}
timeline.setFrame	Go to Frame	{frame} → {timeline}
timeline.setProps	Timeline Settings	{fps?, duration?, workStart?, workEnd?} → {timeline}
```

## tool（5）

```text
tool.presets.edit	Edit Tool Presets	{"action":"rename|delete","preset":name|[names],"name":str (rename)}
tool.presets.list	Tool Presets	{"tool":name? (Current Tool Only)} → {presets:[{name,tool}]}
tool.presets.new	New Tool Preset…	{"name":str?=tool (at most 255 characters; a taken name gets " 2", " 3"…),"tool":name ("crop" for Crop presets),"options":{…}? (opaque; "brush" defaults to the current brush for painting tools),"includeColor":bool=false}
tool.presets.reset	Reset Tool Presets	{}
tool.presets.select	Select Tool Preset	{"preset":name} → {name,tool,options} (applies "brush" and "foreground"; the shell switches tool and options)
```

## tools（13）

```text
tools.decreaseBrushHardness	Decrease Brush Hardness	{}
tools.decreaseBrushSize	Decrease Brush Size	{}
tools.defaultColors	Default Foreground and Background Colors	{}
tools.firstBrush	First Brush	{}
tools.increaseBrushHardness	Increase Brush Hardness	{}
tools.increaseBrushSize	Increase Brush Size	{}
tools.lastBrush	Last Brush	{}
tools.nextBrush	Next Brush	{}
tools.previousBrush	Previous Brush	{}
tools.rotateBrush	Rotate Brush Tip	{"degrees":-360..360 (positive anticlockwise; ← / → while painting send 1, ⇧ 15)}
tools.setBrush	Set Brush	{"preset":name?,"reset":bool?,…BrushSettings fields (camelCase, deep-merged; pose.overrideTiltX/Y:bool; pose.overrideTilt:legacy combined alias; opacity floors at 0.01)}
tools.setColors	Set Colors	{"foreground":"#rrggbb"|[r,g,b,a?]?,"background":same?,"foregroundCmyk":[c,m,y,k]? (inks 0..1 the foreground was picked as: a CMYK document is filled with exactly these),"backgroundCmyk":same?}
tools.swapColors	Switch Foreground and Background Colors	{}
```

## type（99）

```text
type.antiAlias.crisp	Crisp	{"layer":id? or "layers":[id,…]? (default selected Type layers)}
type.antiAlias.none	None	{"layer":id? or "layers":[id,…]? (default selected Type layers)}
type.antiAlias.sharp	Sharp	{"layer":id? or "layers":[id,…]? (default selected Type layers)}
type.antiAlias.smooth	Smooth	{"layer":id? or "layers":[id,…]? (default selected Type layers)}
type.antiAlias.strong	Strong	{"layer":id? or "layers":[id,…]? (default selected Type layers)}
type.antiAlias.windows	Windows	{"layer":id? or "layers":[id,…]? (default selected Type layers)}
type.antiAlias.windowsLcd	Windows LCD	{"layer":id? or "layers":[id,…]? (default selected Type layers)}
type.attachToPath	Type on a Path	{"layer":id? (default active Type layer),"shape":layerId? (a shape layer; default the work path),"subpath":index=0,"start":px=0 (offset along the path),"at":[x,y]? (instead of "start": begin where the path passes nearest this document point, as a Type tool click does),"flip":bool=false (run along the path the other way, on its other side)}
type.caret	Type Caret	{"layer":id?, "index":char (0..=length; empty text is 0)} → {"index","line","segment":[[x,y],[x,y]]} caret segment in document pixels, for rotated and vertical type too
type.characterStyle.apply	Apply Character Style	{"id":u32|0|null (0/null: None / Basic Paragraph),"clearOverrides":bool=false (Alt-click),"layer":id? | "layers":[id]? (default: the selected type layers),"range":[startChar,endChar]? (one layer; default all text)}
type.characterStyle.clearOverride	Clear Override	{"layer":id? | "layers":[id]? (default: the selected type layers),"range":[startChar,endChar]? (one layer; default all text)}
type.characterStyle.delete	Delete Style	{"id":u32} (text keeps its formatting as overrides)
type.characterStyle.duplicate	Duplicate Style	{"id":u32}
type.characterStyle.list	List Character Styles	{"layer":id? | "layers":[id]? (default: the selected type layers),"range":[startChar,endChar]? (one layer; default all text)} → {"styles":[{"id","name",attributes,"resolved"}],"current":{"character":id|null (mixed),"characterOverride":bool,"paragraph":id|null,"paragraphOverride":bool}}
type.characterStyle.new	New Character Style	{"name":str?,"attrs":{model fields as in type.info ("size_pt":36,"font_family":"Inter","align":"Center",…) or Character/Paragraph panel keys as in type.setStyle ("size":36,"font":"Inter","color":"#rrggbb","align":"center",…)}?,"fromSelection":bool=true (start from the targeted text's formatting),"apply":bool=false,"layer":id? | "layers":[id]? (default: the selected type layers),"range":[startChar,endChar]? (one layer; default all text)} → {"id","name"}
type.characterStyle.redefine	Redefine Character Style	{"id":u32? (default: the targeted text's style),"layer":id? | "layers":[id]? (default: the selected type layers),"range":[startChar,endChar]? (one layer; default all text)} (the style takes the formatting of the start of the targeted text)
type.characterStyle.rename	Rename Style	{"id":u32,"name":str}
type.characterStyle.set	Character Style Options	{"id":u32 (paragraph: 0 = Basic Paragraph),"name":str?,"attrs":{model fields as in type.info ("size_pt":36,"font_family":"Inter","align":"Center",…) or Character/Paragraph panel keys as in type.setStyle ("size":36,"font":"Inter","color":"#rrggbb","align":"center",…)},"replace":bool=false (drop attributes not given),"clear":[field]?} (text using the style updates, overrides kept)
type.convertToParagraphText	Convert to Paragraph Text	{"layer":id?}
type.convertToPointText	Convert to Point Text	{"layer":id?}
type.convertToShape	Convert to Shape	{"layer":id?}
type.create	New Type Layer	{"x":px,"y":px (baseline anchor of point text),"text":str,"box":[x,y,w,h]? (paragraph text),"name":str?,"align":"left|center|right|justify…"?,"orientation":"horizontal|vertical"="horizontal", …character keys: "font","size":pt=12,"color",…}
type.createSelection	Type Mask	{"layer":id|name? (a type layer whose glyphs become the selection),"removeLayer":bool=false (delete that layer in the same step: the Type Mask tools' temporary text),"operation":"new|add|subtract|intersect"="new","antialias":"none|sharp|crisp|strong|smooth"?, …without "layer", type.create's keys: "text","x","y" or "box","orientation","font","size","align",…}
type.createWorkPath	Create Work Path	{"layer":id?}
type.decreaseSize	Decrease Type Size	{"layer":id?,"range":[startChar,endChar]? (default all),"by":pt? (as the layer appears)}
type.decreaseSizeMore	Decrease Type Size by 10	{"layer":id?,"range":[startChar,endChar]? (default all),"by":pt? (as the layer appears)}
type.detachFromPath	Release Type from Path	{"layer":id?}
type.edit	Edit Type	{"layer":id?,"text":str? (replace all, styles kept),"replace":{"start":char,"end":char,"text":str}?,"runs":[{"start":char,"end":char,…character keys}]?,"box":[x,y,w,h]? (to paragraph text),"point":[x,y]? (to point text),"move":[dx,dy]?,"transform":[a,b,c,d,e,f]?,"antialias":"none|sharp|crisp|strong|smooth"?,"name":str?,"kerning":1/1000em|"metrics"|"optical"|"off"? (with "range":[startChar,endChar]?, default all),"kernPair":{"at":caretChar,"by":1/1000em}? (Alt+←/→: the pair before the caret becomes manual, its current kerning + by)}
type.fillPath	Area Type	{"layer":id? (default active Type layer),"shape":layerId? (a shape layer; default the work path)} → the text wraps inside the path's closed subpaths, holes included
type.font.favorite	Add to Favorites	{"family":str,"on":bool?=toggle} → family, favorite, favorites
type.font.library	Font Library	{} → favorites
type.fonts	List Fonts	{"family":str? (faces of one family)}
type.hitTest	Hit-Test Type	{"layer":id?, "x":px, "y":px} → {"layer","index":char,"line","inside":bool}. No layer: the topmost visible type layer whose laid-out text or rendered pixels contain the point (same order as the Type tool); a miss is an error. With a layer, index is the nearest caret even when inside is false
type.increaseSize	Increase Type Size	{"layer":id?,"range":[startChar,endChar]? (default all),"by":pt? (as the layer appears)}
type.increaseSizeMore	Increase Type Size by 10	{"layer":id?,"range":[startChar,endChar]? (default all),"by":pt? (as the layer appears)}
type.info	Type Layer Info	{"layer":id?} → text, runs/paragraphs (char offsets + styles), shape, transform, laid-out lines (text space px), bounds
type.insertText	Insert Glyph	{"layer":id?,"text":str,"at":char? (default: end of text),"range":[startChar,endChar]? (replaced),"label":str?} → {"layer","caret"}
type.loadDefaultTypeStyles	Load Default Type Styles	{"layer":id? or "layers":[id,…]? (default selected Type layers)}
type.navigate	Navigate Type	{"layer":id?, "index":char, "move":"wordPrev|wordNext|linePrev|lineNext|lineStart|lineEnd|start|end", "x":px?} → {"index"}. Words are alphanumeric runs. x is the document x to keep across linePrev/lineNext (a caret segment's x); omitted uses the caret's own column. Empty text returns index 0
type.openType.contextualAlternates	Contextual Alternates	{"layer":id? or "layers":[id,…]? (default selected Type layers),"on":bool? (default: toggle representative),"range":[startChar,endChar]? (single layer; default all)}
type.openType.discretionaryLigatures	Discretionary Ligatures	{"layer":id? or "layers":[id,…]? (default selected Type layers),"on":bool? (default: toggle representative),"range":[startChar,endChar]? (single layer; default all)}
type.openType.fractions	Fractions	{"layer":id? or "layers":[id,…]? (default selected Type layers),"on":bool? (default: toggle representative),"range":[startChar,endChar]? (single layer; default all)}
type.openType.numerals.default	Default	{"layer":id? or "layers":[id,…]? (default selected Type layers)}
type.openType.numerals.lining	Lining	{"layer":id? or "layers":[id,…]? (default selected Type layers)}
type.openType.numerals.oldstyle	Oldstyle	{"layer":id? or "layers":[id,…]? (default selected Type layers)}
type.openType.numerals.proportional	Proportional	{"layer":id? or "layers":[id,…]? (default selected Type layers)}
type.openType.numerals.proportionalLining	Proportional Lining	{"layer":id? or "layers":[id,…]? (default selected Type layers)}
type.openType.numerals.proportionalOldstyle	Proportional Oldstyle	{"layer":id? or "layers":[id,…]? (default selected Type layers)}
type.openType.numerals.tabular	Tabular	{"layer":id? or "layers":[id,…]? (default selected Type layers)}
type.openType.numerals.tabularLining	Tabular Lining	{"layer":id? or "layers":[id,…]? (default selected Type layers)}
type.openType.numerals.tabularOldstyle	Tabular Oldstyle	{"layer":id? or "layers":[id,…]? (default selected Type layers)}
type.openType.oldstyle	Oldstyle	{"layer":id? or "layers":[id,…]? (default selected Type layers),"on":bool? (default: toggle representative),"range":[startChar,endChar]? (single layer; default all)}
type.openType.ordinals	Ordinals	{"layer":id? or "layers":[id,…]? (default selected Type layers),"on":bool? (default: toggle representative),"range":[startChar,endChar]? (single layer; default all)}
type.openType.ornaments	Ornaments	{"layer":id? or "layers":[id,…]? (default selected Type layers),"on":bool? (default: toggle representative),"range":[startChar,endChar]? (single layer; default all)}
type.openType.standardLigatures	Standard Ligatures	{"layer":id? or "layers":[id,…]? (default selected Type layers),"on":bool? (default: toggle representative),"range":[startChar,endChar]? (single layer; default all)}
type.openType.stylisticAlternates	Stylistic Alternates	{"layer":id? or "layers":[id,…]? (default selected Type layers),"on":bool? (default: toggle representative),"range":[startChar,endChar]? (single layer; default all)}
type.openType.stylisticSets.set1	Set 1	{"layer":id? or "layers":[id,…]? (default selected Type layers),"on":bool? (default: toggle representative),"range":[startChar,endChar]? (single layer; default all)}
type.openType.stylisticSets.set10	Set 10	{"layer":id? or "layers":[id,…]? (default selected Type layers),"on":bool? (default: toggle representative),"range":[startChar,endChar]? (single layer; default all)}
type.openType.stylisticSets.set11	Set 11	{"layer":id? or "layers":[id,…]? (default selected Type layers),"on":bool? (default: toggle representative),"range":[startChar,endChar]? (single layer; default all)}
type.openType.stylisticSets.set12	Set 12	{"layer":id? or "layers":[id,…]? (default selected Type layers),"on":bool? (default: toggle representative),"range":[startChar,endChar]? (single layer; default all)}
type.openType.stylisticSets.set13	Set 13	{"layer":id? or "layers":[id,…]? (default selected Type layers),"on":bool? (default: toggle representative),"range":[startChar,endChar]? (single layer; default all)}
type.openType.stylisticSets.set14	Set 14	{"layer":id? or "layers":[id,…]? (default selected Type layers),"on":bool? (default: toggle representative),"range":[startChar,endChar]? (single layer; default all)}
type.openType.stylisticSets.set15	Set 15	{"layer":id? or "layers":[id,…]? (default selected Type layers),"on":bool? (default: toggle representative),"range":[startChar,endChar]? (single layer; default all)}
type.openType.stylisticSets.set16	Set 16	{"layer":id? or "layers":[id,…]? (default selected Type layers),"on":bool? (default: toggle representative),"range":[startChar,endChar]? (single layer; default all)}
type.openType.stylisticSets.set17	Set 17	{"layer":id? or "layers":[id,…]? (default selected Type layers),"on":bool? (default: toggle representative),"range":[startChar,endChar]? (single layer; default all)}
type.openType.stylisticSets.set18	Set 18	{"layer":id? or "layers":[id,…]? (default selected Type layers),"on":bool? (default: toggle representative),"range":[startChar,endChar]? (single layer; default all)}
type.openType.stylisticSets.set19	Set 19	{"layer":id? or "layers":[id,…]? (default selected Type layers),"on":bool? (default: toggle representative),"range":[startChar,endChar]? (single layer; default all)}
type.openType.stylisticSets.set2	Set 2	{"layer":id? or "layers":[id,…]? (default selected Type layers),"on":bool? (default: toggle representative),"range":[startChar,endChar]? (single layer; default all)}
type.openType.stylisticSets.set20	Set 20	{"layer":id? or "layers":[id,…]? (default selected Type layers),"on":bool? (default: toggle representative),"range":[startChar,endChar]? (single layer; default all)}
type.openType.stylisticSets.set3	Set 3	{"layer":id? or "layers":[id,…]? (default selected Type layers),"on":bool? (default: toggle representative),"range":[startChar,endChar]? (single layer; default all)}
type.openType.stylisticSets.set4	Set 4	{"layer":id? or "layers":[id,…]? (default selected Type layers),"on":bool? (default: toggle representative),"range":[startChar,endChar]? (single layer; default all)}
type.openType.stylisticSets.set5	Set 5	{"layer":id? or "layers":[id,…]? (default selected Type layers),"on":bool? (default: toggle representative),"range":[startChar,endChar]? (single layer; default all)}
type.openType.stylisticSets.set6	Set 6	{"layer":id? or "layers":[id,…]? (default selected Type layers),"on":bool? (default: toggle representative),"range":[startChar,endChar]? (single layer; default all)}
type.openType.stylisticSets.set7	Set 7	{"layer":id? or "layers":[id,…]? (default selected Type layers),"on":bool? (default: toggle representative),"range":[startChar,endChar]? (single layer; default all)}
type.openType.stylisticSets.set8	Set 8	{"layer":id? or "layers":[id,…]? (default selected Type layers),"on":bool? (default: toggle representative),"range":[startChar,endChar]? (single layer; default all)}
type.openType.stylisticSets.set9	Set 9	{"layer":id? or "layers":[id,…]? (default selected Type layers),"on":bool? (default: toggle representative),"range":[startChar,endChar]? (single layer; default all)}
type.openType.swash	Swash	{"layer":id? or "layers":[id,…]? (default selected Type layers),"on":bool? (default: toggle representative),"range":[startChar,endChar]? (single layer; default all)}
type.openType.titlingAlternates	Titling Alternates	{"layer":id? or "layers":[id,…]? (default selected Type layers),"on":bool? (default: toggle representative),"range":[startChar,endChar]? (single layer; default all)}
type.orientation.horizontal	Horizontal	{"layer":id? or "layers":[id,…]? (default selected Type layers)}
type.orientation.vertical	Vertical	{"layer":id? or "layers":[id,…]? (default selected Type layers)}
type.paragraphStyle.apply	Apply Paragraph Style	{"id":u32|0|null (0/null: None / Basic Paragraph),"clearOverrides":bool=false (Alt-click),"layer":id? | "layers":[id]? (default: the selected type layers),"range":[startChar,endChar]? (one layer; default all text)}
type.paragraphStyle.clearOverride	Clear Override	{"layer":id? | "layers":[id]? (default: the selected type layers),"range":[startChar,endChar]? (one layer; default all text)}
type.paragraphStyle.delete	Delete Style	{"id":u32} (text keeps its formatting as overrides)
type.paragraphStyle.duplicate	Duplicate Style	{"id":u32}
type.paragraphStyle.list	List Paragraph Styles	{"layer":id? | "layers":[id]? (default: the selected type layers),"range":[startChar,endChar]? (one layer; default all text)} → {"styles":[{"id","name",attributes,"resolved"}],"current":{"character":id|null (mixed),"characterOverride":bool,"paragraph":id|null,"paragraphOverride":bool}}
type.paragraphStyle.new	New Paragraph Style	{"name":str?,"attrs":{model fields as in type.info ("size_pt":36,"font_family":"Inter","align":"Center",…) or Character/Paragraph panel keys as in type.setStyle ("size":36,"font":"Inter","color":"#rrggbb","align":"center",…)}?,"fromSelection":bool=true (start from the targeted text's formatting),"apply":bool=false,"layer":id? | "layers":[id]? (default: the selected type layers),"range":[startChar,endChar]? (one layer; default all text)} → {"id","name"}
type.paragraphStyle.redefine	Redefine Paragraph Style	{"id":u32? (default: the targeted text's style),"layer":id? | "layers":[id]? (default: the selected type layers),"range":[startChar,endChar]? (one layer; default all text)} (the style takes the formatting of the start of the targeted text)
type.paragraphStyle.rename	Rename Style	{"id":u32,"name":str}
type.paragraphStyle.set	Paragraph Style Options	{"id":u32 (paragraph: 0 = Basic Paragraph),"name":str?,"attrs":{model fields as in type.info ("size_pt":36,"font_family":"Inter","align":"Center",…) or Character/Paragraph panel keys as in type.setStyle ("size":36,"font":"Inter","color":"#rrggbb","align":"center",…)},"replace":bool=false (drop attributes not given),"clear":[field]?} (text using the style updates, overrides kept)
type.pasteLoremIpsum	Paste Lorem Ipsum	{"layer":id?,"at":char? (default end),"new":bool=false (new paragraph text layer)}
type.rasterize	Rasterize Type	{"layer":id?}
type.rasterizeTypeLayer	Rasterize Type Layer	{"layer":id?}
type.replaceAllMissingFonts	Replace All Missing Fonts	{} (with the default family)
type.resolveMissingFonts	Resolve Missing Fonts…	{"map":{"Missing Family":"Installed Family"}?} (no map: list the missing families)
type.saveDefaultTypeStyles	Save Default Type Styles	{} (from the active type layer; new type layers start from them)
type.setPathPlacement	Set Path Placement	{"layer":id? (default active Type layer),"start":finite f32 arc-length pixels?,"end":finite f32 arc-length pixels|null?,"flip":bool?}. Updates existing path text; omitted values are preserved. Offsets are text-space pixels in the current travel direction. end:null clears the limit and restores legacy placement; an explicit end must be at least start. Position-locked and fully locked layers are rejected.
type.setStyle	Set Type Style	{"layer":id? or "layers":[id,…]? (default selected Type layers),"range":[startChar,endChar]? (single layer; default all),"metricsAsShown":bool=false (size/leading/leadingBy include each layer's transform scale), "font":str,"fontStyle":str,"weight":100..900,"italic":bool,"size":0.1..=1296 pt,"color":"#rrggbb"|[r,g,b,a],"tracking":-1000..=10000 (1/1000 em),"leading":pt|"auto","baselineShift":pt,"horizontalScale":%,"verticalScale":%,"underline":bool,"strikethrough":bool,"fauxBold":bool,"fauxItalic":bool,"kerning":1/1000em (manual, after each character)|"metrics"|"optical"|"off","caps":"normal|small|all","baseline":"normal|superscript|subscript","ligatures":bool,"discretionaryLigatures":bool,"features":{"ss01":1},"variations":{"wght":650},"language":str, relative steps from each character's own value: "leadingBy":pt (auto leading starts from its laid-out value; result 0.01..=5000),"baselineShiftBy":pt (result -5000..=5000),"trackingBy":1/1000 em (result -1000..=10000), paragraph keys: "align":"left|center|right|justify|justifyCenter|justifyRight|justifyAll","firstLineIndent":pt,"startIndent":pt,"endIndent":pt,"spaceBefore":pt,"spaceAfter":pt,"autoLeading":%,"direction":"auto|ltr|rtl","hyphenate":bool}
type.updateAllTextLayers	Update All Text Layers	{}
type.warpText	Warp Text…	{"layer":id? or "layers":[id,…]? (default selected Type layers),"style":"none|arc|arcLower|arcUpper|arch|bulge|shellLower|shellUpper|flag|wave|fish|rise|fisheye|inflate|squeeze|twist"="arc","orientation":"horizontal|vertical"="horizontal","bend":-100..100=50,"horizontalDistortion":-100..100=0,"verticalDistortion":-100..100=0}
```

## updates（1）

```text
updates.status	Update Check Status	{}
```

## variables（1）

```text
variables.list	List Variables	{} → {defs,dataSets,active}
```

## view（31）

```text
view.clearCanvasGuides	Clear Canvas Guides	{}
view.clearGuides	Clear Guides	{}
view.clearSelectedArtboardGuides	Clear Selected Artboard Guides	{} (guides inside the active artboard)
view.clearSlices	Clear Slices	{} (deletes every user and layer-based slice) → {cleared}
view.colorSamplers.add	Add Color Sampler	{"x":f64,"y":f64,"size":1|3|5|11|31|51|101|"point"=1 (the Sample Size the readout averages over, in document pixels)} → the new point {index, number, position, rgb, cmyk}; errors at the 10-point limit or off the canvas
view.colorSamplers.clear	Clear Color Samplers	{}
view.colorSamplers.delete	Delete Color Sampler	{"index":n}
view.colorSamplers.list	Color Samplers	{"size":1|3|5|11|31|51|101|"point"=1 (Sample Size: each readout is the size × size average of document pixels around the point)} → {max, size, samplers:[{index, number, position, rgb, cmyk}]}
view.colorSamplers.move	Move Color Sampler	{"index":n,"x":f64,"y":f64,"size":1|3|5|11|31|51|101|"point"=1}
view.deleteGuide	Delete Guide	{"orientation":"horizontal|vertical","index":n}
view.editGuide	Edit Guide	{"orientation":"horizontal|vertical","index":n,"newOrientation":"horizontal|vertical"?,"position":px or "<number><unit>"?,"color":name or "#rrggbb"?} (Edit Selected Guides: units and colours as for view.newGuide; % is of the new orientation's extent; whatever is left out stays as it was)
view.gamutWarning	Gamut Warning	{"on":bool=toggle,"threshold":deltaE=4,"profile":"<proof profile override>"}
view.layerMask	View Layer Mask	{"layer":id?,"mode":"off"|"gray"|"overlay"|"toggleGray"|"toggleOverlay"="toggleGray","mask":"layer"|"filter"="layer" (filter: a smart object's filter mask)} (gray: the mask alone, ⌥-click its thumbnail; overlay: red rubylith over the composite, ⇧⌥-click or `\`; view state, not an undo step; painting while shown paints the mask)
view.lockSlices	Lock Slices	{"on":bool? (default: toggle)} → {locked}
view.moveGuide	Move Guide	{"orientation":"horizontal|vertical","index":n,"position":px or "<number><unit>","toOrientation":"horizontal|vertical"?} (units as for view.newGuide; toOrientation turns the guide, its position then on the new axis)
view.newGuide	New Guide…	{"orientation":"horizontal|vertical","position":px or "<number><unit>","color":"lightBlue|lightRed|green|mediumBlue|yellow|magenta|cyan|lightGray|black" or "#rrggbb"?} (units px, in, cm, mm, pt, pc or %; % is of the width for a vertical guide, the height for a horizontal one; without a color the guide uses the guide colour in Preferences)
view.newGuideLayout	New Guide Layout…	{"columns":n=0,"width":len?,"gutter":len=0,"rows":n=0,"height":len?,"rowGutter":len=gutter,"margin":len|[top,left,bottom,right]=0,"centerColumns":bool=false,"clearExisting":bool=false,"target":"document|selectedArtboards"="document"} (len: pixels, or text with px, in, cm, mm, pt, pc or % as typed in Photoshop, e.g. "1 cm"; % is of the target's width for columns, gutters and left/right margins, its height for rows and top/bottom margins)
view.newGuidesFromShape	New Guides From Shape	{"layer":id?}
view.proofColors	Proof Colors	{"on":bool=toggle}
view.proofSetup	Proof Setup…	{"profile":"working-cmyk|srgb|display-p3|adobe-rgb-compat|prophoto-compat|linear-srgb|rec2020|gray-gamma-2.2|sgray|lab-d50|coated-cmyk" (or a path to an .icc file)="working-cmyk","intent":"perceptual|relative|saturation|absolute"="relative","bpc":bool=true,"simulatePaper":bool=false}
view.proofSetup.colorBlindnessDeuteranopia	Color Blindness - Deuteranopia-type	{} (sets the proof and turns Proof Colors on)
view.proofSetup.colorBlindnessProtanopia	Color Blindness - Protanopia-type	{} (sets the proof and turns Proof Colors on)
view.proofSetup.legacyMacintoshRgb	Legacy Macintosh RGB (Gamma 1.8)	{} (sets the proof and turns Proof Colors on)
view.proofSetup.workingBlackPlate	Working Black Plate	{} (sets the proof and turns Proof Colors on)
view.proofSetup.workingCmyPlate	Working CMY Plates	{} (sets the proof and turns Proof Colors on)
view.proofSetup.workingCyanPlate	Working Cyan Plate	{} (sets the proof and turns Proof Colors on)
view.proofSetup.workingMagentaPlate	Working Magenta Plate	{} (sets the proof and turns Proof Colors on)
view.proofSetup.workingYellowPlate	Working Yellow Plate	{} (sets the proof and turns Proof Colors on)
view.resetRulerOrigin	Reset Ruler Origin	{} (zero point back at the image's top-left)
view.setRulerOrigin	Set Ruler Origin	{"x":px,"y":px} (the rulers' zero point in document pixels; the rulers and Info panel measure from it)
view.thirtyTwoBitPreviewOptions	32-bit Preview Options…	{"method":"exposureGamma|highlightCompression"="exposureGamma","exposure":-20..20=0,"gamma":0.1..9.99=1}
```


