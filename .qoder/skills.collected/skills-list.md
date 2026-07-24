# 技能清单 (Skills Catalog)

按领域组织的技能清单。每个领域包含安装命令和技能索引。

> 安装时请用 `--skill` 显式指定需要的技能，禁止直接安装整个仓库。
> `-g` 为全局安装；`--agent codex` 为项目级安装（根目录执行）；`--agent openclaw` 在 `.qoder/skills.collected/` 目录下执行。

---

## 全局技能（-g 全局安装，所有项目可用）

### 安装命令

```bash
# mymx2/skills
vpx skills add mymx2/skills \
  --skill find-skills \
  --skill skills-cli \
  --skill writing-guidelines \
  --skill writing-review \
  -g -y

# openai/skills -- deprecated
vpx skills add openai/skills --skill screenshot -g -y

# anthropics/skills
vpx skills add anthropics/skills --skill skill-creator -g -y
```

### 技能索引

| 技能 | 来源 | 一句话 |
|------|------|--------|
| `find-skills` | mymx2/skills | 技能发现与安装助手 |
| `skills-cli` | mymx2/skills | Skills CLI 完整使用指南 |
| `writing-guidelines` | mymx2/skills | 技术文档写作规范 |
| `writing-review` | mymx2/skills | 写作规范合规审查 |
| `screenshot` | openai/skills | 桌面截图工具 |
| `skill-creator` | anthropics/skills | Agent Skill 创建与优化 |

---

## 项目技能（--agent codex 项目级安装）

### 安装命令

```bash
# addyosmani/agent-skills
vpx skills add addyosmani/agent-skills \
  --skill api-and-interface-design \
  --skill browser-testing-with-devtools \
  --skill ci-cd-and-automation \
  --skill code-review-and-quality \
  --skill code-simplification \
  --skill context-engineering \
  --skill debugging-and-error-recovery \
  --skill deprecation-and-migration \
  --skill documentation-and-adrs \
  --skill doubt-driven-development \
  --skill frontend-ui-engineering \
  --skill git-workflow-and-versioning \
  --skill idea-refine \
  --skill incremental-implementation \
  --skill interview-me \
  --skill observability-and-instrumentation \
  --skill performance-optimization \
  --skill planning-and-task-breakdown \
  --skill security-and-hardening \
  --skill shipping-and-launch \
  --skill source-driven-development \
  --skill spec-driven-development \
  --skill test-driven-development \
  --skill using-agent-skills \
  --agent codex -p -y

# openai/plugins — GitHub 协作
vpx skills add https://github.com/openai/plugins/tree/main/plugins/github/skills \
  --skill gh-address-comments \
  --skill gh-fix-ci \
  --skill yeet \
  --skill github \
  --agent codex -p -y

# mymx2/skills
vpx skills add mymx2/skills --skill design-cli --agent codex -p -y
```

### 技能索引

| 技能 | 来源 | 一句话 |
|------|------|--------|
| `api-and-interface-design` | addyosmani/agent-skills | API 与接口设计 |
| `browser-testing-with-devtools` | addyosmani/agent-skills | Chrome DevTools 浏览器测试 |
| `ci-cd-and-automation` | addyosmani/agent-skills | CI/CD 流水线自动化 |
| `code-review-and-quality` | addyosmani/agent-skills | 多维代码审查 |
| `code-simplification` | addyosmani/agent-skills | 代码简化与去复杂化 |
| `context-engineering` | addyosmani/agent-skills | Agent 上下文优化 |
| `debugging-and-error-recovery` | addyosmani/agent-skills | 系统化调试与错误恢复 |
| `deprecation-and-migration` | addyosmani/agent-skills | 废弃与迁移管理 |
| `documentation-and-adrs` | addyosmani/agent-skills | 文档与架构决策记录 |
| `doubt-driven-development` | addyosmani/agent-skills | 对抗性决策审查 |
| `frontend-ui-engineering` | addyosmani/agent-skills | 生产级 UI 工程 |
| `git-workflow-and-versioning` | addyosmani/agent-skills | Git 工作流与版本管理 |
| `idea-refine` | addyosmani/agent-skills | 创意精炼与结构化 |
| `incremental-implementation` | addyosmani/agent-skills | 增量实现与验证 |
| `interview-me` | addyosmani/agent-skills | 需求访谈与澄清 |
| `observability-and-instrumentation` | addyosmani/agent-skills | 可观测性与埋点 |
| `performance-optimization` | addyosmani/agent-skills | 性能优化 |
| `planning-and-task-breakdown` | addyosmani/agent-skills | 任务拆解与规划 |
| `security-and-hardening` | addyosmani/agent-skills | 安全加固 |
| `shipping-and-launch` | addyosmani/agent-skills | 发布与上线 |
| `source-driven-development` | addyosmani/agent-skills | 官方文档驱动开发 |
| `spec-driven-development` | addyosmani/agent-skills | 规格驱动开发 |
| `test-driven-development` | addyosmani/agent-skills | 测试驱动开发 |
| `using-agent-skills` | addyosmani/agent-skills | Agent 技能发现与使用 |
| `gh-address-comments` | openai/plugins | PR 评审评论处理 |
| `gh-fix-ci` | openai/plugins | GitHub Actions CI 修复 |
| `github` | openai/plugins | GitHub 仓库/PR/Issue 导航与摘要 |
| `yeet` | openai/plugins | 一键 stage + commit + push + PR |
| `design-cli` | mymx2/skills | DESIGN.md 规范与 CLI 工具（token 定义、lint、diff、export） |

