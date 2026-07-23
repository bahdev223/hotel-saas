import re

path = 'apps/comptabilite/views/operations.py'
content = open(path, 'r', encoding='utf-8').read()

redirect = "return redirect('comptabilite:operations')"

content = re.sub(
    r'(messages\.error\(request, f"Erreur: \{str\(e\)\}"\))\n(\s*\n)+(    context = \{)',
    lambda m: m.group(1) + '\n            ' + redirect + '\n\n' + m.group(3),
    content
)

open(path, 'w', encoding='utf-8').write(content)
print("Done")
