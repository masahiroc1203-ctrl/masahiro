// npm run lint で使う ESLint 設定（未使用変数・未定義の名前などを検出）
const browser = Object.fromEntries(
  [
    'window', 'document', 'navigator', 'localStorage', 'location', 'history', 'performance',
    'requestAnimationFrame', 'cancelAnimationFrame', 'setTimeout', 'clearTimeout', 'setInterval', 'clearInterval',
    'IntersectionObserver', 'URL', 'URLSearchParams', 'Blob', 'SpeechSynthesisUtterance', 'structuredClone', 'console',
  ].map((k) => [k, 'readonly']),
);
const worker = Object.fromEntries(['self', 'caches', 'fetch', 'Response', 'URL'].map((k) => [k, 'readonly']));
const node = Object.fromEntries(['process', 'console', 'URL'].map((k) => [k, 'readonly']));

const rules = {
  'no-unused-vars': 'error',
  'no-undef': 'error',
  'no-unreachable': 'error',
  'no-dupe-keys': 'error',
  eqeqeq: ['error', 'smart'],
};

export default [
  { ignores: ['node_modules/', '.screenshots/', 'android/'] },
  { files: ['js/**/*.js', 'dev/**/*.js'], languageOptions: { ecmaVersion: 2024, sourceType: 'module', globals: browser }, rules },
  { files: ['sw.js'], languageOptions: { ecmaVersion: 2024, sourceType: 'script', globals: worker }, rules },
  { files: ['tests/**/*.js', 'eslint.config.js'], languageOptions: { ecmaVersion: 2024, sourceType: 'module', globals: node }, rules },
  // smoke.mjs は page.evaluate() の中でブラウザ側のコードも書くので両方
  { files: ['scripts/**/*.mjs'], languageOptions: { ecmaVersion: 2024, sourceType: 'module', globals: { ...node, ...browser } }, rules },
];