---

## rbz-artifact — 设计与创意

Tech: 文档生成、视觉设计、演示文稿

### 安装命令

```bash
# anthropics/skills
vpx skills add anthropics/skills \
  --skill algorithmic-art \
  --skill brand-guidelines \
  --skill canvas-design \
  --skill doc-coauthoring \
  --skill docx \
  --skill frontend-design \
  --skill internal-comms \
  --skill pdf \
  --skill pptx \
  --skill skill-creator \
  --skill slack-gif-creator \
  --skill theme-factory \
  --skill web-artifacts-builder \
  --skill webapp-testing \
  --skill xlsx \
  --agent openclaw -p -y
```

### 技能索引

| 技能 | 来源 | 一句话 |
|------|------|--------|
| `docx` | anthropics/skills | Word 文档生成与读取 |
| `xlsx` | anthropics/skills | Excel 表格解析与导出 |
| `pptx` | anthropics/skills | PowerPoint 幻灯片生成 |
| `pdf` | anthropics/skills | PDF 渲染与处理 |
| `canvas-design` | anthropics/skills | Canvas 动态图形与海报 |
| `frontend-design` | anthropics/skills | 高保真 UI 设计还原 |
| `algorithmic-art` | anthropics/skills | 算法生成艺术 |
| `theme-factory` | anthropics/skills | 主题工厂与 Design Tokens |
| `brand-guidelines` | anthropics/skills | 品牌色彩与排版规范 |
| `internal-comms` | anthropics/skills | 内部沟通文档模板 |
| `doc-coauthoring` | anthropics/skills | 协同文档编写 |
| `web-artifacts-builder` | anthropics/skills | Web 构建产物沙盒 |
| `webapp-testing` | anthropics/skills | Web 应用测试策略 |
| `slack-gif-creator` | anthropics/skills | Slack 动图生成 |
| `skill-creator` | anthropics/skills | Agent Skill 创建与优化 |

---

## rbz-client — Vue 3 + Vite 前端

Tech: Vue 3 Composition API, TypeScript, Vite, UnoCSS, Pinia

### 安装命令

```bash
# antfu/skills
vpx skills add antfu/skills \
  --skill vue \
  --skill vueuse-functions \
  --skill pinia \
  --skill vite \
  --skill vitepress \
  --skill vitest \
  --skill unocss \
  --skill slidev \
  --skill tsdown \
  --skill turborepo \
  --skill pnpm \
  --skill web-design-guidelines \
  --agent openclaw -p -y

# vuejs-ai/skills
vpx skills add vuejs-ai/skills \
  --skill vue-best-practices \
  --skill vue-router-best-practices \
  --skill vue-pinia-best-practices \
  --skill vue-testing-best-practices \
  --skill vue-jsx-best-practices \
  --skill vue-debug-guides \
  --skill create-adaptable-composable \
  --agent openclaw -p -y

# microsoft/playwright-cli
vpx skills add microsoft/playwright-cli --skill playwright-cli --agent openclaw -p -y
```

### 技能索引

