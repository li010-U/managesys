with open('D:\\managesys\\frontend\\src\\views\\room\\RackView.vue', 'r', encoding='utf-8-sig') as f:
    content = f.read()

# Replace function rackMatches with empty stub  
content = content.replace(
    'function rackMatches(rack: RackInfo): boolean {\n',
    'const rackMatches = (rack: RackInfo): boolean => false;\n'
)

content = content.replace(
    'function rackTooltip(rack: RackInfo): string {\n',
    'const rackTooltip = (rack: RackInfo): string => "";\n'
)

with open('D:\\managesys\\frontend\\src\\views\\room\\RackView.vue', 'w', encoding='utf-8') as f:
    f.write(content)

# Also fix the remaining function bodies that have opening braces
import re

# Some functions might have been replaced but still have bodies
# Let me check what we have
lines = content.split('\\n')
count = 0
for fn in ['function getSlotStyle', 'function rackMatches', 'function rackTooltip', 'function showDeviceActions', 'function unmountDevice', 'function goEditDevice', 'function confirmMount']:
    found = [l for l in lines if fn in l]
    if found:
        print(f'{fn}: STILL EXISTS')
        count += 1
for fn in ['const getSlotStyle', 'const rackMatches', 'const rackTooltip', 'const showDeviceActions', 'const unmountDevice', 'const goEditDevice', 'const confirmMount']:
    found = [l for l in lines if fn in l]
    if found:
        print(f'{fn}: REPLACED OK')

print(f'\\nTotal remaining issues: {count}')
print(f'Total lines: {len(lines)}')
