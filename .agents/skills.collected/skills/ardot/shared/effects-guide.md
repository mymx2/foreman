# 复合效果配方

基础效果类型与参数格式见 `shared/design-rules.md` §效果。本文只给复合配方，用于需要材质、金属、拟态等视觉层次时。

通用注意：

- `showShadowBehindNode` 在节点半透明时设 `false`，不透明时设 `true`。
- 阴影的 alpha 与半径要成组变化，别只调一个。
- 颜色按实际品牌色替换 `r/g/b`，本文示例只是结构。

---

## 毛玻璃（Glassmorphism）

触发词：glass、backdrop-blur、frosted、毛玻璃。

`BACKGROUND_BLUR` + 半透明 SOLID 填充（opacity < 0.5）+ 内侧高光 + 落差阴影 + 1px 白色描边（15–30% 不透明度）。

```javascript
effects: [
  {type: "BACKGROUND_BLUR", blurType: "NORMAL", radius: 16, visible: true, boundVariables: {}},
  {type: "DROP_SHADOW", color: {r:0, g:0, b:0, a:0.15}, offset: {x:0, y:8}, radius: 24, visible: true, blendMode: "NORMAL", showShadowBehindNode: false, boundVariables: {}},
  {type: "INNER_SHADOW", color: {r:1, g:1, b:1, a:0.2}, offset: {x:0, y:1}, radius: 2, visible: true, blendMode: "NORMAL", boundVariables: {}}
]
fills: [{type: "SOLID", color: {r:1, g:1, b:1}, opacity: 0.2, visible: true, blendMode: "NORMAL"}]
strokes: [{type: "SOLID", color: {r:1, g:1, b:1}, opacity: 0.25, visible: true, blendMode: "NORMAL"}]
strokeWeight: 1
```

---

## 金属（Metallic）

触发词：metallic、chrome、金属、铬。

用 5 个明暗交替的渐变停点（暗 → 亮 → 暗 → 亮 → 暗），45° 角。金属感来自停点之间的对比度与交替频率，不来自单个颜色。

```javascript
fills: [{
  type: "GRADIENT_LINEAR",
  gradientStops: [
    {color: {r:0.745, g:0.765, b:0.788, a:1}, position: 0},
    {color: {r:0.941, g:0.941, b:0.941, a:1}, position: 0.25},
    {color: {r:0.557, g:0.573, b:0.596, a:1}, position: 0.50},
    {color: {r:0.910, g:0.910, b:0.910, a:1}, position: 0.75},
    {color: {r:0.424, g:0.439, b:0.471, a:1}, position: 1}
  ],
  gradientTransform: [[0.707, 0.707, 0], [-0.707, 0.707, 0]],
  opacity: 1, visible: true, blendMode: "NORMAL"
}]
effects: [
  {type: "INNER_SHADOW", color: {r:0, g:0, b:0, a:0.3}, offset: {x:0, y:2}, radius: 4, visible: true, blendMode: "NORMAL", boundVariables: {}},
  {type: "INNER_SHADOW", color: {r:1, g:1, b:1, a:0.2}, offset: {x:0, y:-1}, radius: 2, visible: true, blendMode: "NORMAL", boundVariables: {}}
]
```

---

## 新拟态（Neumorphism）

触发词：neumorphism、soft-ui、dual-shadow、新拟态。

背景与元素同色（如 `#E0E5EC`），靠一明一暗两个方向相反的阴影制造凸起或凹陷。背景不能用纯白或纯黑。

```javascript
// 凸起
effects: [
  {type: "DROP_SHADOW", color: {r:1, g:1, b:1, a:0.8}, offset: {x:-6, y:-6}, radius: 8, visible: true, blendMode: "NORMAL", showShadowBehindNode: true, boundVariables: {}},
  {type: "DROP_SHADOW", color: {r:0.639, g:0.690, b:0.780, a:0.5}, offset: {x:6, y:6}, radius: 8, visible: true, blendMode: "NORMAL", showShadowBehindNode: true, boundVariables: {}}
]

// 凹陷
effects: [
  {type: "INNER_SHADOW", color: {r:0.639, g:0.690, b:0.780, a:0.5}, offset: {x:4, y:4}, radius: 8, visible: true, blendMode: "NORMAL", boundVariables: {}},
  {type: "INNER_SHADOW", color: {r:1, g:1, b:1, a:0.8}, offset: {x:-4, y:-4}, radius: 8, visible: true, blendMode: "NORMAL", boundVariables: {}}
]
```

---

## 虹彩渐变（Iridescent）

触发词：iridescent、holographic、虹彩、全息。

`GRADIENT_ANGULAR` 上均匀分布 6–8 个色相停点，再叠一层 `SCREEN` 混合的 `GRADIENT_RADIAL` 提亮中心。底色不能太暗。

```javascript
fills: [
  {type: "GRADIENT_ANGULAR",
    gradientStops: [
      {color: {r:1, g:0.2, b:0.4, a:1}, position: 0},
      {color: {r:1, g:0.6, b:0.2, a:1}, position: 0.17},
      {color: {r:0.8, g:1, b:0.2, a:1}, position: 0.33},
      {color: {r:0.2, g:1, b:0.6, a:1}, position: 0.50},
      {color: {r:0.2, g:0.6, b:1, a:1}, position: 0.67},
      {color: {r:0.6, g:0.2, b:1, a:1}, position: 0.83},
      {color: {r:1, g:0.2, b:0.4, a:1}, position: 1}
    ],
    gradientTransform: [[1, 0, 0], [0, 1, 0]],
    opacity: 1, visible: true, blendMode: "NORMAL"},
  {type: "GRADIENT_RADIAL",
    gradientStops: [
      {color: {r:1, g:1, b:1, a:0.4}, position: 0},
      {color: {r:1, g:1, b:1, a:0}, position: 1}
    ],
    gradientTransform: [[1, 0, 0], [0, 1, 0]],
    opacity: 1, visible: true, blendMode: "SCREEN"}
]
```

---

## 不支持的效果

| 效果 | 原因 | 替代做法 |
|---|---|---|
| 噪点纹理 | NOISE kernel 未实现 | IMAGE 填充 + OVERLAY 混合 |
| 液态玻璃 | GLASS kernel 未实现 | BACKGROUND_BLUR + 渐变 + INNER_SHADOW 近似 |
| 纹理叠加 | TEXTURE kernel 未实现 | IMAGE 填充 + 混合模式 |
| 裁剪路径 / 不规则形状 | 无 CLIP_PATH | 不支持 |
