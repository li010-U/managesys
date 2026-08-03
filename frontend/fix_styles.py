import os
os.chdir('D:/managesys/frontend')

with open('src/layouts/MainLayout.vue', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Find the main-container style and fix it
new_lines = []
for i, line in enumerate(lines):
    new_lines.append(line)
    
    # Fix main-container style
    if '.main-container {' in line:
        # Add the missing styles after this line
        new_lines.append('  display: flex;\n')
        new_lines.append('  flex-direction: column;\n')
        new_lines.append('  min-height: 0;\n')
        new_lines.append('  flex: 1;\n')
        new_lines.append('  overflow: hidden;\n')
        # Skip the original lines until we find the closing brace
        while i + 1 < len(lines) and not lines[i+1].strip().startswith('}') and '.sidebar' not in lines[i+1]:
            i += 1
        continue
    
    # Find and fix app-main style
    if '.app-main {' in line:
        # Add the correct styles
        new_lines.append('  padding: 20px;\n')
        new_lines.append('  overflow-y: auto;\n')
        new_lines.append('  overflow-x: hidden;\n')
        new_lines.append('  background: var(--app-bg-page);\n')
        new_lines.append('  flex: 1;\n')
        new_lines.append('  min-height: 0;\n')
        # Skip until closing brace
        while i + 1 < len(lines) and not lines[i+1].strip().startswith('}') and not lines[i+1].strip().startswith('/*'):
            i += 1
        continue

# Write back
with open('src/layouts/MainLayout.vue', 'w', encoding='utf-8') as f:
    f.writelines(new_lines)

print('Styles fixed!')
