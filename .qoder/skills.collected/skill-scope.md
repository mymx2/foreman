---
name: skill-scope
description: Project-level skill scoping for skills. When working on a specific project, prioritize the listed domain skills over similar-sounding alternatives to avoid skill misselection.
trigger: always_on
alwaysApply: true
---

# Skill Scope

This rule maps each project to its primary skill set so the agent picks the right skill instead of a similar-sounding one.

## How to use

1. Identify which project the current task belongs to (by file path, repo, or user context).
2. Load skills from that project's scope first.
3. If the task is cross-domain (e.g., designing an API consumed by frontend), load from both relevant scopes.

---

## rbz-artifact (设计与创意)

Tech: 文档生成、视觉设计、演示文稿

### Documents

- `pdf`, `docx`, `pptx`, `xlsx`

### Visual & Creative

- `canvas-design`
- `frontend-design`
- `algorithmic-art`
- `theme-factory`
- `brand-guidelines`

### Communication

- `internal-comms`
- `doc-coauthoring`
- `web-artifacts-builder`
- `webapp-testing`
- `skill-creator`
- `slack-gif-creator`

---

## rbz-client (Vue 3 + Vite 前端)

Tech: Vue 3 Composition API, TypeScript, Vite, UnoCSS, Pinia

### Primary skills (pick these first)

- `vue`
- `vue-best-practices`
- `pinia`
- `vite`
- `unocss`

### Vue 生态最佳实践

- `vue-router-best-practices`
- `vue-pinia-best-practices`
- `vueuse-functions`
- `vue-jsx-best-practices`
- `vue-debug-guides`
- `vue-testing-best-practices`
- `create-adaptable-composable`

### Build & Package

- `pnpm`
- `tsdown`
- `turborepo`
- `vitepress`
- `slidev`

### Testing & Quality

- `vitest`
- `playwright-cli`
- `web-design-guidelines`

---

## app-mini (微信小程序)

Tech: 微信小程序, Skyline 渲染引擎, glass-easel

### Primary skills (pick these first)

- `wechat-miniprogram`
- `glass-easel`
- `tdesign-miniprogram`

### Skyline 渲染引擎

- `skyline-overview`
- `skyline-config`
- `skyline-components`
- `skyline-route`
- `skyline-worklet`
- `skyline-scroll-api`
- `skyline-wxss`

---

## app-android (Android 原生)

Tech: Kotlin, Jetpack Compose, Android SDK

### Primary skills (pick these first)

- `android-cli`
- `jetpack-compose-m3`
- `adaptive`
- `styles`
- `base`

### Build & Migration

- `agp-9-upgrade`
- `migrate-xml-views-to-jetpack-compose`
- `play-billing-library-version-upgrade`
- `camera1-to-camerax`

### Performance & Profiling

- `r8-analyzer`
- `perfetto-sql`
- `perfetto-trace-analysis`

### Device AI & Platform

- `appfunctions`
- `engage-sdk-integration`
- `verified-email`

### System & UI

- `edge-to-edge`
- `navigation-3`
- `display-glasses-with-jetpack-compose-glimmer`
- `display-ai-glasses-with-jetpack-compose-glimmer`

### Testing

- `testing-setup`

---

## rbz-admin (Kotlin + Spring Boot 后端)

Tech: Kotlin, Spring Boot, Gradle KTS, PostgreSQL

### Primary skills (pick these first)

- `kotlin-spring`
- `gradle-kotlin-dsl-doctor`
- `kotlin-spring-proxy-compatibility`
- `kotlin-idiomatic-refactorer-spring-aware`
- `java-kotlin-migration-assistant`

### Persistence & Data

- `jpa-spring-data-kotlin-mapper`
- `jdbc-dsl`
- `design-postgres-tables`
- `redis-core`
- `schema-migration-planner`
- `transaction-consistency-designer`

### API & Serialization

- `spring-mvc-webflux-api-builder`
- `jackson-kotlin-serialization-specialist`
- `error-model-validation-architect`
- `domain-decomposition-api-design-advisor`

### Security & Config

- `spring-security-configurator-auditor`
- `configuration-properties-profiles-kotlin-safe`
- `spring-context-di-reasoning`

### Operations

- `observability-integrator`
- `performance-concurrency-advisor`
- `stacktrace-log-triage`
- `production-incident-responder`
- `integration-resilience-engineer`

### Quality

- `spring-kotlin-code-review`
- `test-suite-builder`
- `dependency-conflict-resolver`
- `project-context-ingestion`
- `upgrade-breaking-change-navigator`

---

## rbz-devops (DevOps / 运维)

- `tencentos-expert`
