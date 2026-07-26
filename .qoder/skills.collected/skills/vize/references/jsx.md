# Vize JSX/TSX 编写完整参考

## 目录

- [基本模式](#基本模式)
- [VDOM vs Vapor 切换](#vdom-vs-vapor-切换)
- [Scoped Styles](#scoped-styles)
- [已知限制](#已知限制)

## 基本模式

```tsx
type CounterProps = { label: string; start?: number };
type CounterEmits = { change: [value: number] };

const Counter = ({ label, start = 0 }: CounterProps, { emit }: Ctx<CounterEmits>) => {
  const count = ref(start);
  return (
    <section class="counter">
      <p>{label}: {count.value}</p>
      <button type="button" onClick={() => emit("change", count.value + 1)}>+</button>
    </section>
  );
};
```

**要点：**
- Props 是第一参数的类型，Emits/Slots 是 `Ctx<Emits, Slots>` 第二参数
- 默认值用解构默认值，不需要 `withDefaults`
- 组件名从绑定名 `const Counter = ...` 或函数声明 `function Card()` 获取

## VDOM vs Vapor 切换

```tsx
// 全局默认：compiler.jsxMode 配置
// 单组件覆盖：
const Fast = () => {
  "use vue:vapor";  // 强制 Vapor
  return <div class="fast" />;
};

const Classic = () => {
  "use vue:vdom";   // 强制 VDOM
  return <div class="classic" />;
};
```

优先级：per-component 指令 > `compiler.jsxMode` 配置 > 内置默认 `"vdom"`。

> `defineConfig` 也可从 `@vizejs/vite-plugin` 导入（向后兼容），但推荐使用 `import { defineConfig } from "vize"` 统一入口。

## Scoped Styles

```tsx
const Card = ({ title }: { title: string }) => (
  <article class="card">
    <h2>{title}</h2>
    <style scoped>{`
      .card { border: 1px solid currentColor; padding: 12px; }
    `}</style>
  </article>
);
```

## 已知限制

- HMR 未接入独立 `.jsx`/`.tsx` 文件（修改后需刷新）
- `v-bind()` CSS 变量在 JSX scoped style 中不支持
- JSX 类型检查需 `typeChecker.jsxTypecheck: true` 开启（默认关闭，避免误判 React 文件）
- JSX 指令诊断：`"use vue:vdomx"` 等拼写错误会报编译错误（不会静默忽略），同一组件中的冲突指令（`"use vue:vapor"` + `"use vue:vdom"`）同样报错
