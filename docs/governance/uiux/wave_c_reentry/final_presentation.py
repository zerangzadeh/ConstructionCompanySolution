"""Keep result amounts primary and calculation inputs available in disclosure."""
from pathlib import Path

root = Path(__file__).resolve().parents[4]
p = root / "templates/payroll/run_detail.html"
s = p.read_text(encoding="utf-8")
old = '<div class="mt-4 overflow-x-auto"><table'
assert s.count(old) == 1
s = s.replace(old, '<p class="mt-3 text-sm">ناخالص: {{ result.gross_amount|rial }} · کسور: {{ result.deduction_amount|rial }}</p><details class="mt-4"><summary class="cursor-pointer text-sm font-bold">جزئیات اقلام و محاسبه</summary><div class="mt-3 overflow-x-auto"><table')
assert s.count('</table></div></article>') == 1
s = s.replace('</table></div></article>', '</table></div></details></article>')
p.write_text(s, encoding="utf-8")
