# 小游戏研发模板与示例

SKILL.md Process 第 2、6 步引用的填好示例。产出时对照格式，不要自由发挥结构。示例以"水果切切乐"（切割类）为例。

## GDD 章节示例

### 概览

```markdown
类型：反应切割类（单指操作，单局 60–90 秒）
核心循环：水果抛起 → 玩家滑动切割 → 得分/连击 → 难度递增 → 结算
目标用户：碎片时间休闲玩家，无学习成本
```

### 实体定义（节选）

```markdown
| 实体 | 属性 | 状态流转 |
| ---- | ---- | ---- |
| Fruit | type(西瓜/香蕉/…)、size、velocity、scoreValue | spawned → flying → sliced / missed |
| Bomb | triggerRadius | spawned → flying → exploded(切中) / missed |
| Combo | count、windowMs(800) | idle → counting → reset |
```

合格句："玩家切中 Bomb 时本局立即结束，由 Bomb.ts onSliced() 调用 gameOver('bomb')"。
噪声句："炸弹要给人紧张感"——无法映射到开发动作，删。

### 资产需求清单（节选）

```markdown
程序资产：Fruit 抛物线运动、切割轨迹检测、Combo 计时器
素材资产：
- 水果整图 ×6 + 切面图 ×6（西瓜/香蕉/苹果/橙子/柠檬/草莓，切面为拆分图）
- 炸弹 ×1、背景 ×1、刀光粒子 ×1
- 音频：BGM ×1、切割 ×3（普通/连击/炸弹）、结算 ×1
```

## 关卡方案五章示例

```markdown
gameType: fruit-slice
数据结构:
  level: { id, timeLimitSec, spawnIntervalMs, fruitMix: { type: weight }, bombRate, targetScore }
生产方式: 算法生成（参数化：spawnInterval 随关卡递减、bombRate 随关卡递增）
验证方式: 行为模拟——bot 按 90 分位反应速度游玩，每关模拟 200 局，
  通过标准：通关率落在 55%–75% 区间；区间外重新生成
难度曲线:
  Tier1(1-8关): spawnInterval 1200ms, bombRate 0
  Tier2(9-16关): spawnInterval 900ms, bombRate 0.03
  Tier3(17-24关): spawnInterval 700ms, bombRate 0.06
  Tier4(25-30关): spawnInterval 550ms, bombRate 0.10
```

## 生成模式速查表

| 内容类型 | 生产方式 | 有效性判定 | 生成模式 |
| ---- | ---- | ---- | ---- |
| 布局类（消除/配对/数独） | 算法生成 | 算法保证有解，或毫秒级 BFS/DFS 验证有解路径 | 判定快 → 运行时生成 |
| 反应/动作类（切割/跳跃/打地鼠） | 算法生成 | 行为模拟统计通过率（bot 按目标分位反应速度游玩） | 判定快 → 运行时生成；模拟耗时 → 离线预生成 |
| 内容类（词库/题库/对话） | LLM 生成 | AI 校验合理性，低质标记重生 | 判定快 → 生成即验证 |
| 视觉类（找不同/找茬） | 文生图生成 | 行为模拟统计通过率 | 判定耗时 → 离线预生成 + 校验择优 |
| 叙事/剧情类 | LLM 生成 | 不可自动判定 | 人工抽检 + 发布后数据回收（不承诺全自动） |

## 宿主接入清单

- [ ] 数据查询：实现统一查询函数，游戏侧只声明要什么（第 N 关配置），不关心来源
- [ ] 生命周期：onReady / onGameStart / onGameEnd 回调已按模板封装
- [ ] 双向事件：上行 emit('app:event', name, payload)；下行 on('host:event', handler)
- [ ] 构建：独立构建产物 + 入口注册，宿主零代码改动