| 技能 | 来源 | 一句话 |
|------|------|--------|
| `vue` | antfu/skills | Vue 3 核心框架 |
| `vue-best-practices` | vuejs-ai/skills | Composition API + TypeScript 最佳实践 |
| `pinia` | antfu/skills | Vue 状态管理 |
| `vite` | antfu/skills | Vite 构建配置与插件 |
| `unocss` | antfu/skills | 即时原子化 CSS 引擎 |
| `vue-router-best-practices` | vuejs-ai/skills | Vue Router 4 导航守卫 |
| `vue-pinia-best-practices` | vuejs-ai/skills | Pinia Store 模式 |
| `vueuse-functions` | antfu/skills | VueUse 组合式工具 |
| `vue-jsx-best-practices` | vuejs-ai/skills | Vue 中的 JSX 语法 |
| `vue-debug-guides` | vuejs-ai/skills | Vue 3 调试与错误处理 |
| `vue-testing-best-practices` | vuejs-ai/skills | 组件测试与 E2E |
| `create-adaptable-composable` | vuejs-ai/skills | MaybeRef 可复用组合式 |
| `vitest` | antfu/skills | 基于 Vite 的单元测试 |
| `playwright-cli` | microsoft/playwright-cli | 浏览器自动化测试 |
| `pnpm` | antfu/skills | 包管理与 Workspace |
| `tsdown` | antfu/skills | TypeScript 库打包 |
| `turborepo` | antfu/skills | Monorepo 构建系统 |
| `vitepress` | antfu/skills | 静态文档站生成 |
| `slidev` | antfu/skills | Markdown 幻灯片 |
| `web-design-guidelines` | antfu/skills | Web 设计与无障碍规范 |

---

## rbz-mini — 微信小程序

Tech: 微信小程序, Skyline 渲染引擎, glass-easel

### 安装命令

```bash
# wechat-miniprogram/skyline-skills
vpx skills add wechat-miniprogram/skyline-skills \
  --skill skyline-overview \
  --skill skyline-config \
  --skill skyline-components \
  --skill skyline-route \
  --skill skyline-worklet \
  --skill skyline-scroll-api \
  --skill skyline-wxss \
  --agent openclaw -p -y

# wechat-miniprogram/glass-easel
vpx skills add https://github.com/wechat-miniprogram/glass-easel/blob/master/glass-easel-skills/glass-easel --agent openclaw -p -y
```

> `wechat-miniprogram` 和 `tdesign-miniprogram` 来自 CodeBuddy，无 skills.sh 安装命令。

### 技能索引

| 技能 | 来源 | 一句话 |
|------|------|--------|
| `wechat-miniprogram` | CodeBuddy | 微信小程序框架（模板、组件、API、云开发） |
| `glass-easel` | wechat-miniprogram/glass-easel | 新一代组件运行框架 |
| `tdesign-miniprogram` | CodeBuddy | TDesign 小程序组件库（60+ 组件） |
| `skyline-overview` | wechat-miniprogram/skyline-skills | Skyline 架构与迁移概览 |
| `skyline-config` | wechat-miniprogram/skyline-skills | app.json / page.json 配置 |
| `skyline-components` | wechat-miniprogram/skyline-skills | 高性能原生组件 |
| `skyline-route` | wechat-miniprogram/skyline-skills | 自定义路由与页面转场 |
| `skyline-worklet` | wechat-miniprogram/skyline-skills | UI 线程动画 |
| `skyline-scroll-api` | wechat-miniprogram/skyline-skills | 滚动控制与下拉刷新 |
| `skyline-wxss` | wechat-miniprogram/skyline-skills | WXSS/CSS 支持范围 |

---

## rbz-android — Android 原生

Tech: Kotlin, Jetpack Compose, Android SDK

### 安装命令

```bash
# android/skills
vpx skills add android/skills \
  --skill android-cli \
  --skill agp-9-upgrade \
  --skill adaptive \
  --skill appfunctions \
  --skill base \
  --skill camera1-to-camerax \
  --skill display-ai-glasses-with-jetpack-compose-glimmer \
  --skill display-glasses-with-jetpack-compose-glimmer \
  --skill edge-to-edge \
  --skill engage-sdk-integration \
  --skill jetpack-compose-m3 \
  --skill migrate-xml-views-to-jetpack-compose \
  --skill navigation-3 \
  --skill perfetto-sql \
  --skill perfetto-trace-analysis \
  --skill play-billing-library-version-upgrade \
  --skill r8-analyzer \
  --skill styles \
  --skill testing-setup \
  --skill verified-email \
  --agent openclaw -p -y
```

