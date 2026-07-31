# Python script to fix RackView.vue
import re
import os

filepath = r'D:\managesys\frontend\src\views\room\RackView.vue'

with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

original = content

# 1) Template: corner label
content = content.replace('通道</el-tag>', '排号</el-tag>')

# 2) Template: remove hot/cold aisle
old_aisle = ('              <div v-if="r &lt; maxRow" :class="[\'aisle-tag\', r % 2 === 1 ? \'aisle-hot\' : \'aisle-cold\']">\n'
    '                <span>{{ r % 2 === 1 ? \'热通道\' : \'冷通道\' }}</span>\n'
    '              </div>\n')
content = content.replace(old_aisle, '')

# 3) Template: remove getSlotClass(r)
old_class = ':class="[{\'has-rack\':getRackAt(r,c)},getSlotClass(r)]"'
new_class = ':class="[{\'has-rack\':getRackAt(r,c)}]"'
content = content.replace(old_class, new_class)

# 4) Script: remove DELETED comments (lines 363-365)
old_deleted1 = ("// DELETED: if (slot.merged) return { display: 'none' }\n"
    "// DELETED:   return { minHeight: slotHeight + 'px' }\n"
    "// DELETED: }\n\n")
content = content.replace(old_deleted1, '')

# 5) Script: remove DELETED lines 410-416 and orphaned braces
old_deleted2 = ("// DELETED: }\n\n"
    "// DELETED: catch { /* cancelled */ }\n"
    "// DELETED:   finally { unmounting.value = false }\n"
    "// DELETED: }\n\n"
    "// DELETED:   try {\n"
    "    })\n"
    "    })\n"
    "}\n")
content = content.replace(old_deleted2, "}\n\n")

# 6) Script: fix fetchRooms try-catch
content = content.replace(
    "    console.error('Failed to fetch rooms:', e)\n  }",
    "  } catch (e) {\n    console.error('Failed to fetch rooms:', e)\n  }"
)

# 7) Script: fix deleteRack function
old_delete = ("async function deleteRack(rack: RackInfo) {\n"
    "  try {\n"
    "    await ElMessageBox.confirm('确定删除机柜「' + rack.code + ' - ' + rack.name + '」？', '确认删除', { type: 'warning' })\n"
    "}")
new_delete = ("async function deleteRack(rack: RackInfo) {\n"
    "  try {\n"
    "    await ElMessageBox.confirm('确定删除机柜「' + rack.code + ' - ' + rack.name + '」？', '确认删除', { type: 'warning' })\n"
    "    await deleteRackApi(rack.id)\n"
    "    ElMessage.success('已删除')\n"
    "    await fetchRacks()\n"
    "  } catch {\n"
    "    // cancelled or error\n"
    "  }\n"
    "}")
content = content.replace(old_delete, new_delete)

# 8) Script: remove orphaned rackMatches/rackTooltip
lines = content.split('\n')
new_lines = []
skip = False
for line in lines:
    s = line.strip()
    if s == 'const rackMatches = (rack: RackInfo): boolean => false;':
        skip = True
        continue
    if skip and s == '}':
        skip = False
        continue
    if s == 'const rackTooltip = (rack: RackInfo): string => "";':
        skip = True
        continue
    if skip and s == '}':
        skip = False
        continue
    new_lines.append(line)
content = '\n'.join(new_lines)

# 9) CSS: remove aisle-related classes
css_remove = [
    '.aisle-tag { display: inline-flex; align-items: center; gap: 2px; font-size: 9px; padding: 1px 6px; border-radius: 8px; font-weight: 600; letter-spacing: 0.5px; }',
    '.aisle-hot { background: #ffebee; color: #c62828; border: 1px solid #ef9a9a; }',
    '.aisle-cold { background: #e3f2fd; color: #1565c0; border: 1px solid #90caf9; }',
    '.aisle-column-gap { display: flex; align-items: center; justify-content: center; padding: 2px 0; margin: 0; width: 24px; flex-shrink: 0; }',
    '.aisle-column-tag { letter-spacing: 1px; }',
    '.aisle-label { display: flex; align-items: center; gap: 3px; font-size: 11px; margin-top: 4px; white-space: nowrap; padding: 2px 8px; border-radius: 4px; }',
    '.rack-box.rack-dimmed { opacity: 0.25; }',
]
for cls in css_remove:
    content = content.replace(cls + '\n', '')
    content = content.replace(cls, '')

# 10) CSS: remove slot-front/slot-back
content = content.replace(
    '.grid-slot.slot-front { background: linear-gradient(180deg, rgba(33,150,243,0.03), rgba(33,150,243,0.06)); }\n', '')
content = content.replace(
    '.grid-slot.slot-back { background: linear-gradient(180deg, rgba(244,67,54,0.03), rgba(244,67,54,0.06)); }\n', '')

# 11) Clean up multiple blank lines
while '\n\n\n' in content:
    content = content.replace('\n\n\n', '\n\n')

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(content)

print('Done!', len(original), '->', len(content), 'bytes')
