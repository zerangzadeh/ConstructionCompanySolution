/** @type {import('tailwindcss').Config} */
module.exports = {
  content: {
    relative: true,
    files: [
      './templates/**/*.html',
      './apps/*/templates/**/*.html',
      './apps/*/static/**/*.js',
      './apps/**/*.py',
      './core/**/*.py',
      '!./apps/**/static/**/vendor/**',
      '!./apps/**/migrations/**',
      '!./apps/**/tests/**',
      '!./apps/**/tests.py',
      '!./apps/**/test_*.py',
      '!./core/**/tests/**',
      '!./core/**/migrations/**',
      '!./core/**/tests.py',
      '!./core/**/test_*.py',
    ],
  },
  // Utilities in conditional branches, Python widgets and JS are full literals.
  // Generated erp-badge / chart state classes belong to existing custom CSS.
  safelist: [],
  theme: { extend: {} },
  plugins: [],
};
