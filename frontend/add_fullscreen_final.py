import os
os.chdir('D:/managesys/frontend')

with open('src/layouts/MainLayout.vue', 'r', encoding='utf-8') as f:
    lines = f.readlines()

new_lines = []
i = 0
while i < len(lines):
    line = lines[i]
    new_lines.append(line)
    
    # Add isFullscreen after chatVisible
    if 'const chatVisible = ref(false)' in line and 'isFullscreen' not in line:
        new_lines.append('const isFullscreen = ref(false)\n')
    
    # Find the closing of handleCommand and add toggleFullscreen
    if 'router.push(\"/profile\")' in line and 'handleCommand' in ''.join(lines[max(0,i-10):i]):
        # Check if next line is the closing brace
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
    
    i += 1

# Add fullscreen button before user-info
final_lines = []
for line in new_lines:
    final_lines.append(line)
    if '<div class="user-info">' in line and 'el-tooltip content="全屏"' not in ''.join(final_lines):
        final_lines.insert(-1, '''          <el-tooltip content="全屏" placement="bottom">
            <el-button text class="header-btn" @click="toggleFullscreen">
              <el-icon size="20">
                <FullScreen v-if="!isFullscreen" />
                <Close v-else />
              </el-icon>
            </el-button>
          </el-tooltip>
''')

with open('src/layouts/MainLayout.vue', 'w', encoding='utf-8') as f:
    f.writelines(final_lines)

print('Fullscreen feature added successfully!')
