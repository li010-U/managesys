import os
os.chdir('D:/managesys/frontend')
with open('src/layouts/MainLayout.vue', 'r', encoding='utf-8') as f:
    lines = f.readlines()

new_lines = []
added_function = False
added_ref = False

for i, line in enumerate(lines):
    new_lines.append(line)
    
    if not added_ref and 'const chatVisible = ref(false)' in line:
        new_lines.append('const isFullscreen = ref(false)\n')
        added_ref = True
    
    if not added_function and 'router.push' in line and 'profile' in line:
        if i + 1 < len(lines) and lines[i+1].strip() == '}':
            new_lines.append('\n')
            new_lines.append('function toggleFullscreen() {\n')
            new_lines.append('  if (!document.fullscreenElement) {\n')
            new_lines.append('    document.documentElement.requestFullscreen()\n')
            new_lines.append('    isFullscreen.value = true\n')
            new_lines.append('  } else {\n')
            new_lines.append('    document.exitFullscreen()\n')
            new_lines.append('    isFullscreen.value = false\n')
            new_lines.append('  }\n')
            new_lines.append('}\n')
            added_function = True

with open('src/layouts/MainLayout.vue', 'w', encoding='utf-8') as f:
    f.writelines(new_lines)

print('Done! Function:', added_function, 'Ref:', added_ref)