### 技能索引

| 技能 | 来源 | 一句话 |
|------|------|--------|
| `android-cli` | android/skills | Android CLI：SDK 设置、模拟器、部署、文档搜索 |
| `jetpack-compose-m3` | android/skills | Jetpack Compose + Material 3 最佳实践 |
| `adaptive` | android/skills | 自适应布局：Window Size Classes 与响应式 UI |
| `styles` | android/skills | Material 3 主题、样式与 Design Tokens |
| `base` | android/skills | Android 项目基础规范 |
| `agp-9-upgrade` | android/skills | Android Gradle Plugin 9 升级与迁移 |
| `migrate-xml-views-to-jetpack-compose` | android/skills | XML Views → Jetpack Compose 迁移 |
| `play-billing-library-version-upgrade` | android/skills | Google Play Billing Library 版本升级 |
| `camera1-to-camerax` | android/skills | Camera1 → CameraX 迁移 |
| `r8-analyzer` | android/skills | R8/ProGuard 配置分析与审计 |
| `perfetto-sql` | android/skills | Perfetto 性能追踪 SQL 查询 |
| `perfetto-trace-analysis` | android/skills | Perfetto Trace 文件分析 |
| `edge-to-edge` | android/skills | 全屏显示 / Edge-to-Edge 适配 |
| `navigation-3` | android/skills | Navigation 3 设置与迁移 |
| `appfunctions` | android/skills | Device AI AppFunctions 集成 |
| `engage-sdk-integration` | android/skills | Engage SDK 集成 |
| `verified-email` | android/skills | 邮箱验证功能集成 |
| `display-glasses-with-jetpack-compose-glimmer` | android/skills | XR 显示眼镜 + Compose Glimmer |
| `display-ai-glasses-with-jetpack-compose-glimmer` | android/skills | AI 显示眼镜 + Compose Glimmer |
| `testing-setup` | android/skills | Android 测试环境配置 |

---

## rbz-admin — Kotlin + Spring Boot 后端

Tech: Kotlin, Spring Boot, Gradle KTS, PostgreSQL

### 安装命令

```bash
# jetbrains/skills
vpx skills add jetbrains/skills \
  --skill ci-cd-containerization-advisor \
  --skill configuration-properties-profiles-kotlin-safe \
  --skill dependency-conflict-resolver \
  --skill domain-decomposition-api-design-advisor \
  --skill error-model-validation-architect \
  --skill gradle-kotlin-dsl-doctor \
  --skill integration-resilience-engineer \
  --skill jackson-kotlin-serialization-specialist \
  --skill java-kotlin-migration-assistant \
  --skill jpa-spring-data-kotlin-mapper \
  --skill kotlin-idiomatic-refactorer-spring-aware \
  --skill kotlin-spring-proxy-compatibility \
  --skill observability-integrator \
  --skill performance-concurrency-advisor \
  --skill production-incident-responder \
  --skill project-context-ingestion \
  --skill schema-migration-planner \
  --skill spring-context-di-reasoning \
  --skill spring-kotlin-code-review \
  --skill spring-mvc-webflux-api-builder \
  --skill spring-security-configurator-auditor \
  --skill stacktrace-log-triage \
  --skill test-suite-builder \
  --skill transaction-consistency-designer \
  --skill upgrade-breaking-change-navigator \
  --agent openclaw -p -y

# mymx2/skills
vpx skills add mymx2/skills --skill kotlin-spring --agent openclaw -p -y

# timescale/pg-aiguide
vpx skills add timescale/pg-aiguide --skill design-postgres-tables --agent openclaw -p -y

# redis/agent-skills — Redis
vpx skills add redis/agent-skills --skill redis-core --agent openclaw -p -y
```

### 技能索引

