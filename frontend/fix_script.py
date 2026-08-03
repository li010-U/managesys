import os
os.chdir('D:/managesys/frontend')

with open('src/layouts/MainLayout.vue', 'r', encoding='utf-8') as f:
    lines = f.readlines()

new_lines = []
for i, line in enumerate(lines):
    new_lines.append(line)
    
    # Fix: add closing brace before toggleFullscreen
    if 'router.push("/profile")' in line:
        if i + 1 < len(lines) and '}' not in lines[i+1]:
            # Add the closing brace
            pass  # Already handled by structure

with open('src/layouts/MainLayout.vue', 'w', encoding='utf-8') as f:
    f.writelines(new_lines)

print('Checking...')
with open('src/layouts/MainLayout.vue', 'r', encoding='utf-8') as f:
    content = f.read()

# Find and fix the section
target = 'else if (cmd === "profile") router.push("/profile")'
idx = content.find(target)
if idx >= 0:
    # Check if there's a closing brace after this
    rest = content[idx + len(target):idx + len(target) + 50]
    if 'function toggleFullscreen' in rest and '}' not in rest[:30]:
        # Need to add closing brace
        old = 'else if (cmd === "profile") router.push("/profile")\n\nfunction toggleFullscreen'
        new = 'else if (cmd === "profile") router.push("/profile")\n  }\n\nfunction toggleFullscreen'
        content = content.replace(old, new)
        
        # Also fix the extra closing brace at end
        old2 = '  }\n}\n}\n</script>'
        new2 = '  }\n}\n</script>'
        content = content.replace(old2, new2)
        
        with open('src/layouts/MainLayout.vue', 'w', encoding='utf-8') as f:
            f.write(content)
        print('Fixed!')
    else:
        print('Already correct or needs different fix')
else:
    print('Target not found')
