import { defineConfig } from 'vite-plus'

const ignorePatterns = [
  'pnpm-workspace.yaml',
  '**/*-lock.*',
  '__*',
  '.agents',
  '.qoder',
  'references',
  'projects',
  'skills',
]

export default defineConfig({
  lint: {
    options: {
      typeAware: true,
      typeCheck: true,
    },
    ignorePatterns: [...ignorePatterns],
  },
  fmt: {
    singleQuote: true,
    semi: false,
    arrowParens: 'avoid',
    printWidth: 120,
    ignorePatterns: [...ignorePatterns],
  },
  staged: {
    '*': 'vp check --no-error-on-unmatched-pattern',
  },
  test: {
    exclude: ['**/node_modules/**', '**/dist/**', 'projects/**'],
  },
})