| 技能 | 来源 | 一句话 |
|------|------|--------|
| `kotlin-spring` | mymx2/skills | Spring Boot 全家桶（25 个子技能） |
| `gradle-kotlin-dsl-doctor` | jetbrains/skills | Gradle 构建调试与修复 |
| `kotlin-spring-proxy-compatibility` | jetbrains/skills | @Transactional/@Cacheable 代理兼容 |
| `kotlin-idiomatic-refactorer-spring-aware` | jetbrains/skills | Kotlin 代码清理（Spring 安全） |
| `java-kotlin-migration-assistant` | jetbrains/skills | Java → Kotlin 迁移 |
| `jpa-spring-data-kotlin-mapper` | jetbrains/skills | JPA 实体、Repository、N+1 |
| `jdbc-dsl` | 本地提供 | JDBC DSL 查询构建（用户自定义提供） |
| `design-postgres-tables` | timescale/pg-aiguide | PostgreSQL 表设计、索引、JSONB |
| `redis-core` | redis/agent-skills | Redis 数据建模：数据结构选择与键名规范 |
| `schema-migration-planner` | jetbrains/skills | Flyway/Liquibase 零停机迁移 |
| `transaction-consistency-designer` | jetbrains/skills | 事务边界、幂等性、锁策略 |
| `spring-mvc-webflux-api-builder` | jetbrains/skills | REST/WebFlux API 构建 |
| `jackson-kotlin-serialization-specialist` | jetbrains/skills | Jackson + Kotlin 序列化 |
| `error-model-validation-architect` | jetbrains/skills | 统一错误模型与校验 |
| `domain-decomposition-api-design-advisor` | jetbrains/skills | 限界上下文与 API 契约 |
| `spring-security-configurator-auditor` | jetbrains/skills | Spring Security 配置审计 |
| `configuration-properties-profiles-kotlin-safe` | jetbrains/skills | 配置属性绑定与 Profile |
| `spring-context-di-reasoning` | jetbrains/skills | 上下文启动失败诊断 |
| `observability-integrator` | jetbrains/skills | 日志/指标/链路追踪 |
| `performance-concurrency-advisor` | jetbrains/skills | 性能与并发分析 |
| `stacktrace-log-triage` | jetbrains/skills | 堆栈与日志分诊 |
| `production-incident-responder` | jetbrains/skills | 生产事故响应 |
| `integration-resilience-engineer` | jetbrains/skills | 重试/熔断/DLQ 韧性设计 |
| `spring-kotlin-code-review` | jetbrains/skills | Kotlin + Spring 代码审查 |
| `test-suite-builder` | jetbrains/skills | 分层测试设计 |
| `dependency-conflict-resolver` | jetbrains/skills | Gradle 依赖冲突 |
| `project-context-ingestion` | jetbrains/skills | 项目上下文采集 |
| `upgrade-breaking-change-navigator` | jetbrains/skills | 大版本升级导航 |
| `ci-cd-containerization-advisor` | jetbrains/skills | CI/CD 与容器化 |

---

## 其他技能

### 安装命令

```bash
# tw93/Waza
vpx skills add tw93/Waza \
  --skill think \
  --skill ui \
  --skill check \
  --skill hunt \
  --skill learn \
  --skill read \
  --skill write \
  --skill health \
  --agent openclaw -p -y

# anthropics/claude-plugins-official
vpx skills add anthropics/claude-plugins-official --skill claude-md-improver --agent openclaw -p -y

# dgreenheck/webgpu-claude-skill — WebGPU 3D
vpx skills add dgreenheck/webgpu-claude-skill --skill webgpu-threejs-tsl --agent openclaw -p -y
```

> `tencentos-expert` 为手动收集，无 skills.sh 安装命令。
> `kdocs-skill`（金山文档）通过 git clone 安装到 `skills.disabled/`。
> [飞书文档技能](https://www.skills.sh/larksuite/cli) 尚未收集。
> 其余未作说明部分均来自个人创建或收集

### 技能索引

| 技能 | 来源 | 一句话 |
|------|------|--------|
| `think` | tw93/Waza | 方案设计与决策 |
| `ui` | tw93/Waza | 生产级 UI 设计 |
| `check` | tw93/Waza | 代码审查与发布检查 |
| `hunt` | tw93/Waza | 根因诊断与修复 |
| `learn` | tw93/Waza | 深度研究与成稿 |
| `read` | tw93/Waza | URL/PDF 阅读与摘要 |
| `write` | tw93/Waza | 中英文润色与去 AI 味 |
| `health` | tw93/Waza | 工程健康度审计 |
| `claude-md-improver` | anthropics/claude-plugins-official | CLAUDE.md 审计与优化 |
| `webgpu-threejs-tsl` | dgreenheck/webgpu-claude-skill | Three.js WebGPU + TSL 着色器 |
| `tencentos-expert` | 手动收集 | TencentOS 服务器运维诊断 |
| `sql-parser-cst` | 个人创建 | 解析 SQL 生成 CST 语法树，提取表结构与 SQL 元信息 |
